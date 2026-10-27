"""Exécution d'une expérience décrite en YAML : politiques × traces × tailles × graines."""
from __future__ import annotations

import csv
import statistics
from pathlib import Path
from typing import Any

import yaml

from .engine import EngineConfig, apply_size_mode, resolve_capacity, simulate, trace_stats
from .policies import get_policy
from .traces import Magento1Config, generate, read_csv

GENERATORS = {"magento1": (Magento1Config, generate)}


def load(path: str | Path) -> dict:
    with Path(path).open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _policy_specs(cfg: dict) -> list[tuple[str, str, dict]]:
    """Accepte « lru » ou {name: lecar, label: lecar-lr0.1, params: {...}}."""
    specs = []
    for item in cfg["policies"]:
        if isinstance(item, str):
            specs.append((item, item, {}))
        else:
            name = item["name"]
            specs.append((name, item.get("label", name), item.get("params", {}) or {}))
    return specs


def _load_trace(spec: dict, seed: int):
    if "path" in spec:
        return list(read_csv(spec["path"]))
    gen = spec.get("generator")
    if gen not in GENERATORS:
        raise ValueError(f"générateur inconnu : {gen} (disponibles : {', '.join(GENERATORS)})")
    _, fn = GENERATORS[gen]
    return fn(**{**(spec.get("params") or {}), "seed": seed})


def run(cfg: dict, progress=print) -> list[dict[str, Any]]:
    engine = EngineConfig(**(cfg.get("engine") or {}))
    seeds = cfg.get("seeds") or [1]
    rows: list[dict[str, Any]] = []
    for tspec in cfg["traces"]:
        tname = tspec.get("name") or tspec.get("path") or tspec.get("generator")
        # Une trace sur fichier est la même pour toutes les graines : on la lit une fois.
        file_trace = _load_trace(tspec, seeds[0]) if "path" in tspec else None
        for seed in seeds:
            trace = file_trace if file_trace is not None else _load_trace(tspec, seed)
            trace = apply_size_mode(trace, engine.sizes)
            stats = trace_stats(trace)
            for size_spec in cfg["cache_sizes"]:
                capacity = resolve_capacity(size_spec, stats)
                for name, label, params in _policy_specs(cfg):
                    policy = get_policy(name)(capacity, seed=seed, **params)
                    res = simulate(policy, trace, engine)
                    row = {"trace": tname, "seed": seed, "cache_size": str(size_spec),
                           "capacity_bytes": capacity, "policy": label, **res}
                    rows.append(row)
                    progress(f"{tname:<16} seed={seed:<3} size={str(size_spec):<6} {label:<14} "
                             f"hit={res['hit_rate']:.4f} p95={res['latency_p95_ms']:.1f}ms "
                             f"overhead={res['overhead_us']:.2f}µs")
    return rows


def save(rows: list[dict], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        fields = list(dict.fromkeys(k for r in rows for k in r))
        w = csv.DictWriter(f, fieldnames=fields, restval="")
        w.writeheader()
        w.writerows(rows)


METRICS = ["hit_rate", "byte_hit_rate", "latency_mean_ms", "latency_p95_ms",
           "latency_p99_ms", "overhead_us", "false_hit_rate"]


def summarize(rows: list[dict]) -> list[dict]:
    """Moyenne et écart-type par (trace, taille, politique), sur les graines."""
    groups: dict[tuple, list[dict]] = {}
    for r in rows:
        groups.setdefault((r["trace"], r["cache_size"], r["policy"]), []).append(r)
    out = []
    for (trace, size, policy), rs in groups.items():
        s = {"trace": trace, "cache_size": size, "policy": policy, "seeds": len(rs)}
        for m in METRICS:
            vals = [r[m] for r in rs]
            s[m] = statistics.fmean(vals)
            s[m + "_std"] = statistics.stdev(vals) if len(vals) > 1 else 0.0
        out.append(s)
    return out


def format_summary(summary: list[dict]) -> str:
    lines = [f"{'trace':<16} {'taille':<7} {'politique':<14} {'hit rate':>16} "
             f"{'latence moy.':>13} {'p95':>9} {'p99':>9} {'surcoût':>10}"]
    for s in summary:
        lines.append(
            f"{s['trace']:<16} {s['cache_size']:<7} {s['policy']:<14} "
            f"{s['hit_rate']:>8.4f} ±{s['hit_rate_std']:.4f} "
            f"{s['latency_mean_ms']:>10.1f} ms {s['latency_p95_ms']:>6.0f} ms {s['latency_p99_ms']:>6.0f} ms "
            f"{s['overhead_us']:>7.2f} µs"
            + (f"  faux hits {s['false_hit_rate']:.4f}" if s["false_hit_rate"] else ""))
    return "\n".join(lines)

