"""CACHEUS++ v2 : réglé comme l'original, il doit rendre exactement ses décisions."""
from __future__ import annotations

import pytest

from cachebench.engine import EngineConfig, apply_size_mode, resolve_capacity, simulate, trace_stats
from cachebench.policies import get_policy
from cachebench.policies.cacheus_pp2 import ORIGINAL, V2, CACHEUSPlusPlusV2
from cachebench.traces import generate


@pytest.fixture(scope="module")
def trace():
    return generate(n_requests=20000, seed=11)


def run(trace, name, sizes, inv, cap="5%", **params):
    c = resolve_capacity(cap, trace_stats(apply_size_mode(trace, sizes)))
    hits: list[int] = []
    p = get_policy(name)(c, **params)
    r = simulate(p, trace, EngineConfig(sizes=sizes, invalidation=inv), hits_out=hits)
    return hits, r, p


@pytest.mark.parametrize("sizes,inv", [("bytes", "eager"), ("unit", "lazy")])
def test_original_settings_reproduce_cacheus_pp(trace, sizes, inv):
    ref, _, _ = run(trace, "cacheus_pp", sizes, inv, seed=2)
    got, _, _ = run(trace, "cacheus_pp2", sizes, inv, seed=2, **ORIGINAL)
    assert got == ref


@pytest.mark.parametrize("change", [k for k in V2 if V2[k] != ORIGINAL[k]])
def test_each_change_alone_runs_within_capacity(trace, change):
    params = dict(ORIGINAL, **{change: V2[change]})
    _, r, p = run(trace, "cacheus_pp2", "bytes", "eager", seed=1, **params)
    assert 0 < r["hit_rate"] < 1
    assert p.used_bytes() <= p.capacity


def test_v2_defaults(trace):
    _, r, p = run(trace, "cacheus_pp2", "unit", "lazy", seed=1)
    assert p._alg.stats()["config"] == {k: V2[k] for k in V2}
    _, r_tlfu, _ = run(trace, "cacheus_pp2", "unit", "lazy", seed=1, admission="tinylfu")
    assert r_tlfu["hit_rate"] > 0


def test_aging_halves_counts():
    alg = CACHEUSPlusPlusV2(100, freq_window=1, min_history=4, seed=0)
    for k in "aaab":
        alg._observe_access(k)
    assert alg._freq == {"a": 1}   # 4 accès = fenêtre (1 × min_history) : a 3 -> 1, b 1 -> 0 (retiré)


def test_bad_parameters():
    for bad in ({"feedback": "x"}, {"selection": "x"}, {"admission": "x"}):
        with pytest.raises(ValueError):
            CACHEUSPlusPlusV2(100, **bad)
