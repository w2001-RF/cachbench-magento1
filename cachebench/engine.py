"""Moteur de simulation : rejoue une trace dans une politique et mesure."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, replace
from typing import Sequence

import numpy as np

from .policies.base import CachePolicy
from .traces.request import GET, PURGE, Request


@dataclass
class EngineConfig:
    warmup: float = 0.1          # part des requêtes GET exclue des mesures (le cache se remplit)
    hit_cost_ms: float = 0.5     # coût d'un hit ; hypothèse à calibrer sur Magento
    check_invariants: bool = True
    sizes: str = "bytes"         # "unit" : chaque objet pèse 1, la capacité devient un nombre d'objets
    # "eager" : la purge retire l'entrée du cache (policy.invalidate).
    # "lazy"  : l'entrée reste, mais la requête suivante sur cette clé est un miss. Seul mode
    #           possible pour le code officiel de cacheus ; à utiliser pour comparer avec lui.
    invalidation: str = "eager"


def apply_size_mode(trace: Sequence[Request], mode: str) -> list[Request]:
    if mode == "bytes":
        return list(trace)
    if mode == "unit":
        return [r if r.op == PURGE or r.size == 1 else replace(r, size=1) for r in trace]
    raise ValueError(f"mode de taille inconnu : {mode!r} (bytes ou unit)")


@dataclass
class TraceStats:
    requests: int
    cacheable: int
    purges: int
    unique_keys: int
    unique_bytes: int


def trace_stats(trace: Sequence[Request]) -> TraceStats:
    sizes: dict[str, int] = {}
    gets = cacheable = purges = 0
    for r in trace:
        if r.op == PURGE:
            purges += 1
            continue
        gets += 1
        if r.cacheable:
            cacheable += 1
            sizes[r.key] = max(r.size, sizes.get(r.key, 0))
    return TraceStats(gets, cacheable, purges, len(sizes), sum(sizes.values()))


_PCT = re.compile(r"^\s*([0-9.]+)\s*%\s*$")
_UNITS = {"b": 1, "kb": 1024, "mb": 1024**2, "gb": 1024**3}


def resolve_capacity(spec: int | float | str, stats: TraceStats) -> int:
    """« 5% » = 5 % du volume unique cachable de la trace ; « 64MB » ; ou un entier en octets."""
    if isinstance(spec, (int, float)):
        return max(1, int(spec))
    m = _PCT.match(spec)
    if m:
        return max(1, int(stats.unique_bytes * float(m.group(1)) / 100))
    m = re.match(r"^\s*([0-9.]+)\s*([a-zA-Z]+)\s*$", spec)
    if m and m.group(2).lower() in _UNITS:
        return max(1, int(float(m.group(1)) * _UNITS[m.group(2).lower()]))
    raise ValueError(f"taille de cache illisible : {spec!r}")


def simulate(policy: CachePolicy, trace: Sequence[Request], cfg: EngineConfig | None = None,
             hits_out: list | None = None) -> dict:
    """hits_out, si fourni, reçoit 1/0 pour chaque requête jouée (sert au test de conformité PHP)."""
    cfg = cfg or EngineConfig()
    trace = apply_size_mode(trace, cfg.sizes)
    played = [r for r in trace if r.op == GET and r.cacheable]
    policy.prepare(played)

    n_gets = sum(1 for r in trace if r.op == GET)
    warm_until = int(n_gets * cfg.warmup)

    latencies: list[float] = []
    overhead_ns = 0
    hits = measured = 0
    bytes_hit = bytes_total = 0
    seen = 0
    lazy = cfg.invalidation == "lazy"
    if cfg.invalidation not in ("eager", "lazy"):
        raise ValueError(f"mode d'invalidation inconnu : {cfg.invalidation!r} (eager ou lazy)")
    by_tag: dict[str, set[str]] = {}
    stale: set[str] = set()

    for r in trace:
        if r.op == PURGE:
            if lazy:
                for t in r.tags:
                    stale |= by_tag.pop(t, set())
            else:
                policy.invalidate(r.tags)
            continue
        seen += 1
        measuring = seen > warm_until
        if not r.cacheable:
            if measuring:
                latencies.append(r.cost_ms)
            continue
        policy.measuring = measuring
        t0 = time.perf_counter_ns()
        hit = policy.access(r)
        dt = time.perf_counter_ns() - t0
        if lazy:
            if r.key in stale:
                hit = False
                stale.discard(r.key)
            for t in r.tags:
                by_tag.setdefault(t, set()).add(r.key)
        if cfg.check_invariants and policy.used_bytes() > policy.capacity:
            raise AssertionError(
                f"{policy.name} dépasse sa capacité : {policy.used_bytes()} > {policy.capacity}")
        if hits_out is not None:
            hits_out.append(1 if hit else 0)
        if not measuring:
            continue
        measured += 1
        overhead_ns += dt
        bytes_total += r.size
        if hit:
            hits += 1
            bytes_hit += r.size
            latencies.append(cfg.hit_cost_ms)
        else:
            latencies.append(r.cost_ms)

    lat = np.asarray(latencies) if latencies else np.zeros(1)
    return {
        "requests": measured,
        "hit_rate": hits / measured if measured else 0.0,
        "byte_hit_rate": bytes_hit / bytes_total if bytes_total else 0.0,
        "latency_mean_ms": float(lat.mean()),
        "latency_p50_ms": float(np.percentile(lat, 50)),
        "latency_p95_ms": float(np.percentile(lat, 95)),
        "latency_p99_ms": float(np.percentile(lat, 99)),
        "overhead_us": overhead_ns / measured / 1000 if measured else 0.0,
        "evictions": policy.evictions,
        # Piste sémantique : hits servis par une page « proche », et ceux qui étaient faux.
        "approx_hit_rate": getattr(policy, "approx_hits", 0) / measured if measured else 0.0,
        "false_hit_rate": getattr(policy, "false_hits", 0) / measured if measured else 0.0,
    }
