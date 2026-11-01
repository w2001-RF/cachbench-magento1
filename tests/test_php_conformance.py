"""Le module PHP doit donner les mêmes hits que Python, requête par requête.

Lancé seulement si `php` est installé. LeCaR, CACHEUS, ARC et LIRS sont comparés au code officiel
(il faut vendor/cacheus) ; un écart d'un ulp dans exp() de numpy pourrait en théorie les
faire diverger, d'où un seuil d'accord plutôt qu'une égalité stricte pour eux.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from cachebench.engine import EngineConfig, apply_size_mode, resolve_capacity, simulate, trace_stats
from cachebench.policies.base import get_policy
from cachebench.policies.official import vendor_dir
from cachebench.traces import generate, write_csv

ROOT = Path(__file__).resolve().parents[1]
PHP = shutil.which("php")
pytestmark = pytest.mark.skipif(PHP is None, reason="php absent")


@pytest.fixture(scope="module")
def trace_file(tmp_path_factory):
    trace = generate(n_requests=15000, seed=7)
    path = tmp_path_factory.mktemp("php") / "trace.csv"
    write_csv(trace, path)
    return trace, path


def php_replay(path, name, sizes, inv, params):
    cmd = [PHP, str(ROOT / "php/shell/aicache_replay.php"), "--trace", str(path), "--policy", name,
           "--capacity", "10%", "--sizes", sizes, "--invalidation", inv, "--hits"]
    for k, v in params.items():
        cmd += ["--param", f"{k}={v}"]
    return json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)


CASES = [
    ("lru", {}, "bytes", "eager", 1.0),
    ("fifo", {}, "bytes", "eager", 1.0),
    ("lfu", {}, "bytes", "eager", 1.0),
    ("drl", {"model": str(ROOT / "models/drl-bytes.json")}, "bytes", "eager", 1.0),
    ("semantic", {"threshold": 0.6}, "bytes", "eager", 1.0),
    ("lecar", {}, "unit", "lazy", 0.999),
    ("cacheus", {}, "unit", "lazy", 0.999),
    ("cacheus", {}, "unit", "eager", 0.999),
    ("arc", {}, "unit", "lazy", 1.0),
    ("arc", {}, "unit", "eager", 1.0),
    ("lirs", {}, "unit", "lazy", 1.0),
    ("lirs", {"hirs_ratio": 0.1}, "unit", "eager", 1.0),
    ("cacheus_pp", {"seed": 1}, "bytes", "eager", 1.0),
    ("cacheus_pp", {"seed": 3}, "unit", "lazy", 1.0),
    ("cacheus_pp2", {"seed": 1}, "bytes", "eager", 1.0),
    ("cacheus_pp2", {"seed": 3}, "unit", "lazy", 1.0),
    ("cacheus_pp2", {"seed": 2, "feedback": "regret", "selection": "argmax", "admission": "logistic",
                     "fix_versions": False, "rl": False}, "bytes", "eager", 1.0),
]


@pytest.mark.parametrize("name,params,sizes,inv,min_agree", CASES,
                         ids=[f"{c[0]}-{c[2]}-{c[3]}" for c in CASES])
def test_same_hits(trace_file, name, params, sizes, inv, min_agree):
    if name in ("lecar", "cacheus", "arc", "lirs") and not (vendor_dir() / "code" / "algs").is_dir():
        pytest.skip("code officiel absent (scripts/fetch_vendor.sh)")
    trace, path = trace_file
    cap = resolve_capacity("10%", trace_stats(apply_size_mode(trace, sizes)))
    hits: list[int] = []
    py = simulate(get_policy(name)(cap, **params), trace, EngineConfig(sizes=sizes, invalidation=inv), hits_out=hits)
    php = php_replay(path, name, sizes, inv, params)
    assert php["capacity"] == cap
    ref = "".join(map(str, hits))
    assert len(php["hits"]) == len(ref)
    agree = sum(a == b for a, b in zip(php["hits"], ref)) / len(ref)
    assert agree >= min_agree, f"{name} : {agree:.4%} d'accord"
    assert php["hit_rate"] == pytest.approx(py["hit_rate"], abs=1e-3)
    if name == "semantic":
        assert php["false_hit_rate"] == pytest.approx(py["false_hit_rate"], abs=1e-9)


def test_mersenne_twister_matches_numpy():
    out = json.loads(subprocess.run([PHP, str(ROOT / "tests/php/mt_check.php")], capture_output=True,
                                    text=True, check=True).stdout)
    rs = np.random.RandomState(123)
    expected = [rs.rand() for _ in range(5)]
    assert [float(x) for x in out[:5]] == expected
    np.random.seed(123)
    [np.random.rand() for _ in range(5)]
    choices = [0 if np.random.choice(["Increase", "Decrease"]) == "Increase" else 1 for _ in range(5)]
    assert out[5:] == choices


def test_pcg64_matches_numpy_default_rng():
    out = json.loads(subprocess.run([PHP, str(ROOT / "tests/php/pcg_check.php")], capture_output=True,
                                    text=True, check=True).stdout)
    for o in out:
        seed = o["seed"]
        assert o["words"] == np.random.SeedSequence(seed).generate_state(8).tolist()
        assert o["raw"] == [f"{int(x):016x}" for x in np.random.PCG64(seed).random_raw(4)]
        g = np.random.default_rng(seed)
        g.bit_generator.random_raw(4)
        assert [float(x) for x in o["random"]] == [g.random() for _ in range(4)]
        assert o["choice"] == [int(g.choice(3, p=np.array([0.2, 0.5, 0.3]))) for _ in range(20)]


def test_theta_state_product_matches_numpy():
    # CACHEUS++ calcule theta @ state ; numpy passe par le dgemv d'OpenBLAS, que PHP reproduit.
    rng = np.random.default_rng(0)
    theta = rng.uniform(-5, 5, (4000, 3, 5))
    state = np.column_stack([np.ones(4000), rng.random((4000, 4))])
    pairs = [[theta[i, e].tolist(), state[i].tolist()] for i in range(4000) for e in range(3)]
    out = json.loads(subprocess.run([PHP, str(ROOT / "tests/php/gemv_check.php")], input=json.dumps(pairs),
                                    capture_output=True, text=True, check=True).stdout)
    expected = [float(v) for i in range(4000) for v in theta[i] @ state[i]]
    agree = sum(float(a) == b for a, b in zip(out, expected)) / len(expected)
    assert agree >= 0.999, f"{agree:.4%}"


def test_rounding_matches_python_and_numpy():
    rng = np.random.default_rng(0)
    xs = list(rng.uniform(-1, 1, 3000)) + [0.0625, 0.1875, -0.0625, 0.0005, 0.0015, 0.5, 1.0, 0.0]
    xs += [k / 1000 + 0.0005 for k in range(0, 1000, 7)]
    out = json.loads(subprocess.run([PHP, str(ROOT / "tests/php/round_check.php")], input=json.dumps(xs),
                                    capture_output=True, text=True, check=True).stdout)
    for x, (py_r, np_r) in zip(xs, out):
        assert py_r == round(float(x), 3), x
        assert np_r == float(round(np.float64(x), 3)), x


def test_magento_backend_evicts_with_policy():
    script = ROOT / "tests/php/backend_smoke.php"
    out = subprocess.run([PHP, str(script)], capture_output=True, text=True, check=True).stdout.split()
    assert out == ["k4,k1,k6", "k1,k4,k6"]


def test_php_lint():
    files = sorted((ROOT / "php").rglob("*.php"))
    assert files
    for f in files:
        r = subprocess.run([PHP, "-l", str(f)], capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
