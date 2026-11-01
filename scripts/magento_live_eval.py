"""Test en conditions réelles : politiques du cache objet de Magento comparées sous forte charge.

    python scripts/magento_live_eval.py --users 100 --capacities 2MB,8MB --reps 6
    python scripts/magento_live_eval.py --report-only --out results/cacheus-pp2-live

Plan en blocs aléatoires : chaque répétition est un bloc dans lequel chaque couple (politique,
capacité) passe une fois, dans un ordre tiré au sort (--seed). Dans un bloc r, les visiteurs
virtuels suivent les mêmes parcours (graine r du test de charge) et CACHEUS++ a la graine r : la
comparaison est appariée par bloc, et l'ordre aléatoire répartit les dérives lentes de la
machine (températures, antivirus, journaux qui grossissent) entre les politiques.

Avant chaque passe : politique, capacité et graine écrites dans app/etc/local.xml (sauvegardé
puis rétabli à la fin), cache de Magento vidé, état de la politique et journal du cache effacés
(scripts/magento_cache_reset.php). Le cache pleine page (FPC) est coupé pendant le test, sinon
les pages ne passent pas par le cache objet ; son réglage est rétabli à la fin.

Une passe = scripts/magento_load_test.py, un palier de --users visiteurs pendant --duration s,
dont les --settle premières ne sont pas mesurées (le cache se remplit). Mesures sur la partie
mesurée : hit rate et byte hit rate du cache objet (journal cache-trace.csv), temps de réponse
des pages (moyenne, médiane, p95), débit, erreurs, plantages d'Apache.

Rapport (report.md, runs.csv, stats.json dans --out) : moyenne ± IC 95 % par politique et
capacité ; comparaisons appariées par bloc avec IC de Student et bootstrap, tests t et de
Wilcoxon, p corrigés de Holm.
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
from itertools import combinations
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from stats_tools import fmt_p, holm, mean_ci, paired  # noqa: E402

UNITS = {"KB": 1024, "MB": 1024 ** 2}
METRICS = [("hit_rate", "hit rate", 100, "%"), ("byte_hit_rate", "byte hit rate", 100, "%"),
           ("ms_mean", "temps moyen", 1, "ms"), ("ms_p50", "médiane", 1, "ms"), ("ms_p95", "p95", 1, "ms"),
           ("rps", "débit", 1, "pages/s"), ("error_rate", "erreurs", 100, "%")]


def size_bytes(s: str) -> int:
    m = re.fullmatch(r"([0-9.]+)\s*([KM]B)", s.strip(), re.I)
    return int(float(m.group(1)) * UNITS[m.group(2).upper()]) if m else int(s)


class Shop:
    def __init__(self, a):
        self.a = a
        self.local_xml = Path(a.magento) / "app/etc/local.xml"
        self.backup = None

    def sql(self, query: str) -> str:
        return subprocess.run([self.a.mysql, "-uroot", "-N", self.a.database, "-e", query],
                              capture_output=True, text=True, check=True).stdout.strip()

    def configure(self, policy: str, capacity: int, seed: int) -> None:
        xml = self.local_xml.read_text(encoding="utf-8")
        for tag, val in (("policy", policy), ("capacity", str(capacity)), ("seed", str(seed))):
            xml, n = re.subn(rf"<{tag}>[^<]*</{tag}>", f"<{tag}>{val}</{tag}>", xml, count=1)
            if n != 1:
                raise SystemExit(f"<{tag}> introuvable dans {self.local_xml}")
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


def cache_metrics(trace: Path, t0: float, t1: float) -> dict:
    """Hit : lecture réussie (ligne get de coût nul sans autre tag que __id_). Miss : écriture après un échec."""
    hits = n = bytes_hit = bytes_all = 0
    with trace.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["op"] != "get" or not t0 <= float(r["ts"]) <= t1:
                continue
            size = int(r["size"])
            hit = float(r["cost_ms"]) == 0 and all(t.startswith("__id_") for t in r["tags"].split("|") if t)
            n += 1
            bytes_all += size
            if hit:
                hits += 1
                bytes_hit += size
    return {"cache_accesses": n, "hit_rate": hits / n if n else 0.0, "byte_hit_rate": bytes_hit / bytes_all if bytes_all else 0.0}


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
    shop.configure(policy, size_bytes(cap_label), rep)
    cfg = shop.php("reset")
    if cfg["apcu"] or cfg["fpc"] != "off" or cfg["policy"] != policy:
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
    return analyse_run(run_dir, policy, cap_label, rep)


def analyse_run(run_dir: Path, policy: str, cap_label: str, rep: int) -> dict:
    step = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))["steps"][0]
    t0, t1 = step["t_measured"], step["t_end"]
    row = {"run": run_dir.name, "policy": policy, "capacity": cap_label, "rep": rep, "users": step["users"],
           "crashes": step.get("crashes")}
    row.update(page_metrics(run_dir / "requests.csv", t0, t1))
    row.update(cache_metrics(run_dir / "cache-trace.csv", t0, t1))
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    row["evictions"] = state.get("evictions")
    return row


def report(rows: list[dict], out: Path, a) -> None:
    # Ordre de --policies : dans chaque paire, B est la politique citée plus loin (la plus récente).
    policies = [p for p in a.policies.split(",") if any(r["policy"] == p for r in rows)]
    caps = sorted({r["capacity"] for r in rows}, key=size_bytes)
    lines = ["# Test en conditions réelles sur la boutique Magento", "",
             f"Généré par `scripts/magento_live_eval.py`. {len(rows)} passes : {len(policies)} politiques × "
             f"{len(caps)} capacités × {max(r['rep'] for r in rows)} blocs, ordre tiré au sort dans chaque bloc. "
             f"{rows[0]['users']} visiteurs simultanés ; {a.duration:.0f} s par passe dont {a.settle:.0f} s non mesurées ; "
             "cache pleine page coupé. Moyenne ± demi-largeur de l'IC à 95 % (Student) sur les blocs.", ""]
    stats_out = {"cells": [], "comparisons": []}
    for metric, name, scale, unit in METRICS:
        lines += [f"## {name[0].upper() + name[1:]} ({unit})", "",
                  "| Capacité | " + " | ".join(policies) + " |", "| --- | " + " | ".join("---:" for _ in policies) + " |"]
        for cap in caps:
            cols = []
            for p in policies:
                v = [r[metric] for r in rows if r["policy"] == p and r["capacity"] == cap]
                m, h = mean_ci(v)
                cols.append(f"{m * scale:.2f} ± {h * scale:.2f}")
                stats_out["cells"].append({"metric": metric, "capacity": cap, "policy": p, "mean": m, "ci": h, "n": len(v)})
            lines.append(f"| {cap} | " + " | ".join(cols) + " |")
        lines.append("")

    lines += ["## Comparaisons appariées par bloc", "",
              "Δ = B − A sur les mêmes blocs. p de Holm corrigé sur toutes les lignes du tableau, à partir du test t : "
              "avec peu de blocs, le test de Wilcoxon ne peut pas descendre assez bas pour survivre à la correction.", "",
              "| Mesure | Capacité | A | B | n | Δ | IC 95 % Student | IC 95 % bootstrap | p t | p Wilcoxon | p Holm | v/é/d |",
              "| --- | --- | --- | --- | ---: | ---: | --- | --- | ---: | ---: | ---: | --- |"]
    tests = []
    for metric, name, scale, unit in METRICS[:5]:
        for cap in caps:
            for pa, pb in combinations(policies, 2):
                by = defaultdict(dict)
                for r in rows:
                    if r["capacity"] == cap and r["policy"] in (pa, pb):
                        by[r["rep"]][r["policy"]] = r[metric]
                reps = sorted(k for k, v in by.items() if pa in v and pb in v)
                if len(reps) < 2:
                    continue
                t = paired([by[k][pa] for k in reps], [by[k][pb] for k in reps])
                t.update(metric=metric, name=name, scale=scale, unit=unit, capacity=cap, a=pa, b=pb)
                tests.append(t)
    for t, adj in zip(tests, holm([t["p_t"] for t in tests])):
        t["p_holm"] = adj
        s, u = t["scale"], (" pts" if t["unit"] == "%" else f" {t['unit']}")
        lines.append(f"| {t['name']} | {t['capacity']} | {t['a']} | {t['b']} | {t['n']} | **{t['diff'] * s:+.2f}{u}** | "
                     f"[{t['ci_low'] * s:+.2f}, {t['ci_high'] * s:+.2f}] | [{t['boot_low'] * s:+.2f}, {t['boot_high'] * s:+.2f}] | "
                     f"{fmt_p(t['p_t'])} | {fmt_p(t['p_wilcoxon'])} | {fmt_p(t['p_holm'])} | {t['wins']}/{t['ties']}/{t['losses']} |")
    stats_out["comparisons"] = tests
    n_blocks = max(r["rep"] for r in rows)
    lines += ["", f"Avec {n_blocks} blocs, le plus petit p possible du test de Wilcoxon (bilatéral, exact) est "
              f"{2 / 2 ** n_blocks:.4f}.", "",
              "## Passes", "", "| Ordre | Passe | Politique | Capacité | Bloc | Requêtes | Erreurs | Plantages | Hit rate | Temps moyen |",
              "| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for i, r in enumerate(rows, 1):
        lines.append(f"| {i} | {r['run']} | {r['policy']} | {r['capacity']} | {r['rep']} | {r['requests']} | "
                     f"{100 * r['error_rate']:.1f} % | {r['crashes']} | {100 * r['hit_rate']:.2f} % | {r['ms_mean']:.0f} ms |")
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "stats.json").write_text(json.dumps(stats_out, indent=1, default=float), encoding="utf-8")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("base", nargs="?", default="http://127.0.0.1/magento")
    p.add_argument("--policies", default="lru,cacheus_pp,cacheus_pp2")
    p.add_argument("--capacities", default="2MB,8MB")
    p.add_argument("--reps", type=int, default=6, help="nombre de blocs")
    p.add_argument("--users", type=int, default=100, help="visiteurs simultanés")
    p.add_argument("--duration", type=float, default=240, help="durée d'une passe (s)")
    p.add_argument("--settle", type=float, default=60, help="début de passe non mesuré (s)")
    p.add_argument("--think", default="2,8", help="pause entre deux pages, min,max (s)")
    p.add_argument("--seed", type=int, default=2026, help="tirage de l'ordre des passes")
    p.add_argument("--magento", default="C:/wamp64/www/magento")
    p.add_argument("--php", default="C:/wamp64/bin/php/php7.1.29/php.exe")
    p.add_argument("--mysql", default="C:/wamp64/bin/mysql/mysql5.7.26/bin/mysql.exe")
    p.add_argument("--database", default="magento")
    p.add_argument("--out", default="results/cacheus-pp2-live")
    p.add_argument("--report-only", action="store_true")
    a = p.parse_args()
    out = ROOT / a.out
    out.mkdir(parents=True, exist_ok=True)
    runs_csv = out / "runs.csv"

    if a.report_only:
        saved = json.loads((out / "config.json").read_text(encoding="utf-8"))
        a.duration, a.settle = saved["duration"], saved["settle"]
        rows = list(csv.DictReader(runs_csv.open(encoding="utf-8")))
        for r in rows:
            for k in r:
                if k not in ("run", "policy", "capacity", "crashes"):
                    r[k] = float(r[k]) if "." in r[k] or "e" in r[k] else int(r[k])
        report(rows, out, a)
        print((out / "report.md").read_text(encoding="utf-8"))
        return 0

    policies, caps = a.policies.split(","), a.capacities.split(",")
    rng = random.Random(a.seed)
    plan = []
    for rep in range(1, a.reps + 1):
        block = [(p, c, rep) for p in policies for c in caps]
        rng.shuffle(block)
        plan += block
    (out / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    (out / "config.json").write_text(json.dumps(vars(a), indent=1), encoding="utf-8")
    print(f"{len(plan)} passes de {a.duration:.0f} s, {a.users} visiteurs : ~{len(plan) * (a.duration + 40) / 3600:.1f} h")

    rows: list[dict] = []
    with Shop(a) as shop:
        for i, (pol, cap, rep) in enumerate(plan, 1):
            name = f"{i:02d}-{pol}-{cap}-b{rep}"
            row = run_one(shop, a, out / "runs" / name, pol, cap, rep)
            rows.append(row)
            print(f"[{i}/{len(plan)}] {name}: hit {100 * row['hit_rate']:.2f} %, {row['ms_mean']:.0f} ms moy., "
                  f"p95 {row['ms_p95']:.0f} ms, {row['rps']:.1f} pages/s, erreurs {100 * row['error_rate']:.1f} %, "
                  f"plantages {row['crashes']}", flush=True)
            with runs_csv.open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(rows)
    report(rows, out, a)
    print((out / "report.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
