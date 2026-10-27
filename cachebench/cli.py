"""Ligne de commande : cachebench run | gen-trace | stats | list."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from . import experiment
from .engine import trace_stats
from .policies import available
from .traces import read_csv, write_csv
from .traces.magento1 import Magento1Config, generate


def _cmd_run(a) -> int:
    cfg = experiment.load(a.config)
    rows = experiment.run(cfg, progress=(lambda *_: None) if a.quiet else print)
    out = a.output or cfg.get("output") or "results/results.csv"
    experiment.save(rows, out)
    summary = experiment.summarize(rows)
    experiment.save(summary, out.replace(".csv", "_summary.csv"))
    print()
    print(experiment.format_summary(summary))
    print(f"\nRésultats : {out}")
    return 0


def _cmd_gen(a) -> int:
    overrides = json.loads(a.params) if a.params else {}
    trace = generate(Magento1Config(n_requests=a.n, seed=a.seed), **overrides)
    n = write_csv(trace, a.out)
    print(f"{n} événements écrits dans {a.out}")
    print(json.dumps(asdict(trace_stats(trace)), indent=2))
    return 0


def _cmd_train_drl(a) -> int:
    from .engine import apply_size_mode, resolve_capacity
    from .policies.drl import train
    if a.trace:
        trace = list(read_csv(a.trace))
        source = a.trace
    else:
        overrides = json.loads(a.params) if a.params else {}
        trace = generate(Magento1Config(n_requests=a.n, seed=a.seed), **overrides)
        source = f"magento1 seed={a.seed} n={a.n}"
    trace = apply_size_mode(trace, a.sizes)
    capacity = resolve_capacity(a.capacity, trace_stats(trace))
    info = train(trace, capacity, a.out, k=a.k, horizon=a.horizon, epochs=a.epochs, seed=a.seed,
                 meta={"sizes": a.sizes, "trained_on": source, "capacity_spec": a.capacity})
    print(f"Modèle écrit dans {a.out} : {json.dumps(info)}")
    return 0


def _cmd_stats(a) -> int:
    print(json.dumps(asdict(trace_stats(list(read_csv(a.trace)))), indent=2))
    return 0


def _cmd_list(_a) -> int:
    print("\n".join(available()))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="cachebench", description="Benchmark d'algorithmes de cache pour Magento")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="lancer une expérience décrite en YAML")
    r.add_argument("config")
    r.add_argument("-o", "--output")
    r.add_argument("-q", "--quiet", action="store_true")
    r.set_defaults(fn=_cmd_run)

    g = sub.add_parser("gen-trace", help="générer une trace synthétique Magento 1")
    g.add_argument("out")
    g.add_argument("-n", type=int, default=100_000, help="nombre de requêtes GET")
    g.add_argument("--seed", type=int, default=1)
    g.add_argument("--params", help='surcharges JSON, ex. \'{"product_alpha": 1.1}\'')
    g.set_defaults(fn=_cmd_gen)

    t = sub.add_parser("train-drl", help="entraîner l'éviction apprise (drl) sur une trace d'entraînement")
    t.add_argument("out", help="fichier JSON du modèle")
    t.add_argument("--trace", help="trace CSV ; sinon trace synthétique Magento 1")
    t.add_argument("-n", type=int, default=100_000)
    t.add_argument("--seed", type=int, default=1001, help="graine d'entraînement, distincte de celles d'évaluation")
    t.add_argument("--params", help="surcharges JSON du générateur")
    t.add_argument("--capacity", default="10%")
    t.add_argument("--sizes", choices=["bytes", "unit"], default="bytes")
    t.add_argument("-k", type=int, default=16)
    t.add_argument("--horizon", type=int, default=5000, help="requêtes regardées pour la récompense")
    t.add_argument("--epochs", type=int, default=8)
    t.set_defaults(fn=_cmd_train_drl)

    s = sub.add_parser("stats", help="statistiques d'une trace CSV")
    s.add_argument("trace")
    s.set_defaults(fn=_cmd_stats)

    l = sub.add_parser("list", help="lister les politiques disponibles")
    l.set_defaults(fn=_cmd_list)

    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
