import pytest

from cachebench import EngineConfig, Request, get_policy, simulate
from cachebench.engine import apply_size_mode
from cachebench.policies.official import vendor_dir
from cachebench.traces import PURGE, generate

pytestmark = pytest.mark.skipif(not (vendor_dir() / "code" / "algs").is_dir(),
                                reason="code officiel absent : lancer scripts/fetch_vendor.sh")

OFFICIAL = ["cacheus", "lecar", "arc", "lirs"]
UNIT = EngineConfig(sizes="unit", warmup=0)


@pytest.fixture(scope="module")
def trace():
    return apply_size_mode(generate(n_requests=6000, seed=2), "unit")


@pytest.mark.parametrize("name", OFFICIAL)
def test_runs_and_respects_capacity(name, trace):
    res = simulate(get_policy(name)(200), trace, UNIT)
    assert 0 < res["hit_rate"] < 1


@pytest.mark.parametrize("name", OFFICIAL)
def test_resident_set_matches_official_state(name, trace):
    p = get_policy(name)(150)
    played = [r for r in trace if r.op != PURGE and r.cacheable]
    p.prepare(played)
    seen = set()
    for i, r in enumerate(played):
        p.access(r)
        seen.add(r.key)
        if i % 500 == 0:
            assert p._resident == {k for k in seen if k in p._alg}
    assert p.used_bytes() <= 150


@pytest.mark.parametrize("name", OFFICIAL)
def test_never_beats_opt(name, trace):
    opt = simulate(get_policy("opt")(200), trace, UNIT)["hit_rate"]
    assert simulate(get_policy(name)(200), trace, UNIT)["hit_rate"] <= opt


def test_requires_unit_sizes():
    p = get_policy("cacheus")(100)
    with pytest.raises(ValueError, match="sizes: unit"):
        p.access(Request(0, "a", size=500))


def test_purge_makes_next_access_a_miss():
    p = get_policy("lecar")(10)
    p.prepare([])
    assert p.access(Request(0, "a", tags=("catalog_product_1",))) is False
    assert p.access(Request(1, "a", tags=("catalog_product_1",))) is True
    assert p.invalidate(["catalog_product_1"]) == 1
    assert "a" not in p
    assert p.access(Request(2, "a", tags=("catalog_product_1",))) is False
    assert p.access(Request(3, "a", tags=("catalog_product_1",))) is True
