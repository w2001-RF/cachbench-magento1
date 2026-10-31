"""Ligne de commande : cachebench run | gen-trace | train-drl | convert | stats | list | ui."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from . import experiment
from .engine import trace_stats
from .ml.device import DEVICES
from .policies import available
from .traces import FORMATS, detect, load_trace, write_csv
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
        trace = load_trace(a.trace)
        source = a.trace
    else:
        overrides = json.loads(a.params) if a.params else {}
        trace = generate(Magento1Config(n_requests=a.n, seed=a.seed), **overrides)
        source = f"magento1 seed={a.seed} n={a.n}"
    trace = apply_size_mode(trace, a.sizes)
    capacity = resolve_capacity(a.capacity, trace_stats(trace))
    info = train(trace, capacity, a.out, k=a.k, horizon=a.horizon, epochs=a.epochs, seed=a.seed,
                 hidden=a.hidden, batch=a.batch, device=a.device,
                 meta={"sizes": a.sizes, "trained_on": source, "capacity_spec": a.capacity})
    print(f"Modèle écrit dans {a.out} : {json.dumps(info)}")
    return 0


def _cmd_stats(a) -> int:
    trace = load_trace(a.trace, format=a.format, max_requests=a.n)
    print(json.dumps({"format": a.format or detect(a.trace), **asdict(trace_stats(trace))}, indent=2))
    return 0


def _cmd_convert(a) -> int:
    trace = load_trace(a.trace, format=a.format, max_requests=a.n)
    n = write_csv(trace, a.out)
    print(f"{n} événements ({a.format or detect(a.trace)}) écrits dans {a.out}")
    return 0


def _cmd_list(_a) -> int:
    print("\n".join(available()))
    return 0


def _cmd_ui(a) -> int:
    from .ui import serve
    serve(a.root, a.port, open_browser=not a.no_browser)
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
    t.add_argument("--trace", help="trace sur fichier (tout format) ; sinon trace synthétique Magento 1")
    t.add_argument("-n", type=int, default=100_000)
    t.add_argument("--seed", type=int, default=1001, help="graine d'entraînement, distincte de celles d'évaluation")
    t.add_argument("--params", help="surcharges JSON du générateur")
    t.add_argument("--capacity", default="10%")
    t.add_argument("--sizes", choices=["bytes", "unit"], default="bytes")
    t.add_argument("-k", type=int, default=16)
    t.add_argument("--horizon", type=int, default=5000, help="requêtes regardées pour la récompense")
    t.add_argument("--epochs", type=int, default=8)
    t.add_argument("--hidden", type=int, default=32,
                   help="neurones par couche cachée ; le module PHP évalue ce réseau à chaque éviction")
    t.add_argument("--batch", type=int, default=512, help="candidats par pas d'Adam")
    t.add_argument("--device", choices=DEVICES, default="cpu",
                   help="cpu (numpy), gpu (CuPy, carte NVIDIA) ou auto (GPU s'il est disponible)")
    t.set_defaults(fn=_cmd_train_drl)

    s = sub.add_parser("stats", help="statistiques d'une trace (format commun ou externe)")
    s.add_argument("trace")
    s.add_argument("--format", choices=FORMATS, help="détecté d'après le fichier si absent")
    s.add_argument("-n", type=int, help="ne lire que les n premières requêtes")
    s.set_defaults(fn=_cmd_stats)

    c = sub.add_parser("convert", help="convertir une trace externe au format CSV commun")
    c.add_argument("trace")
    c.add_argument("out")
    c.add_argument("--format", choices=FORMATS, help="détecté d'après le fichier si absent")
    c.add_argument("-n", type=int, help="ne lire que les n premières requêtes")
    c.set_defaults(fn=_cmd_convert)

    l = sub.add_parser("list", help="lister les politiques disponibles")
    l.set_defaults(fn=_cmd_list)

    u = sub.add_parser("ui", help="ouvrir l'interface web locale (expériences, traces, résultats, test Magento)")
    u.add_argument("--port", type=int, default=8765)
    u.add_argument("--root", default=".", help="dossier du projet (experiments/, results/, traces/)")
    u.add_argument("--no-browser", action="store_true", help="ne pas ouvrir le navigateur")
    u.set_defaults(fn=_cmd_ui)

    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
