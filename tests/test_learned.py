import json

import numpy as np
import pytest

from cachebench import EngineConfig, Request, get_policy, simulate
from cachebench.engine import apply_size_mode
from cachebench.ml import MLP
from cachebench.policies.drl import FEATURES, train
from cachebench.policies.semantic import embed
from cachebench.traces import generate


def test_mlp_json_roundtrip(tmp_path):
    rng = np.random.default_rng(0)
    X = rng.normal(size=(500, 4))
    y = X[:, 0] * 2 - X[:, 1]
    net = MLP([4, 8, 1], seed=1)
    losses = net.fit(X, y, epochs=40, batch=32, lr=1e-2)
    assert losses[-1] < 0.05 * float(np.var(y))
    net.save(tmp_path / "m.json", note="x")
    back, meta = MLP.load(tmp_path / "m.json")
    assert meta["note"] == "x"
    assert np.allclose(back.predict(X[:10]), net.predict(X[:10]))



def _gpu_or_skip():
    from cachebench.ml.device import get_xp
    try:
        get_xp("gpu")
    except RuntimeError as e:
        pytest.skip(str(e))


def test_mlp_device_choice():
    from cachebench.ml.device import get_xp
    assert get_xp("cpu")[0] is np
    assert get_xp("auto")[0] is not None          # GPU, ou repli sur numpy sans CuPy
    with pytest.raises(ValueError):
        get_xp("tpu")


def test_mlp_gpu_matches_cpu():
    _gpu_or_skip()
    rng = np.random.default_rng(0)
    X = rng.normal(size=(3000, 4))
    y = X[:, 0] * 2 - np.abs(X[:, 1])
    cpu, gpu = MLP([4, 16, 16, 1], seed=1), MLP([4, 16, 16, 1], seed=1)
    lc = cpu.fit(X, y, epochs=3, batch=64, seed=2)
    lg = gpu.fit(X, y, epochs=3, batch=64, seed=2, device="gpu")
    assert all(isinstance(W, np.ndarray) for W in gpu.W + gpu.b)   # ramenés de la carte : exportables
    assert np.allclose(lc, lg, rtol=1e-9)
    for a, b in zip(cpu.W + cpu.b, gpu.W + gpu.b):
        assert np.allclose(a, b, atol=1e-9)


def test_train_drl_on_gpu(tmp_path):
    _gpu_or_skip()
    trace = apply_size_mode(generate(n_requests=4000, seed=1001), "unit")
    info = train(trace, 150, tmp_path / "g.json", epochs=1, horizon=500, hidden=64, batch=1024,
                 device="gpu", log=lambda *_: None)
    net, meta = MLP.load(tmp_path / "g.json")
    assert meta["decisions"] == info["decisions"] > 0 and net.W[0].shape == (len(FEATURES), 64)

@pytest.fixture(scope="module")
def drl_model(tmp_path_factory):
    path = tmp_path_factory.mktemp("m") / "drl.json"
    trace = apply_size_mode(generate(n_requests=8000, seed=1001), "unit")
    info = train(trace, 200, path, epochs=2, horizon=1000, log=lambda *_: None)
    assert info["decisions"] > 0
    return path


def test_drl_needs_a_model():
    trace = apply_size_mode(generate(n_requests=2000, seed=1), "unit")
    with pytest.raises(RuntimeError, match="modèle"):
        simulate(get_policy("drl")(50), trace, EngineConfig(sizes="unit"))


def test_drl_model_is_exportable_and_runs(drl_model):
    d = json.loads(drl_model.read_text())
    assert d["features"] == FEATURES and d["k"] == 16
    trace = generate(n_requests=4000, seed=3)
    res = simulate(get_policy("drl")(200, model=str(drl_model)), trace,
                   EngineConfig(sizes="unit", check_invariants=True))
    assert 0 < res["hit_rate"] < 1


def test_embedding_absorbs_typos_and_word_order():
    a = embed("robe rouge")
    assert a @ embed("rouge robe") > 0.99
    assert a @ embed("rboe rouge") > 0.6
    assert a @ embed("valise cuir") < 0.2


def s(ts, text, intent):
    return Request(ts, f"/catalogsearch/result/?q={text}", tags=(f"intent_{intent}",), text=text)


def test_semantic_hit_and_false_hit_counting():
    p = get_policy("semantic")(100, threshold=0.8)
    assert p.access(s(0, "robe rouge", "a")) is False
    assert p.access(s(1, "rouge robe", "a")) is True        # même intention : bon hit
    assert p.approx_hits == 1 and p.false_hits == 0
    loose = get_policy("semantic")(100, threshold=0.3)
    loose.access(s(0, "robe rouge", "a"))
    assert loose.access(s(1, "robe noir", "b")) is True     # seuil trop bas : faux hit
    assert loose.false_hits == 1


def test_semantic_eviction_frees_vectors():
    p = get_policy("semantic")(2, threshold=0.9)
    p.access(s(0, "robe rouge", "a"))
    p.access(s(1, "valise cuir", "b"))
    p.access(s(2, "montre luxe", "c"))   # évince « robe rouge »
    assert p.access(s(3, "rouge robe", "a")) is False
    assert len(p._slot) == 2
