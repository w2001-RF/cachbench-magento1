"""Test en conditions réelles : politiques du cache objet de Magento comparées sous forte charge.

    python scripts/magento_live_eval.py --users 150 --capacities 1MB,2MB,8MB --reps 5
    python scripts/magento_live_eval.py --report-only --out results/live-all-policies

Plan en blocs aléatoires : chaque répétition est un bloc dans lequel chaque couple (politique,
capacité) passe une fois, dans un ordre tiré au sort (--seed). Dans un bloc r, les visiteurs
virtuels suivent les mêmes parcours (graine r du test de charge) et les politiques aléatoires
ont la graine r : la comparaison est appariée par bloc, et l'ordre aléatoire répartit les
dérives lentes de la machine (températures, antivirus, journaux qui grossissent) entre les
politiques.

Avant chaque passe : politique, capacité et paramètres écrits dans app/etc/local.xml (sauvegardé
puis rétabli à la fin), cache de Magento vidé, état de la politique et journal du cache effacés
(scripts/magento_cache_reset.php). Le cache pleine page (FPC) est coupé pendant le test, sinon
les pages ne passent pas par le cache objet ; son réglage est rétabli à la fin.

lecar, cacheus, arc et lirs comptent des objets : leur capacité est le nombre d'entrées qui tient
sous LRU dans le même nombre d'octets (--unit-bytes : 16 000 o par entrée ; rejeu de quatre journaux
de passes LRU, 60 à 78 entrées par Mo). Ces politiques ignorent la taille des entrées : les octets
réellement occupés en fin de passe sont relevés pour toutes les politiques. OPT connaît l'avenir et ne peut pas tourner sur la boutique : sa borne est calculée
hors ligne en rejouant le journal de chaque passe LRU (--opt-bound).

Une passe = scripts/magento_load_test.py, un palier de --users visiteurs pendant --duration s,
dont les --settle premières ne sont pas mesurées (le cache se remplit). Mesures sur la partie
mesurée : hit rate et byte hit rate du cache objet (journal cache-trace.csv), lectures manquées
par page servie (chacune reconstruit l'entrée, souvent depuis MySQL), temps de réponse des pages
(moyenne, médiane, p95), pages servies sans erreur par seconde, erreurs, plantages d'Apache.

Rapport (report.md, runs.csv, stats.json dans --out) : moyenne ± IC 95 % par politique et
capacité ; test de Friedman par capacité ; chaque politique comparée à la meilleure, par paires
sur les blocs, avec IC de Student et bootstrap, tests t et de Wilcoxon, p corrigés de Holm.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from stats_tools import fmt_p, holm, mean_ci, paired  # noqa: E402

UNITS = {"KB": 1024, "MB": 1024 ** 2}
UNIT_POLICIES = ("lecar", "cacheus", "arc", "lirs")
POLICY_PARAMS = {"drl": {"model": str(ROOT / "models/drl-bytes.json")}}
DEFAULT_POLICIES = "lru,fifo,lfu,arc,lirs,lecar,cacheus,drl,cacheus_pp,cacheus_pp2"
# (clé, nom, échelle, unité, sens : +1 plus grand = mieux, -1 plus petit = mieux)
METRICS = [("hit_rate", "hit rate", 100, "%", 1), ("byte_hit_rate", "byte hit rate", 100, "%", 1),
           ("miss_per_page", "lectures manquées par page", 1, "", -1),
           ("ms_mean", "temps moyen", 1, "ms", -1), ("ms_p50", "médiane", 1, "ms", -1),
           ("ms_p95", "p95", 1, "ms", -1), ("goodput", "pages servies sans erreur", 1, "pages/s", 1),
           ("error_rate", "erreurs", 100, "%", -1)]
TESTED = ["hit_rate", "miss_per_page", "ms_p95", "ms_mean", "goodput"]


def size_bytes(s: str) -> int:
    m = re.fullmatch(r"([0-9.]+)\s*([KM]B)", s.strip(), re.I)
    return int(float(m.group(1)) * UNITS[m.group(2).upper()]) if m else int(s)


def capacity_for(policy: str, cap_label: str, unit_bytes: int) -> int:
    b = size_bytes(cap_label)
    return max(2, round(b / unit_bytes)) if policy in UNIT_POLICIES else b


class Shop:
    def __init__(self, a):
        self.a = a
        self.local_xml = Path(a.magento) / "app/etc/local.xml"
        self.backup = None

    def sql(self, query: str) -> str:
        return subprocess.run([self.a.mysql, "-uroot", "-N", self.a.database, "-e", query],
                              capture_output=True, text=True, check=True).stdout.strip()

    def configure(self, policy: str, capacity: int, seed: int) -> None:
        """Politique, capacité et <params> : la graine, les réglages communs gardés, ceux de la politique."""
        xml = self.backup
        for tag, val in (("policy", policy), ("capacity", str(capacity))):
            xml, n = re.subn(rf"<{tag}>[^<]*</{tag}>", f"<{tag}>{val}</{tag}>", xml, count=1)
            if n != 1:
                raise SystemExit(f"<{tag}> introuvable dans {self.local_xml}")
        m = re.search(r"(<params>)(.*?)(\s*</params>)", xml, re.S)
        if not m:
            raise SystemExit(f"<params> introuvable dans {self.local_xml}")
        indent = re.search(r"\n(\s*)<", m.group(2))
        indent = indent.group(1) if indent else "\n"
        keep = re.search(r"<metadata_capacity>[^<]*</metadata_capacity>(<!--.*?-->)?", m.group(2))
        params = {"seed": seed, **POLICY_PARAMS.get(policy, {})}
        body = "".join(f"\n{indent}<{k}>{v}</{k}>" for k, v in params.items())
        if keep:
            body += f"\n{indent}{keep.group(0)}"
        xml = xml[:m.start()] + m.group(1) + body + m.group(3) + xml[m.end():]
        self.local_xml.write_text(xml, encoding="utf-8")

    def php(self, mode: str) -> dict:
        out = subprocess.run([self.a.php, str(ROOT / "scripts/magento_cache_reset.php"), self.a.magento, mode],
                             capture_output=True, text=True, check=True).stdout
        return json.loads(out.strip().splitlines()[-1])

    def __enter__(self):
        self.backup = self.local_xml.read_text(encoding="utf-8")
        self.fpc = self.sql("select value from core_cache_option where code='fpc'") or None
        self.sql("update core_cache_option set value=0 where code='fpc'")
        return self

    def __exit__(self, *exc):
        self.local_xml.write_text(self.backup, encoding="utf-8")
        if self.fpc is not None:
            self.sql(f"update core_cache_option set value={int(self.fpc)} where code='fpc'")
        self.php("reset")


def cache_metrics(trace: Path, t0: float, t1: float, resident: list[str] | None) -> dict:
    """Hit : lecture réussie (ligne get de coût nul sans autre tag que __id_). Miss : écriture après un échec."""
    hits = n = bytes_hit = bytes_all = 0
    last_size: dict[str, int] = {}
    with trace.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["op"] != "get":
                continue
            size = int(r["size"])
            if resident is not None:
                last_size[r["key"]] = size
            if not t0 <= float(r["ts"]) <= t1:
                continue
            hit = float(r["cost_ms"]) == 0 and all(t.startswith("__id_") for t in r["tags"].split("|") if t)
            n += 1
            bytes_all += size
            if hit:
                hits += 1
                bytes_hit += size
    out = {"cache_accesses": n, "cache_misses": n - hits, "hit_rate": hits / n if n else 0.0,
           "byte_hit_rate": bytes_hit / bytes_all if bytes_all else 0.0}
    if resident is not None:
        out["resident_bytes"] = sum(last_size.get(k, 0) for k in resident)
    return out


def page_metrics(requests: Path, t0: float, t1: float) -> dict:
    ms, errors, n = [], 0, 0
    with requests.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if not t0 <= float(r["start"]) <= t1:
                continue
            n += 1
            if r["error"]:
                errors += 1
            else:
                ms.append(float(r["ms"]))
    ms = np.asarray(ms) if ms else np.zeros(1)
    return {"requests": n, "rps": n / (t1 - t0), "error_rate": errors / n if n else 0.0, "ms_mean": float(ms.mean()),
            "ms_p50": float(np.percentile(ms, 50)), "ms_p95": float(np.percentile(ms, 95))}


def derive(row: dict) -> dict:
    """Mesures tirées des autres (recalculées aussi pour les runs.csv d'anciennes versions)."""
    pages = row["requests"] * (1 - row["error_rate"])
    misses = row.get("cache_misses", row["cache_accesses"] * (1 - row["hit_rate"]))
    row["goodput"] = row["rps"] * (1 - row["error_rate"])
    row["miss_per_page"] = misses / pages if pages else float("nan")
    return row


def warm_up(base: str, tries: int = 5) -> None:
    """Première page après le vidage : Magento reconstruit sa configuration, ce qui peut être long."""
    for i in range(tries):
        try:
            with urllib.request.urlopen(base.rstrip("/") + "/index.php/", timeout=180) as r:
                r.read()
            return
        except OSError:
            time.sleep(10 * (i + 1))
    raise SystemExit(f"boutique injoignable après le vidage du cache : {base}")


def run_one(shop: Shop, a, run_dir: Path, policy: str, cap_label: str, rep: int) -> dict:
    capacity = capacity_for(policy, cap_label, a.unit_bytes)
    shop.configure(policy, capacity, rep)
    cfg = shop.php("reset")
    if cfg["apcu"] or cfg["fpc"] != "off" or cfg["policy"] != policy or cfg["capacity"] != capacity:
        raise SystemExit(f"configuration inattendue : {cfg}")
    run_dir.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(ROOT / "scripts/magento_load_test.py"), a.base, "--users", str(a.users),
           "--step", str(a.duration), "--settle", str(a.settle), "--no-stop", "--seed", str(rep),
           "--think", a.think, "--out", str(run_dir)]
    warm_up(a.base)
    with (run_dir / "load_test.log").open("w", encoding="utf-8") as log:
        subprocess.run(cmd, check=True, stdout=log, stderr=subprocess.STDOUT)
    shutil.copy(Path(a.magento) / "var/aicache/cache-trace.csv", run_dir / "cache-trace.csv")
    state = shop.php("state")
    (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    return analyse_run(run_dir, policy, cap_label, rep, capacity)


def analyse_run(run_dir: Path, policy: str, cap_label: str, rep: int, capacity: int) -> dict:
    step = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))["steps"][0]
    t0, t1 = step["t_measured"], step["t_end"]
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    row = {"run": run_dir.name, "policy": policy, "capacity": cap_label, "rep": rep, "policy_capacity": capacity,
           "users": step["users"], "crashes": step.get("crashes")}
    row.update(page_metrics(run_dir / "requests.csv", t0, t1))
    row.update(cache_metrics(run_dir / "cache-trace.csv", t0, t1, state.get("resident_keys")))
    row.setdefault("resident_bytes", state.get("used_bytes"))
    row["evictions"] = state.get("evictions")
    return derive(row)


def opt_bound(out: Path, rows: list[dict]) -> list[dict]:
    """Hit rate d'OPT et de LRU hors ligne sur le journal de chaque passe LRU (mise en cache dans opt_bound.csv)."""
    from cachebench.engine import EngineConfig, simulate
    from cachebench.policies import get_policy
    from cachebench.traces import load_trace

    path = out / "opt_bound.csv"
    done = {(r["capacity"], int(r["rep"])): r for r in csv.DictReader(path.open(encoding="utf-8"))} if path.exists() else {}
    for r in rows:
        trace_file = out / "runs" / r["run"] / "cache-trace.csv"
        if r["policy"] != "lru" or (r["capacity"], int(r["rep"])) in done or not trace_file.exists():
            continue
        trace = load_trace(trace_file)
        cap = size_bytes(r["capacity"])
        res = {p: simulate(get_policy(p)(cap), trace, EngineConfig())["hit_rate"] for p in ("opt", "lru")}
        done[(r["capacity"], int(r["rep"]))] = {"capacity": r["capacity"], "rep": r["rep"], "opt": res["opt"],
                                                 "lru_offline": res["lru"]}
        print(f"borne OPT {r['capacity']} bloc {r['rep']} : {100 * res['opt']:.2f} % (LRU hors ligne "
              f"{100 * res['lru']:.2f} %)", flush=True)
    bound = sorted(done.values(), key=lambda d: (size_bytes(d["capacity"]), int(d["rep"])))
    if bound:
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["capacity", "rep", "opt", "lru_offline"])
            w.writeheader()
            w.writerows(bound)
    return [dict(d, opt=float(d["opt"]), lru_offline=float(d["lru_offline"])) for d in bound]


def by_block(rows, cap, metric, policies):
    """{bloc: {politique: valeur}} pour les blocs où toutes les politiques demandées ont passé."""
    by = defaultdict(dict)
    for r in rows:
        if r["capacity"] == cap and r["policy"] in policies:
            by[r["rep"]][r["policy"]] = r[metric]
    return {k: v for k, v in sorted(by.items()) if all(p in v for p in policies)}


def fmt_val(v: float, scale: float, unit: str) -> str:
    digits = 2 if unit in ("%", "") else (1 if unit == "pages/s" else 0)
    return f"{v * scale:.{digits}f}"


def report(rows: list[dict], out: Path, a, bound: list[dict]) -> None:
    policies = [p for p in a.policies.split(",") if any(r["policy"] == p for r in rows)]
    caps = sorted({r["capacity"] for r in rows}, key=size_bytes)
    n_blocks = max(r["rep"] for r in rows)
    lines = ["# Test en conditions réelles sur la boutique Magento : toutes les politiques", "",
             f"Généré par `scripts/magento_live_eval.py`. {len(rows)} passes : {len(policies)} politiques × "
             f"{len(caps)} capacités × {n_blocks} blocs, ordre tiré au sort dans chaque bloc. "
             f"{rows[0]['users']} visiteurs simultanés ; {a.duration:.0f} s par passe dont {a.settle:.0f} s non "
             "mesurées ; cache pleine page coupé. Moyenne ± demi-largeur de l'IC à 95 % (Student) sur les blocs.", "",
             f"lecar, cacheus, arc et lirs comptent des objets : capacité = octets / {a.unit_bytes} o (taille moyenne "
             "d'une entrée résidente sous LRU), soit autant d'entrées que LRU. Ils ignorent la taille des entrées : la "
             "colonne « occupé » donne les octets réellement en cache en fin de passe.", ""]
    stats_out = {"cells": [], "friedman": [], "vs_best": [], "opt_bound": bound}
    cell = {}
    for metric, *_ in METRICS + [("resident_bytes",)]:
        for cap in caps:
            for p in policies:
                v = [r[metric] for r in rows if r["policy"] == p and r["capacity"] == cap and r.get(metric) is not None]
                if v:
                    cell[metric, cap, p] = mean_ci(v)
                    stats_out["cells"].append({"metric": metric, "capacity": cap, "policy": p, "mean": cell[metric, cap, p][0],
                                               "ci": cell[metric, cap, p][1], "n": len(v)})

    # tests : Friedman par capacité et mesure, puis chaque politique contre la meilleure, Holm sur l'ensemble
    tests, friedman = [], {}
    for metric, name, scale, unit, sense in METRICS:
        if metric not in TESTED:
            continue
        for cap in caps:
            blocks = by_block(rows, cap, metric, policies)
            if len(blocks) >= 2 and len(policies) >= 3:
                chi2, p = stats.friedmanchisquare(*[[b[pol] for b in blocks.values()] for pol in policies])
                friedman[metric, cap] = (float(chi2), float(p), len(blocks))
                stats_out["friedman"].append({"metric": metric, "capacity": cap, "chi2": chi2, "p": p, "n": len(blocks)})
            best = max(policies, key=lambda pol: sense * cell[metric, cap, pol][0])
            for pol in policies:
                if pol == best:
                    continue
                pair = by_block(rows, cap, metric, (best, pol))
                if len(pair) < 2:
                    continue
                t = paired([b[best] for b in pair.values()], [b[pol] for b in pair.values()])
                t.update(metric=metric, name=name, scale=scale, unit=unit, sense=sense, capacity=cap, best=best, other=pol)
                tests.append(t)
    for t, adj in zip(tests, holm([t["p_t"] for t in tests])):
        t["p_holm"] = adj
    stats_out["vs_best"] = tests
    tied = defaultdict(set)   # (mesure, capacité) -> politiques non distinguables de la meilleure
    for t in tests:
        tied[t["metric"], t["capacity"]].add(t["best"])
        if t["p_holm"] >= 0.05:
            tied[t["metric"], t["capacity"]].add(t["other"])

    lines += ["## En bref", "",
              "Pour chaque capacité : la meilleure politique, et entre parenthèses celles qu'on ne peut pas en "
              "distinguer (p de Holm ≥ 0,05).", "",
              "| Capacité | Hit rate | Lectures manquées / page | p95 | Pages servies / s |", "| --- | --- | --- | --- | --- |"]
    for cap in caps:
        cols = []
        for metric in ("hit_rate", "miss_per_page", "ms_p95", "goodput"):
            best = [t["best"] for t in tests if t["metric"] == metric and t["capacity"] == cap][:1]
            if not best:
                cols.append("—")
                continue
            others = sorted(tied[metric, cap] - set(best), key=policies.index)
            cols.append(f"**{best[0]}**" + (f" ({', '.join(others)})" if others else ""))
        lines.append(f"| {cap} | " + " | ".join(cols) + " |")
    lines.append("")

    bound_by_cap = defaultdict(list)
    for b in bound:
        bound_by_cap[b["capacity"]].append(b)
    for cap in caps:
        order = sorted(policies, key=lambda pol: -cell["hit_rate", cap, pol][0])
        lines += [f"## {cap}", "", "Trié par hit rate.", "",
                  "| Politique | Hit rate (%) | Byte hit rate (%) | Lectures manquées / page | Temps moyen (ms) | "
                  "p95 (ms) | Pages servies / s | Erreurs (%) | Plantages | Occupé (Mo) |",
                  "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for pol in order:
            cols = []
            for metric in ("hit_rate", "byte_hit_rate", "miss_per_page", "ms_mean", "ms_p95", "goodput", "error_rate"):
                _, _, scale, unit, _ = next(m for m in METRICS if m[0] == metric)
                m, h = cell[metric, cap, pol]
                cols.append(f"{fmt_val(m, scale, unit)} ± {fmt_val(h, scale, unit)}")
            crashes = sum(int(r["crashes"] or 0) for r in rows if r["policy"] == pol and r["capacity"] == cap)
            occ = cell.get(("resident_bytes", cap, pol))
            cols += [str(crashes), f"{occ[0] / 2 ** 20:.2f}" if occ else "—"]
            lines.append(f"| {pol} | " + " | ".join(cols) + " |")
        if bound_by_cap[cap]:
            o, oh = mean_ci([b["opt"] for b in bound_by_cap[cap]])
            l, lh = mean_ci([b["lru_offline"] for b in bound_by_cap[cap]])
            lines += ["", f"Borne OPT (hors ligne, journal des passes LRU, {len(bound_by_cap[cap])} blocs) : "
                      f"**{100 * o:.2f} ± {100 * oh:.2f} %** ; LRU rejoué de même : {100 * l:.2f} ± {100 * lh:.2f} %. "
                      "Le rejeu ne compte pas les hits comme le journal de la boutique : comparer OPT au LRU rejoué, "
                      "pas aux colonnes ci-dessus."]
        lines.append("")

    lines += ["## Tests de Friedman", "",
              "Toutes les politiques ont-elles le même rang dans chaque bloc ? (rangs par bloc, sans hypothèse de normalité)", "",
              "| Mesure | Capacité | χ² | blocs | p |", "| --- | --- | ---: | ---: | ---: |"]
    for (metric, cap), (chi2, p, n) in friedman.items():
        name = next(m[1] for m in METRICS if m[0] == metric)
        lines.append(f"| {name} | {cap} | {chi2:.1f} | {n} | {fmt_p(p)} |")

    lines += ["", "## Chaque politique contre la meilleure", "",
              "Δ = autre − meilleure sur les mêmes blocs (négatif = moins bien pour le hit rate et les pages servies, "
              "positif = moins bien pour les temps et les lectures manquées). p de Holm corrigé sur toutes les lignes, "
              f"à partir du test t : avec {n_blocks} blocs, le plus petit p possible du test de Wilcoxon (bilatéral, "
              f"exact) est {2 / 2 ** n_blocks:.4f}.", "",
              "| Mesure | Capacité | Meilleure | Autre | n | Δ | IC 95 % Student | IC 95 % bootstrap | p t | p Wilcoxon | p Holm | v/é/d |",
              "| --- | --- | --- | --- | ---: | ---: | --- | --- | ---: | ---: | ---: | --- |"]
    for t in tests:
        s = t["scale"]
        u = " pts" if t["unit"] == "%" else (f" {t['unit']}" if t["unit"] else "")
        f = (lambda v: f"{v * s:+.2f}") if t["unit"] in ("%", "") else (lambda v: f"{v * s:+.1f}")
        lines.append(f"| {t['name']} | {t['capacity']} | {t['best']} | {t['other']} | {t['n']} | **{f(t['diff'])}{u}** | "
                     f"[{f(t['ci_low'])}, {f(t['ci_high'])}] | [{f(t['boot_low'])}, {f(t['boot_high'])}] | "
                     f"{fmt_p(t['p_t'])} | {fmt_p(t['p_wilcoxon'])} | {fmt_p(t['p_holm'])} | {t['wins']}/{t['ties']}/{t['losses']} |")

    lines += ["", "## Passes", "", "| Ordre | Passe | Politique | Capacité | Bloc | Requêtes | Erreurs | Plantages | Hit rate | p95 |",
              "| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for i, r in enumerate(rows, 1):
        lines.append(f"| {i} | {r['run']} | {r['policy']} | {r['capacity']} | {r['rep']} | {r['requests']} | "
                     f"{100 * r['error_rate']:.1f} % | {r['crashes']} | {100 * r['hit_rate']:.2f} % | {r['ms_p95']:.0f} ms |")
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "stats.json").write_text(json.dumps(stats_out, indent=1, default=float), encoding="utf-8")


def read_runs(path: Path) -> list[dict]:
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    for r in rows:
        for k in list(r):
            if k in ("run", "policy", "capacity", "crashes"):
                continue
            r[k] = None if r[k] in ("", "None") else (float(r[k]) if "." in r[k] or "e" in r[k] else int(r[k]))
        derive(r)
    return rows


def write_runs(path: Path, rows: list[dict]) -> None:
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("base", nargs="?", default="http://127.0.0.1/magento")
    p.add_argument("--policies", default=DEFAULT_POLICIES)
    p.add_argument("--capacities", default="1MB,2MB,8MB")
    p.add_argument("--reps", type=int, default=5, help="nombre de blocs")
    p.add_argument("--users", type=int, default=150, help="visiteurs simultanés")
    p.add_argument("--duration", type=float, default=180, help="durée d'une passe (s)")
    p.add_argument("--settle", type=float, default=45, help="début de passe non mesuré (s)")
    p.add_argument("--think", default="2,8", help="pause entre deux pages, min,max (s)")
    p.add_argument("--seed", type=int, default=2026, help="tirage de l'ordre des passes")
    p.add_argument("--unit-bytes", type=int, default=16000,
                   help="octets par entrée pour lecar, cacheus, arc, lirs (taille moyenne d'une entrée résidente sous LRU)")
    p.add_argument("--no-opt-bound", action="store_true", help="ne pas calculer la borne OPT hors ligne")
    p.add_argument("--resume", action="store_true", help="reprendre un plan interrompu (passes déjà dans runs.csv sautées)")
    p.add_argument("--magento", default="C:/wamp64/www/magento")
    p.add_argument("--php", default="C:/wamp64/bin/php/php7.1.29/php.exe")
    p.add_argument("--mysql", default="C:/wamp64/bin/mysql/mysql5.7.26/bin/mysql.exe")
    p.add_argument("--database", default="magento")
    p.add_argument("--out", default="results/live-all-policies")
    p.add_argument("--report-only", action="store_true")
    a = p.parse_args()
    out = ROOT / a.out
    out.mkdir(parents=True, exist_ok=True)
    runs_csv = out / "runs.csv"

    if a.report_only:
        saved = json.loads((out / "config.json").read_text(encoding="utf-8"))
        a.duration, a.settle = saved["duration"], saved["settle"]
        a.policies, a.unit_bytes = saved["policies"], saved.get("unit_bytes", 0)
        rows = read_runs(runs_csv)
        report(rows, out, a, [] if a.no_opt_bound else opt_bound(out, rows))
        print((out / "report.md").read_text(encoding="utf-8"))
        return 0

    policies, caps = a.policies.split(","), a.capacities.split(",")
    if a.resume:
        plan = [tuple(x) for x in json.loads((out / "plan.json").read_text(encoding="utf-8"))]
        rows = read_runs(runs_csv) if runs_csv.exists() else []
    else:
        rng = random.Random(a.seed)
        plan = []
        for rep in range(1, a.reps + 1):
            block = [(pol, c, rep) for pol in policies for c in caps]
            rng.shuffle(block)
            plan += block
        rows = []
        (out / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
        (out / "config.json").write_text(json.dumps(vars(a), indent=1), encoding="utf-8")
    done = {r["run"] for r in rows}
    left = sum(1 for i, (pol, cap, rep) in enumerate(plan, 1) if f"{i:03d}-{pol}-{cap}-b{rep}" not in done)
    print(f"{left} passes de {a.duration:.0f} s sur {len(plan)}, {a.users} visiteurs : ~{left * (a.duration + 25) / 3600:.1f} h ; "
          f"entrée moyenne {a.unit_bytes} o", flush=True)

    with Shop(a) as shop:
        for i, (pol, cap, rep) in enumerate(plan, 1):
            name = f"{i:03d}-{pol}-{cap}-b{rep}"
            if name in done:
                continue
            row = run_one(shop, a, out / "runs" / name, pol, cap, rep)
            rows.append(row)
            print(f"[{i}/{len(plan)}] {name}: hit {100 * row['hit_rate']:.2f} %, {row['miss_per_page']:.2f} manquées/page, "
                  f"{row['ms_mean']:.0f} ms moy., p95 {row['ms_p95']:.0f} ms, {row['goodput']:.1f} pages/s servies, "
                  f"erreurs {100 * row['error_rate']:.1f} %, plantages {row['crashes']}", flush=True)
            write_runs(runs_csv, rows)
    report(rows, out, a, [] if a.no_opt_bound else opt_bound(out, rows))
    print((out / "report.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
