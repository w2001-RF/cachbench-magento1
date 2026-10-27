import random

import pytest

from cachebench import EngineConfig, Request, available, get_policy, simulate
from cachebench.traces import PURGE


def reqs(keys, size=1):
    return [Request(ts=i, key=str(k), size=size) for i, k in enumerate(keys)]


def play(name, keys, capacity):
    p = get_policy(name)(capacity)
    trace = reqs(keys)
    p.prepare(trace)
    return [p.access(r) for r in trace], p


def test_registry_lists_baselines():
    assert {"lru", "lfu", "fifo", "opt"} <= set(available())
    with pytest.raises(KeyError):
        get_policy("nexiste-pas")


def test_lru_sequence():
    hits, _ = play("lru", [1, 2, 1, 3, 2, 1], 2)
    # 1 m, 2 m, 1 h, 3 m (évince 2), 2 m (évince 1), 1 m
    assert hits == [False, False, True, False, False, False]


def test_fifo_ignores_hits():
    hits, _ = play("fifo", [1, 2, 1, 3, 1], 2)
    # 3 évince 1 (le plus ancien inséré) malgré le hit sur 1
    assert hits == [False, False, True, False, False]


def test_lfu_keeps_frequent():
    hits, _ = play("lfu", [1, 1, 1, 2, 3, 1], 2)
    assert hits[-1] is True


def test_opt_textbook():
    hits, _ = play("opt", [1, 2, 3, 1, 2, 3], 2)
    # Belady garde 1 et 2, n'admet pas 3 la première fois
    assert hits == [False, False, False, True, True, False]


def random_trace(n=4000, keys=300, seed=0, sizes=False):
    rnd = random.Random(seed)
    out = []
    for i in range(n):
        k = int(rnd.paretovariate(1.2)) % keys
        size = (k % 7 + 1) * 100 if sizes else 1
        out.append(Request(ts=i, key=f"k{k}", size=size, tags=(f"t{k % 10}",)))
        if sizes and i % 500 == 0:
            out.append(Request(ts=i, key="", size=0, tags=(f"t{rnd.randrange(10)}",), op=PURGE))
    return out


@pytest.mark.parametrize("name", ["lru", "lfu", "fifo", "opt"])
def test_capacity_never_exceeded(name):
    trace = random_trace(sizes=True)
    simulate(get_policy(name)(5000), trace, EngineConfig(check_invariants=True))


def test_opt_beats_online_policies_with_unit_sizes():
    trace = random_trace()
    rates = {n: simulate(get_policy(n)(50), trace, EngineConfig(warmup=0))["hit_rate"]
             for n in ["lru", "lfu", "fifo", "opt"]}
    assert rates["opt"] >= max(rates["lru"], rates["lfu"], rates["fifo"])


def test_invalidate_by_tag():
    p = get_policy("lru")(10)
    p.access(Request(0, "a", tags=("catalog_product_1",)))
    p.access(Request(1, "b", tags=("catalog_product_2",)))
    assert p.invalidate(["catalog_product_1"]) == 1
    assert "a" not in p and "b" in p
    assert p.used_bytes() == 1


def test_object_larger_than_cache_is_not_admitted():
    p = get_policy("lru")(10)
    assert p.access(Request(0, "big", size=11)) is False
    assert "big" not in p and p.used_bytes() == 0
