"""Interface web : API JSON et tâches lancées en sous-processus."""
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import pytest

from cachebench.ui import make_server


@pytest.fixture()
def ui(tmp_path):
    (tmp_path / "experiments").mkdir()
    (tmp_path / "experiments" / "petit.yaml").write_text("name: petit\npolicies: [lru]\n", encoding="utf-8")
    server = make_server(tmp_path, port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    yield base, tmp_path
    server.shutdown()
    server.server_close()


def call(base, path, body=None, headers=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(base + path, data=data, headers={
        **({"Content-Type": "application/json"} if body is not None else {}), **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def wait(base, job, timeout=120):
    t0 = time.time()
    while time.time() - t0 < timeout:
        _, v = call(base, f"/api/jobs/{job['id']}")
        if v["status"] != "running":
            return v
        time.sleep(0.2)
    raise AssertionError("tâche trop longue")


def test_page_et_info(ui):
    base, _ = ui
    with urllib.request.urlopen(base + "/") as r:
        assert b"cachebench" in r.read()
    code, info = call(base, "/api/info")
    assert code == 200
    assert {"lru", "cacheus_pp", "opt"} <= set(info["policies"])
    assert "magento" in info["formats"]
    assert info["experiments"] == [{"path": "experiments/petit.yaml", "name": "petit"}]


def test_requetes_refusees(ui):
    base, _ = ui
    req = urllib.request.Request(base + "/api/jobs", data=b"{}", headers={"Content-Type": "text/plain"})
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req)
    assert e.value.code == 400                      # POST hors JSON : formulaire d'un autre site
    code, _ = call(base, "/api/info", headers={"Host": "attaquant.example"})
    assert code == 403                              # rebinding DNS
    code, err = call(base, "/api/jobs", {"kind": "gen", "out": "../hors-projet.csv"})
    assert code == 400 and "doivent rester" in err["error"]
    code, err = call(base, "/api/jobs", {"kind": "run", "config": {"name": "x", "traces": []}})
    assert code == 400


def test_generer_analyser_puis_comparer(ui):
    base, root = ui
    code, job = call(base, "/api/jobs", {"kind": "gen", "out": "traces/t.csv", "n": 2000, "seed": 3})
    assert code == 200, job
    v = wait(base, job)
    assert v["status"] == "done", v
    assert v["result"]["output"] == "traces/t.csv" and v["result"]["requests"] == 2000
    assert v["command"].startswith("cachebench gen-trace")

    _, job = call(base, "/api/jobs", {"kind": "stats", "trace": "traces/t.csv"})
    v = wait(base, job)
    assert v["status"] == "done" and v["result"]["format"] == "cachebench"

    cfg = {"name": "essai", "seeds": [1, 2], "traces": [{"name": "t", "path": "traces/t.csv"}],
           "cache_sizes": ["10%"], "engine": {"warmup": 0.1}, "policies": ["lru", {"name": "lfu", "label": "lfu-b"}]}
    _, job = call(base, "/api/jobs", {"kind": "run", "config": cfg})
    v = wait(base, job)
    assert v["status"] == "done", v
    rows = v["result"]["rows"]
    assert [r["policy"] for r in rows] == ["lru", "lfu-b"] and rows[0]["seeds"] == 2
    assert (root / "results" / "essai_summary.csv").is_file()

    _, results = call(base, "/api/results")
    assert [r["path"] for r in results] == ["results/essai_summary.csv"]
    _, res = call(base, "/api/result?path=results/essai_summary.csv")
    assert 0 < res["rows"][0]["hit_rate"] <= 1


def test_annuler(ui):
    base, _ = ui
    _, job = call(base, "/api/jobs", {"kind": "gen", "out": "traces/long.csv", "n": 3_000_000})
    _, v = call(base, f"/api/jobs/{job['id']}/cancel", {})
    assert wait(base, job)["status"] == "cancelled"


def test_yaml_aller_retour_et_enregistrement(ui):
    base, root = ui
    cfg = {"name": "exp", "traces": [{"generator": "magento1"}], "cache_sizes": ["5%"], "policies": ["lru"]}
    _, y = call(base, "/api/yaml", {"config": cfg})
    _, back = call(base, "/api/parse", {"yaml": y["yaml"]})
    assert back["config"] == cfg
    _, saved = call(base, "/api/experiment/save", {"config": cfg})
    assert saved["path"] == "experiments/exp.yaml" and (root / "experiments" / "exp.yaml").is_file()


def test_resume_http_et_config_magento(ui):
    base, root = ui
    (root / "results").mkdir()
    (root / "results" / "a.http.csv").write_text(
        "i,url,kind,status,ms\n0,u,product,200,100\n1,u,product,200,300\n2,u,cart,0,50\n", encoding="utf-8")
    _, res = call(base, "/api/result?path=results/a.http.csv")
    assert res["overall"]["requests"] == 3 and res["overall"]["failed"] == 1
    product = next(k for k in res["by_kind"] if k["kind"] == "product")
    assert product["mean_ms"] == 200 and product["p50_ms"] == 200

    etc = root / "mage" / "app" / "etc"
    etc.mkdir(parents=True)
    (etc / "local.xml").write_text(
        "<config><global><cache><backend>Aicache_Benchmark_Model_Backend</backend><backend_options>"
        "<inner_backend>Cm_Cache_Backend_Redis</inner_backend><policy>cacheus_pp</policy>"
        "<capacity>8388608</capacity><params><seed>2</seed></params></backend_options></cache></global></config>",
        encoding="utf-8")
    _, c = call(base, "/api/magento?root=" + urllib.parse.quote(str(root / "mage")))
    assert c["policy"] == "cacheus_pp" and c["capacity"] == "8388608" and c["params"] == {"seed": "2"}
