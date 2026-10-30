import pytest

from cachebench import EngineConfig, Request, available, get_policy, simulate
from cachebench.engine import apply_size_mode
from cachebench.traces import generate


@pytest.fixture(scope="module")
def trace():
    return generate(n_requests=6000, seed=2)


def test_registered():
    assert "cacheus_pp" in available()


@pytest.mark.parametrize("sizes,invalidation", [("bytes", "eager"), ("unit", "lazy"), ("unit", "eager")])
def test_runs_and_respects_capacity(trace, sizes, invalidation):
    cfg = EngineConfig(sizes=sizes, invalidation=invalidation, warmup=0)
    capacity = 200 if sizes == "unit" else 2_000_000
    res = simulate(get_policy("cacheus_pp")(capacity, seed=1), trace, cfg)
    assert 0 < res["hit_rate"] < 1


def test_never_beats_opt(trace):
    cfg = EngineConfig(sizes="unit", invalidation="lazy", warmup=0)
    opt = simulate(get_policy("opt")(200), trace, cfg)["hit_rate"]
    assert simulate(get_policy("cacheus_pp")(200, seed=1), trace, cfg)["hit_rate"] <= opt


def test_same_seed_same_result(trace):
    cfg = EngineConfig(sizes="unit", warmup=0)
    unit = apply_size_mode(trace, "unit")
    runs = [simulate(get_policy("cacheus_pp")(200, seed=7), unit, cfg)["hit_rate"] for _ in range(2)]
    assert runs[0] == runs[1]


def test_purge_removes_entry():
    p = get_policy("cacheus_pp")(100)
    assert p.access(Request(0, "a", tags=("catalog_product_1",))) is False
    assert p.access(Request(1, "a", tags=("catalog_product_1",))) is True
    assert p.invalidate(["catalog_product_1"]) == 1
    assert "a" not in p and p.used_bytes() == 0
    assert p.access(Request(2, "a", tags=("catalog_product_1",))) is False


def test_size_change_is_a_miss():
    p = get_policy("cacheus_pp")(1000)
    p.access(Request(0, "a", size=50))
    assert p.access(Request(1, "a", size=60)) is False
    assert p.used_bytes() == 60
