"""Évaluation hors ligne de CACHEUS++ v2 face à CACHEUS++, aux politiques classiques et à OPT.

    python scripts/eval_cacheus_pp2.py                 # tout (≈ 30 min sur 14 processus)
    python scripts/eval_cacheus_pp2.py --quick         # 3 répliques, pour vérifier
    python scripts/eval_cacheus_pp2.py --report-only   # refait le rapport depuis offline.csv

Plan d'expérience :

- **synthétique** (générateur Magento 1, 100 000 requêtes) : graines 1 à 20, une trace et une
  graine de politique par réplique ; unités et purge paresseuse (tailles 0,5 à 10 %), puis
  octets et purge immédiate (1 et 5 %). Les graines 101 et 102 ont servi au réglage : aucune
  n'est réutilisée ici.
- **traces Magento réelles** (7 mois, oct. 2019 à avr. 2020) : unités, purge paresseuse, 1, 5
  et 10 % ; graines de politique 1 à 10. Octobre 2019 a servi au réglage : il est montré mais
  exclu de la conclusion « sur les mois », faite sur les 6 autres (une réplique = un mois).
- **journal de la boutique** (results/magento-live/unbounded.cache-trace.csv) : octets, purge
  immédiate, 1 à 16 Mo ; graines 1 à 10. 2 et 8 Mo ont servi au réglage.

Chaque comparaison est appariée (même trace, même graine, même taille). Les politiques
déterministes (lru, lfu, arc, lirs, cacheus, opt) ne tournent qu'une fois par trace.
L'ablation retire une correction à la fois de v2 (« v2 sans x » : x remis à sa valeur
d'origine) pour mesurer ce que chacune apporte.

Sorties dans --out : offline.csv (une ligne par simulation), offline_summary.csv (format des
expériences, lisible dans l'interface), report.md et stats.json.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from cachebench.engine import EngineConfig, apply_size_mode, resolve_capacity, simulate, trace_stats  # noqa: E402
from cachebench.experiment import save, summarize  # noqa: E402
from cachebench.policies import get_policy  # noqa: E402
from cachebench.policies.cacheus_pp2 import ORIGINAL, V2  # noqa: E402
from cachebench.traces import generate, load_trace  # noqa: E402
from stats_tools import fmt_ci, fmt_p, holm, mean_ci, paired  # noqa: E402

MONTHS = ["2019_Oct", "2019_Nov", "2019_Dec", "2020_Jan", "2020_Feb", "2020_Mar", "2020_Apr"]
SCENARIOS = {
    "synth-unit": dict(traces=[f"synth:{s}" for s in range(1, 21)], sizes=["0.5%", "1%", "2%", "5%", "10%"],
                       mode="unit", inv="lazy", seeds=None),
    "synth-bytes": dict(traces=[f"synth:{s}" for s in range(1, 21)], sizes=["1%", "5%"],
                        mode="bytes", inv="eager", seeds=None),
    "magento-months": dict(traces=[f"month:{m}" for m in MONTHS], sizes=["1%", "5%", "10%"],
                           mode="unit", inv="lazy", seeds=list(range(1, 11))),
    "live": dict(traces=["live"], sizes=["1MB", "2MB", "4MB", "8MB", "16MB"],
                 mode="bytes", inv="eager", seeds=list(range(1, 11))),
}
TUNING = {"month:2019_Oct", ("live", "2MB"), ("live", "8MB")}
DETERMINISTIC = ["lru", "lfu", "opt"]
OFFICIAL = ["arc", "lirs", "cacheus"]          # comptent des objets : mode unités seulement
CHANGES = [k for k in V2 if V2[k] != ORIGINAL[k]]
LABELS = {"fix_versions": "versions", "feedback": "contrefactuel", "history_factor": "fantômes ×4",
          "freq_window": "vieillissement", "admission": "sans admission apprise",
          "max_object_fraction": "objets ≤ 50 %"}


def policies(mode: str) -> tuple[list, list]:
    """(politiques déterministes, politiques aléatoires) : (étiquette, nom, paramètres)."""
    det = [(p, p, {}) for p in DETERMINISTIC + (OFFICIAL if mode == "unit" else [])]
    rnd = [("cacheus_pp", "cacheus_pp", {}), ("cacheus_pp2", "cacheus_pp2", {})]
    rnd += [(f"v2 sans {LABELS[k]}", "cacheus_pp2", {k: ORIGINAL[k]}) for k in CHANGES]
    return det, rnd


def load(trace_id: str):
    if trace_id.startswith("synth:"):
        return generate(n_requests=100_000, seed=int(trace_id[6:]))
    if trace_id.startswith("month:"):
        return load_trace(ROOT / f"data/magento_trace_{trace_id[6:]}.csv")
    return load_trace(ROOT / "results/magento-live/unbounded.cache-trace.csv")


def run_group(scenario: str, trace_id: str, size: str, seeds: list[int] | None) -> list[dict]:
    """Toutes les simulations d'une trace et d'une taille (le processus ne charge qu'une trace)."""
    sc = SCENARIOS[scenario]
    trace = apply_size_mode(load(trace_id), sc["mode"])
    cap = resolve_capacity(size, trace_stats(trace))
    cfg = EngineConfig(sizes=sc["mode"], invalidation=sc["inv"])
    reps = seeds or [int(trace_id[6:])]
    det, rnd = policies(sc["mode"])
    rows = []

    def one(label, name, params, seed):
        res = simulate(get_policy(name)(cap, seed=seed, **params), trace, cfg)
        return {"scenario": scenario, "trace": trace_id, "cache_size": size, "capacity_bytes": cap,
                "seed": seed, "policy": label, **res}

    for label, name, params in det:
        r = one(label, name, params, reps[0])
        rows += [dict(r, seed=s) for s in reps]
    for s in reps:
        rows += [one(label, name, params, s) for label, name, params in rnd]
    return rows


# --------------------------------------------------------------------------------------------
# Rapport
# --------------------------------------------------------------------------------------------

def read_rows(path: Path) -> list[dict]:
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    for r in rows:
        r["seed"] = int(r["seed"])
        for k in ("hit_rate", "byte_hit_rate", "latency_mean_ms"):
            r[k] = float(r[k])
    return rows


def is_tuning(scenario: str, trace: str, size: str) -> bool:
    return trace in TUNING or (scenario, size) in TUNING


def pairs(rows: list[dict], a: str, b: str, metric="hit_rate", by_trace_mean=False, exclude_tuning=False):
    """Valeurs appariées de a et b par (scénario, taille). by_trace_mean : une réplique = une trace."""
    cell = defaultdict(dict)
    for r in rows:
        if r["policy"] in (a, b) and not (exclude_tuning and is_tuning(r["scenario"], r["trace"], r["cache_size"])):
            cell[(r["scenario"], r["cache_size"], r["trace"], r["seed"])][r["policy"]] = r[metric]
    out = defaultdict(lambda: ([], []))
    if by_trace_mean:
        per_trace = defaultdict(lambda: ([], []))
        for (sc, sz, tr, _), v in cell.items():
            if a in v and b in v:
                per_trace[(sc, sz, tr)][0].append(v[a])
                per_trace[(sc, sz, tr)][1].append(v[b])
        for (sc, sz, _), (xa, xb) in per_trace.items():
            out[(sc, sz)][0].append(float(np.mean(xa)))
            out[(sc, sz)][1].append(float(np.mean(xb)))
    else:
        for (sc, sz, _, _), v in sorted(cell.items(), key=lambda kv: (kv[0][2], kv[0][3])):
            if a in v and b in v:
                out[(sc, sz)][0].append(v[a])
                out[(sc, sz)][1].append(v[b])
    return out


def size_key(s: str) -> float:
    return float(s.rstrip("%MB")) * (1e6 if s.endswith("MB") else 1)


def cells(rows):
    keys = {(r["scenario"], r["cache_size"]) for r in rows}
    order = list(SCENARIOS)
    return sorted(keys, key=lambda k: (order.index(k[0]), size_key(k[1])))


def report(rows: list[dict], out: Path, elapsed: float | None) -> None:
    lines = ["# CACHEUS++ v2 : évaluation hors ligne", "",
             "Généré par `scripts/eval_cacheus_pp2.py`. Hit rate en %, moyenne ± demi-largeur de "
             "l'intervalle de confiance à 95 % (Student). Différences en points de pourcentage (pts).", ""]
    n_sims = len(rows)
    lines += [f"{n_sims} lignes de simulation" + (f", {elapsed / 60:.0f} min de calcul." if elapsed else "."), ""]
    lines += ["## Protocole", "",
              "- Répliques : synthétique, une trace par graine (n = 20) ; mois réels et boutique, la "
              "graine de la politique (n = 10) ; « 6 mois » : une réplique = un mois (moyenne de ses "
              "10 graines), octobre 2019 exclu car utilisé pour le réglage.",
              "- Cas marqués ⚙ : utilisés pour régler v2 (choix des paramètres) ; les autres n'ont "
              "jamais été vus pendant le réglage.",
              "- Tests appariés : t de Student et rangs signés de Wilcoxon ; p de Holm corrigé sur "
              "l'ensemble des cas du tableau ; IC bootstrap à 95 % (10 000 tirages) en plus de l'IC "
              "de Student.", ""]

    stats_out = {"main": [], "months_pooled": [], "ablation": []}

    # --- 1. hit rates ---
    show = ["lru", "lfu", "arc", "lirs", "cacheus", "cacheus_pp", "cacheus_pp2", "opt"]
    lines += ["## 1. Hit rate par politique", "",
              "| Scénario | Taille | " + " | ".join(show) + " |",
              "| --- | --- | " + " | ".join("---:" for _ in show) + " |"]
    for sc, sz in cells(rows):
        vals = defaultdict(lambda: defaultdict(list))
        for r in rows:
            if r["scenario"] == sc and r["cache_size"] == sz:
                vals[r["policy"]][(r["trace"], r["seed"])] = r["hit_rate"]
        cols = []
        for p in show:
            v = list(vals[p].values()) if p in vals else []
            if not v:
                cols.append("—")
                continue
            # Une trace par réplique (synthétique) ou moyenne sur les traces : IC sur les répliques
            cols.append(fmt_ci(*mean_ci(v)))
        mark = " ⚙" if (sc, sz) in TUNING else ""
        lines.append(f"| {sc} | {sz}{mark} | " + " | ".join(cols) + " |")
    lines += ["", "Pour magento-months, la moyenne porte sur les 7 mois × 10 graines.", ""]

    # --- 2. v2 contre CACHEUS++ ---
    def comparison_table(title, pr, note, key):
        tests = []
        for (sc, sz), (a, b) in sorted(pr.items(), key=lambda kv: cells(rows).index(kv[0])):
            t = paired(a, b)
            t.update(scenario=sc, size=sz, tuning=(sc, sz) in TUNING)
            tests.append(t)
        for t, adj in zip(tests, holm([t["p_wilcoxon"] for t in tests])):
            t["p_holm"] = adj
        opt = pairs(rows, "cacheus_pp", "opt")
        lines.extend([f"## {title}", "", note, "",
                      "| Scénario | Taille | n | cacheus_pp | cacheus_pp2 | Δ (pts) | IC 95 % Student | IC 95 % bootstrap | p t | p Wilcoxon | p Holm | d_z | v/é/d | écart à opt comblé |",
                      "| --- | --- | ---: | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | --- | ---: |"])
        for t in tests:
            o = opt.get((t["scenario"], t["size"]))
            closed = ""
            if o:
                gap = float(np.mean(o[1]) - np.mean(o[0]))
                closed = f"{100 * t['diff'] / gap:.0f} %" if gap > 1e-9 else "—"
            mark = " ⚙" if t["tuning"] else ""
            lines.append(
                f"| {t['scenario']} | {t['size']}{mark} | {t['n']} | {100 * t['mean_a']:.2f} | {100 * t['mean_b']:.2f} | "
                f"**{100 * t['diff']:+.2f}** | [{100 * t['ci_low']:+.2f}, {100 * t['ci_high']:+.2f}] | "
                f"[{100 * t['boot_low']:+.2f}, {100 * t['boot_high']:+.2f}] | {fmt_p(t['p_t'])} | "
                f"{fmt_p(t['p_wilcoxon'])} | {fmt_p(t['p_holm'])} | {t['dz']:.2f} | "
                f"{t['wins']}/{t['ties']}/{t['losses']} | {closed} |")
        lines.append("")
        stats_out[key] = tests
        return tests

    comparison_table("2. CACHEUS++ v2 contre CACHEUS++", pairs(rows, "cacheus_pp", "cacheus_pp2"),
                     "Différence appariée cacheus_pp2 − cacheus_pp. v/é/d : répliques où v2 gagne, fait "
                     "jeu égal, perd. « Écart comblé » : part de l'écart opt − cacheus_pp rattrapée.", "main")
    months = {k: v for k, v in pairs(rows, "cacheus_pp", "cacheus_pp2", by_trace_mean=True,
                                     exclude_tuning=True).items() if k[0] == "magento-months"}
    if months:
        comparison_table("3. Sur les 6 mois non vus au réglage (une réplique = un mois)", months,
                         "Généralisation à d'autres périodes de trafic : chaque mois compte pour une "
                         "réplique (moyenne de ses 10 graines).", "months_pooled")
        lines += ["Détail par mois (Δ en pts, IC 95 % sur les 10 graines) :", "",
                  "| Mois | " + " | ".join(SCENARIOS["magento-months"]["sizes"]) + " |",
                  "| --- | " + " | ".join("---:" for _ in SCENARIOS["magento-months"]["sizes"]) + " |"]
        for m in MONTHS:
            cols = []
            for sz in SCENARIOS["magento-months"]["sizes"]:
                sub = [r for r in rows if r["trace"] == f"month:{m}" and r["cache_size"] == sz]
                pr = pairs(sub, "cacheus_pp", "cacheus_pp2").get(("magento-months", sz))
                if pr:
                    t = paired(*pr, n_boot=1000)
                    cols.append(f"{100 * t['diff']:+.2f} [{100 * t['ci_low']:+.2f}, {100 * t['ci_high']:+.2f}]")
                else:
                    cols.append("—")
            lines.append(f"| {m}{' ⚙' if f'month:{m}' in TUNING else ''} | " + " | ".join(cols) + " |")
        lines.append("")

    # --- 4. ablation ---
    labels = [f"v2 sans {LABELS[k]}" for k in CHANGES]
    lines += ["## 4. Ablation : ce qu'apporte chaque correction", "",
              "Δ = cacheus_pp2 − (v2 sans la correction), en pts, sur les cas non vus au réglage "
              "(moyenne des cas, IC 95 % sur l'ensemble des répliques appariées de ces cas). Positif : la "
              "correction aide.", "",
              "| Correction | Δ moyen (pts) | IC 95 % | p Wilcoxon | p Holm | cas où elle aide / nuit (IC hors de 0) |",
              "| --- | ---: | --- | ---: | ---: | --- |"]
    abl = []
    for lab, k in zip(labels, CHANGES):
        pr = pairs(rows, lab, "cacheus_pp2", exclude_tuning=True)
        a = [x for v in pr.values() for x in v[0]]
        b = [x for v in pr.values() for x in v[1]]
        if not a:
            continue
        t = paired(a, b)
        helps = hurts = 0
        for v in pr.values():
            c = paired(*v, n_boot=200)
            helps += c["ci_low"] > 0
            hurts += c["ci_high"] < 0
        t.update(change=k, label=LABELS[k], helps=helps, hurts=hurts, cells=len(pr))
        abl.append(t)
    for t, adj in zip(abl, holm([t["p_wilcoxon"] for t in abl])):
        t["p_holm"] = adj
        lines.append(f"| {t['label']} (`{t['change']}`) | {100 * t['diff']:+.3f} | "
                     f"[{100 * t['ci_low']:+.3f}, {100 * t['ci_high']:+.3f}] | {fmt_p(t['p_wilcoxon'])} | "
                     f"{fmt_p(t['p_holm'])} | {t['helps']} / {t['hurts']} sur {t['cells']} |")
    stats_out["ablation"] = abl
    lines.append("")
    lines += ["Détail par cas (Δ en pts) :", "",
              "| Scénario | Taille | " + " | ".join(LABELS[k] for k in CHANGES) + " |",
              "| --- | --- | " + " | ".join("---:" for _ in CHANGES) + " |"]
    for sc, sz in cells(rows):
        cols = []
        for lab in labels:
            pr = pairs([r for r in rows if r["scenario"] == sc and r["cache_size"] == sz], lab, "cacheus_pp2")
            v = pr.get((sc, sz))
            cols.append(f"{100 * (np.mean(v[1]) - np.mean(v[0])):+.2f}" if v else "—")
        lines.append(f"| {sc} | {sz}{' ⚙' if (sc, sz) in TUNING else ''} | " + " | ".join(cols) + " |")
    lines.append("")

    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text("\n".join(lines), encoding="utf-8")
    (out / "stats.json").write_text(json.dumps(stats_out, indent=1, default=float), encoding="utf-8")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", default="results/cacheus-pp2")
    p.add_argument("--workers", type=int, default=14)
    p.add_argument("--quick", action="store_true", help="3 répliques par cas")
    p.add_argument("--scenarios", nargs="*", default=list(SCENARIOS))
    p.add_argument("--report-only", action="store_true")
    a = p.parse_args()
    out = ROOT / a.out
    csv_path = out / "offline.csv"
    if a.report_only:
        report(read_rows(csv_path), out, None)
        print((out / "report.md").read_text(encoding="utf-8"))
        return

    groups = []
    for sc in a.scenarios:
        spec = SCENARIOS[sc]
        traces = spec["traces"][:3] if a.quick else spec["traces"]
        seeds = (spec["seeds"][:3] if a.quick else spec["seeds"]) if spec["seeds"] else None
        groups += [(sc, t, sz, seeds) for t in traces for sz in spec["sizes"]]
    groups.sort(key=lambda g: g[1] != "live")   # les plus longs d'abord
    t0 = time.time()
    rows: list[dict] = []
    with ProcessPoolExecutor(a.workers) as ex:
        futs = {ex.submit(run_group, *g): g for g in groups}
        for i, f in enumerate(as_completed(futs), 1):
            rows += f.result()
            g = futs[f]
            print(f"[{i}/{len(groups)}] {g[0]} {g[1]} {g[2]} ({time.time() - t0:.0f} s)", flush=True)
    save(rows, csv_path)
    save(summarize([dict(r, trace=f"{r['scenario']}/{r['trace']}") for r in rows]), out / "offline_summary.csv")
    report(read_rows(csv_path), out, time.time() - t0)
    print((out / "report.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
