"""Le module PHP doit donner les mêmes hits que Python, requête par requête.

Lancé seulement si `php` est installé. LeCaR et CACHEUS sont comparés au code officiel
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
]


@pytest.mark.parametrize("name,params,sizes,inv,min_agree", CASES,
                         ids=[f"{c[0]}-{c[2]}-{c[3]}" for c in CASES])
def test_same_hits(trace_file, name, params, sizes, inv, min_agree):
    if name in ("lecar", "cacheus") and not (vendor_dir() / "code" / "algs").is_dir():
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
