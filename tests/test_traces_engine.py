from cachebench import EngineConfig, Request, get_policy, resolve_capacity, simulate, trace_stats
from cachebench.experiment import run, summarize
from cachebench.traces import PURGE, generate, read_csv, write_csv
from cachebench.traces.magento1 import NOT_CACHEABLE


def test_generator_is_deterministic():
    a = generate(n_requests=2000, seed=7)
    b = generate(n_requests=2000, seed=7)
    c = generate(n_requests=2000, seed=8)
    assert a == b
    assert a != c


def test_generator_shape():
    trace = generate(n_requests=5000, seed=1)
    gets = [r for r in trace if r.op != PURGE]
    assert len(gets) == 5000
    assert all(r.ts <= s.ts for r, s in zip(trace, trace[1:]))
    assert all(not r.cacheable for r in gets if r.kind in NOT_CACHEABLE)
    sizes = {}
    for r in gets:  # une page garde sa taille
        assert sizes.setdefault(r.key, r.size) == r.size
    kinds = {r.kind for r in gets}
    assert {"catalog_product_view", "catalog_category_view", "cms_index_index"} <= kinds
    assert any(r.op == PURGE for r in trace)


def test_csv_roundtrip(tmp_path):
    trace = generate(n_requests=500, seed=3)
    path = tmp_path / "t.csv"
    write_csv(trace, path)
    back = list(read_csv(path))
    assert [(r.key, r.size, r.op, r.tags, r.cacheable, r.text) for r in back] == \
           [(r.key, r.size, r.op, r.tags, r.cacheable, r.text) for r in trace]


def test_resolve_capacity():
    stats = trace_stats([Request(0, "a", size=600), Request(1, "b", size=400), Request(2, "a", size=600)])
    assert stats.unique_bytes == 1000
    assert resolve_capacity("10%", stats) == 100
    assert resolve_capacity("2KB", stats) == 2048
    assert resolve_capacity(512, stats) == 512


def test_latency_uses_hit_cost_and_miss_cost():
    trace = [Request(0, "a", cost_ms=100), Request(1, "a", cost_ms=100)]
    res = simulate(get_policy("lru")(10), trace, EngineConfig(warmup=0, hit_cost_ms=1))
    assert res["hit_rate"] == 0.5
    assert res["latency_mean_ms"] == 50.5


def test_experiment_runs_end_to_end():
    cfg = {"seeds": [1, 2], "cache_sizes": ["5%"],
           "traces": [{"name": "synth", "generator": "magento1", "params": {"n_requests": 3000}}],
           "policies": ["lru", {"name": "lfu", "label": "lfu-bis"}, "opt"]}
    rows = run(cfg, progress=lambda *_: None)
    assert len(rows) == 6
    summary = {s["policy"]: s for s in summarize(rows)}
    assert summary["opt"]["hit_rate"] >= summary["lru"]["hit_rate"]
    assert 0 < summary["lru"]["hit_rate"] < 1


def test_lazy_invalidation_turns_next_hit_into_miss():
    trace = [Request(0, "a", tags=("p1",)), Request(1, "a", tags=("p1",)),
             Request(2, "", tags=("p1",), op=PURGE),
             Request(3, "a", tags=("p1",)), Request(4, "a", tags=("p1",))]
    for mode in ("eager", "lazy"):
        res = simulate(get_policy("lru")(10), trace, EngineConfig(warmup=0, invalidation=mode))
        assert res["hit_rate"] == 0.5, mode
