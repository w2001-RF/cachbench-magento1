"""Pourquoi OPT (Belady) fait mieux que CACHEUS++ : analyse requête par requête.

    python scripts/analyze_opt_gap.py                    # traces et tailles par défaut
    python scripts/analyze_opt_gap.py --sizes 1% 5% --sample 4000

Sur chaque trace et taille de cache, rejoue opt, cacheus_pp et lru avec le moteur de
cachebench, en observant CACHEUS++ de l'intérieur (choix de l'expert, victime, refus
d'admission, retraits imposés), puis compare chaque décision au futur de la trace :

1. écart : requêtes servies par opt et manquées par cacheus_pp, classées par cause
   (clé évincée avant par l'expert LRU, LFU ou GDSF ; refusée à l'admission ; retirée par
   une purge ou un changement de taille) ;
2. qualité des évictions : rang de la victime parmi les clés présentes, classées de la plus
   lointaine prochaine demande (0 = choix de Belady) à la plus proche (1 = pire choix) ; même
   mesure pour le candidat de chacun des trois experts au même instant, et part des
   évictions où l'expert tiré au sort était le meilleur des trois ;
3. pollution : part du cache occupée par des clés qui ne seront plus jamais demandées
   (opt n'en admet aucune) ;
4. écart par popularité de la clé, par distance de réutilisation et par type de page.

Écrit un rapport (report.md) et les chiffres (summary.json) dans --out.
"""
from __future__ import annotations

import argparse
import bisect
import heapq
import json
import math
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cachebench.engine import EngineConfig, apply_size_mode, resolve_capacity, simulate, trace_stats  # noqa: E402
from cachebench.policies import get_policy  # noqa: E402
from cachebench.traces import GET, generate, load_trace  # noqa: E402

EXPERTS = ("LRU", "LFU", "GDSF")
TRACES = {
    # nom : (chargement, mode des tailles, invalidation) — mêmes réglages que les expériences du dépôt
    "magento1-synth": (lambda: generate(n_requests=100_000, seed=1), "unit", "lazy"),
    "magento-2020-Mar": (lambda: load_trace("data/magento_trace_2020_Mar.csv"), "unit", "lazy"),
    "magento-live": (lambda: load_trace("results/magento-live/unbounded.cache-trace.csv"), "bytes", "eager"),
}
DEFAULT_SIZES = {"magento1-synth": ["1%", "5%"], "magento-2020-Mar": ["1%", "5%"], "magento-live": ["8MB"]}


class Watch:
    """Observe un CacheusPP (adaptateur cachebench) sans changer ses décisions."""

    def __init__(self, policy, played, sample_every: int):
        self.p, self.alg = policy, policy._alg
        self.keys = [r.key for r in played]
        self.pos_of: dict[str, list[int]] = defaultdict(list)
        for i, k in enumerate(self.keys):
            self.pos_of[k].append(i)
        self.pos = -1
        self.sample_every = sample_every
        self.history: dict[str, list[tuple[int, str]]] = defaultdict(list)   # clé -> [(position, évènement)]
        self.evictions = Counter()
        self.samples: list[dict] = []
        self.weights: list[list[float]] = []
        self.rejections = 0
        self._wrap()

    def next_use(self, key: str, pos: int) -> float:
        p = self.pos_of.get(key, [])
        j = bisect.bisect_right(p, pos)
        return p[j] if j < len(p) else math.inf

    def _wrap(self):
        alg, p = self.alg, self.p
        access, select, should, drop = p.access, alg._select_victim, alg.should_cache, p._drop

        def access_w(req):
            self.pos += 1
            if self.pos % 2000 == 0:
                self.weights.append(alg.weights.round(4).tolist())
            return access(req)

        def select_w(incoming):
            sample = self.evictions.total() % self.sample_every == 0
            if sample:
                # candidats des trois experts avant le tirage (le tirage n'en dépend pas)
                cands = (next(iter(alg._lru)), self._peek_copy(alg._lfu_heap), self._peek_copy(alg._gdsf_heap))
            victim, expert, state = select(incoming)
            self.evictions[EXPERTS[expert]] += 1
            self.history[victim].append((self.pos, f"évincée par {EXPERTS[expert]}"))
            if sample:
                self.samples.append(self._grade(victim, expert, cands))
            return victim, expert, state

        def should_w(creq):
            ok = should(creq)
            if not ok:
                self.rejections += 1
                too_big = creq.size > alg.cache_size * alg.max_object_fraction
                self.history[creq.key].append((self.pos, "trop grosse (> 10 % du cache)" if too_big else "refusée à l'admission"))
            return ok

        def drop_w(key):
            self.history[key].append((self.pos, "retirée (purge ou nouvelle taille)"))
            return drop(key)

        p.access, alg._select_victim, alg.should_cache, p._drop = access_w, select_w, should_w, drop_w

    def _peek_copy(self, heap: list):
        """Ce que _peek renverrait, lu sur une copie : _peek jette les entrées périmées du tas,
        ce qui change les décisions suivantes (bogue de version, voir le rapport)."""
        h = list(heap)
        while h:
            item = heapq.heappop(h)
            if self.alg._is_current(item):
                return item[-1]
        return None

    def _grade(self, victim, expert, cands) -> dict:
        res = list(self.alg._meta)
        nxt = np.array([self.next_use(k, self.pos) for k in res])

        def rank(key):     # part des présentes demandées plus tard que `key` : 0 = choix de Belady
            if key is None:
                return None
            return float((nxt > self.next_use(key, self.pos)).mean())
        ranks = [rank(c) for c in cands]
        valid = [r for r in ranks if r is not None]
        return {"victim_rank": rank(victim), "expert": EXPERTS[expert], "cand_ranks": ranks,
                "chosen_is_best": ranks[expert] is not None and ranks[expert] <= min(valid),
                "dead_share": float(np.isinf(nxt).mean()), "victim_dead": math.isinf(self.next_use(victim, self.pos))}


def measured_mask(trace, warmup: float) -> np.ndarray:
    """Pour chaque requête jouée (GET cachable) : est-elle mesurée (après la chauffe) ? Comme engine.simulate."""
    n_gets = sum(1 for r in trace if r.op == GET)
    warm, seen, out = int(n_gets * warmup), 0, []
    for r in trace:
        if r.op != GET:
            continue
        seen += 1
        if r.cacheable:
            out.append(seen > warm)
    return np.array(out)


def bucket(value, edges, labels):
    for e, lab in zip(edges, labels):
        if value < e:
            return lab
    return labels[-1]


def analyze(name, trace, sizes_mode, inval, size_spec, seed, sample_every):
    trace = apply_size_mode(trace, sizes_mode)
    cfg = EngineConfig(sizes=sizes_mode, invalidation=inval, warmup=0.1)
    cap = resolve_capacity(size_spec, trace_stats(trace))
    played = [r for r in trace if r.op == GET and r.cacheable]
    mask = measured_mask(trace, cfg.warmup)

    hits = {}
    res = {}
    for pol in ("opt", "lru", "cacheus_pp"):
        h: list[int] = []
        res[pol] = simulate(get_policy(pol)(cap, seed=seed), trace, cfg, hits_out=h)["hit_rate"]
        hits[pol] = np.array(h, dtype=bool)
    # même rejeu, observé de l'intérieur ; les décisions doivent être identiques
    watched = get_policy("cacheus_pp")(cap, seed=seed)
    w = Watch(watched, played, sample_every)
    h = []
    simulate(watched, trace, cfg, hits_out=h)
    if not np.array_equal(np.array(h, dtype=bool), hits["cacheus_pp"]):
        raise SystemExit("l'observation a changé les décisions de cacheus_pp : analyse invalide")

    opt, cpp = hits["opt"] & mask, hits["cacheus_pp"] & mask
    gap_idx = np.flatnonzero(opt & ~cpp)
    rev_idx = np.flatnonzero(cpp & ~opt)
    freq = Counter(w.keys)
    order = {k: i for i, (k, _) in enumerate(freq.most_common())}
    nkeys = len(order)
    prev: dict[str, int] = {}
    reuse = np.full(len(played), -1)
    for i, k in enumerate(w.keys):
        if k in prev:
            reuse[i] = i - prev[k]
        prev[k] = i

    # cause du miss : dernier évènement de la clé avant la requête (un retrait pendant la requête
    # elle-même, nouvelle taille de page, compte aussi)
    causes = Counter()
    for i in gap_idx:
        ev = w.history.get(w.keys[i], [])
        j = bisect.bisect_right([p for p, _ in ev], i) - 1
        causes[ev[j][1] if j >= 0 else "jamais vue / autre"] += 1

    def split(idx, fn):
        c = Counter(fn(i) for i in idx)
        return {k: v for k, v in sorted(c.items(), key=lambda kv: -kv[1])}

    pop_lab = ["top 1 % des clés", "1-10 %", "10-50 %", "50-100 % (traîne)"]
    pop = split(gap_idx, lambda i: bucket(order[w.keys[i]] / nkeys, [0.01, 0.10, 0.50, 2], pop_lab))
    n_res = max(1, len(watched._alg._meta))
    dist_lab = [f"< capacité ({n_res} clés)", "1-4 × capacité", "4-16 × capacité", "> 16 × capacité"]
    dist = split(gap_idx, lambda i: bucket(reuse[i] / n_res, [1, 4, 16, math.inf], dist_lab))
    kinds = split(gap_idx, lambda i: played[i].kind or "?")

    s = w.samples
    by_exp = defaultdict(list)
    for x in s:
        for e, r in zip(EXPERTS, x["cand_ranks"]):
            if r is not None:
                by_exp[e].append(r)
    best_of_three = [min(r for r in x["cand_ranks"] if r is not None) for x in s]
    one_hit = sum(1 for k in w.keys if freq[k] == 1) / len(w.keys)
    measured = int(mask.sum())
    out = {
        "trace": name, "size": size_spec, "capacity": cap, "sizes": sizes_mode, "invalidation": inval,
        "played": len(played), "measured": measured, "unique_keys": nkeys, "one_hit_request_share": one_hit,
        "hit_rate": res, "gap_points": (res["opt"] - res["cacheus_pp"]) * 100,
        "gap_requests": int(len(gap_idx)), "reverse_requests": int(len(rev_idx)),
        "gap_causes": dict(causes.most_common()), "gap_by_popularity": pop, "gap_by_reuse": dist, "gap_by_kind": kinds,
        "evictions_by_expert": dict(w.evictions), "admission_rejections": w.rejections,
        "final_weights": dict(zip(EXPERTS, watched._alg.weights.round(3).tolist())),
        "weights_min_max": {e: [round(min(v[i] for v in w.weights), 3), round(max(v[i] for v in w.weights), 3)]
                            for i, e in enumerate(EXPERTS)} if w.weights else {},
        "sampled_evictions": len(s),
        "victim_rank_mean": float(np.mean([x["victim_rank"] for x in s])) if s else None,
        "expert_rank_mean": {e: float(np.mean(v)) for e, v in by_exp.items()},
        "best_of_three_rank_mean": float(np.mean(best_of_three)) if s else None,
        "chosen_is_best_share": float(np.mean([x["chosen_is_best"] for x in s])) if s else None,
        "dead_share_in_cache": float(np.mean([x["dead_share"] for x in s])) if s else None,
        "victim_dead_share": float(np.mean([x["victim_dead"] for x in s])) if s else None,
    }
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--traces", nargs="*", default=list(TRACES))
    p.add_argument("--sizes", nargs="*", help="tailles de cache (par défaut : selon la trace)")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--sample", type=int, default=3000, help="évictions notées au plus (échantillon régulier)")
    p.add_argument("--out", default="results/opt-gap")
    a = p.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    results = []
    for name in a.traces:
        loader, mode, inval = TRACES[name]
        t0 = time.time()
        trace = loader()
        for size in a.sizes or DEFAULT_SIZES[name]:
            # environ `--sample` évictions notées : on estime leur nombre par une passe lru
            r = analyze_sampled(name, trace, mode, inval, size, a.seed, a.sample)
            results.append(r)
            print(f"{name} {size}: opt {r['hit_rate']['opt']:.4f}  cacheus_pp {r['hit_rate']['cacheus_pp']:.4f}  "
                  f"lru {r['hit_rate']['lru']:.4f}  écart {r['gap_points']:.2f} pts  ({time.time() - t0:.0f} s)", flush=True)
    (out / "summary.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "report.md").write_text(report(results), encoding="utf-8")
    print(f"\nrapport : {out / 'report.md'}")
    return 0


def analyze_sampled(name, trace, mode, inval, size, seed, target):
    # une passe lru donne l'ordre de grandeur du nombre d'évictions, pour échantillonner ~target évictions
    t = apply_size_mode(trace, mode)
    cap = resolve_capacity(size, trace_stats(t))
    lru = get_policy("lru")(cap)
    simulate(lru, t, EngineConfig(sizes=mode, invalidation=inval))
    every = max(1, lru.evictions // target)
    return analyze(name, trace, mode, inval, size, seed, every)


def pct(x):
    return f"{x * 100:.1f} %"


def report(results) -> str:
    L = ["# Écart entre OPT et CACHEUS++", "",
         "Rejeu des mêmes traces par opt (Belady, connaît le futur), cacheus_pp et lru ; CACHEUS++ "
         "observé de l'intérieur. Généré par `scripts/analyze_opt_gap.py`.", "",
         "| Trace | Taille | opt | cacheus_pp | lru | écart opt − c++ | requêtes de l'écart | inverses |",
         "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for r in results:
        h = r["hit_rate"]
        L.append(f"| {r['trace']} | {r['size']} | {pct(h['opt'])} | {pct(h['cacheus_pp'])} | {pct(h['lru'])} | "
                 f"{r['gap_points']:.2f} pts | {r['gap_requests']} | {r['reverse_requests']} |")
    for r in results:
        g = r["gap_requests"] or 1
        L += ["", f"## {r['trace']}, {r['size']} ({r['capacity']} {'objets' if r['sizes'] == 'unit' else 'octets'})", "",
              f"{r['played']} requêtes cachables, {r['unique_keys']} clés ; {pct(r['one_hit_request_share'])} des "
              f"requêtes portent sur une clé vue une seule fois.", "",
              "**Cause du miss dans CACHEUS++** (requêtes servies par opt) :", ""]
        L += [f"- {k} : {v} ({pct(v / g)})" for k, v in r["gap_causes"].items()]
        L += ["", "**Qualité des évictions** (rang de la victime : 0 = choix de Belady, 0,5 = au hasard, 1 = pire) :", "",
              f"- victime choisie : {r['victim_rank_mean']:.3f} ; meilleur des trois candidats : "
              f"{r['best_of_three_rank_mean']:.3f} ; expert tiré = meilleur des trois dans "
              f"{pct(r['chosen_is_best_share'])} des cas",
              "- candidat de chaque expert : " + ", ".join(f"{e} {v:.3f}" for e, v in r["expert_rank_mean"].items()),
              f"- évictions par expert : {r['evictions_by_expert']} ; poids finaux {r['final_weights']}, "
              f"min-max au fil du temps {r['weights_min_max']}",
              f"- pollution : {pct(r['dead_share_in_cache'])} du cache occupé par des clés jamais redemandées ; "
              f"victime déjà « morte » dans {pct(r['victim_dead_share'])} des évictions ; "
              f"refus d'admission : {r['admission_rejections']}", "",
              "**Écart par popularité** : " + ", ".join(f"{k} {pct(v / g)}" for k, v in r["gap_by_popularity"].items()),
              "", "**Écart par distance de réutilisation** : " + ", ".join(f"{k} {pct(v / g)}" for k, v in r["gap_by_reuse"].items()),
              "", "**Écart par type de page** : " + ", ".join(f"{k} {pct(v / g)}" for k, v in list(r["gap_by_kind"].items())[:6])]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    sys.exit(main())
