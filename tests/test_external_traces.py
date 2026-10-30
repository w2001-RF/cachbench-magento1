import gzip
import struct

import pytest

from cachebench import experiment
from cachebench.traces import detect, load_trace, write_csv
from cachebench.traces.magento1 import CART, PRODUCT, Magento1Config

FILES = {
    "magento.csv": "timestamp,url,size,category\n"
                   "1575158400.0,/product/1,47677,product\n"
                   "1575158401.0,/checkout/cart/add/1,3420,api\n"
                   "1575158402.0,/product/1,47677,product\n",
    "twitter.csv": "0,key:a,5,100,1,get,0\n"
                   "1,key:a,5,100,1,get,0\n"
                   "2,key:b,5,0,1,get,0\n"
                   "3,key:b,5,50,1,set,0\n"
                   "4,key:b,5,0,1,get,0\n",
    "libcachesim.csv": "# time, object, size, next_access_vtime\n0, 11, 737, 2\n1, 12, 248, -1\n2, 11, 737, -1\n",
    "access.log": '1.2.3.4 - - [01/Jul/1995:00:00:01 -0400] "GET /catalog/product/view/id/5 HTTP/1.0" 200 6245\n'
                  '1.2.3.4 - - [01/Jul/1995:00:00:06 -0400] "GET / HTTP/1.0" 200 3985\n',
}


@pytest.fixture
def folder(tmp_path):
    for name, text in FILES.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    with gzip.open(tmp_path / "rees46.csv.gz", "wt", encoding="utf-8") as f:
        f.write("event_time,event_type,product_id,category_id,category_code,brand,price,user_id,user_session\n"
                "2019-12-01 00:00:00 UTC,view,1005105,1,,apple,1302.48,5,s\n"
                "2019-12-01 00:00:03 UTC,cart,1005105,1,,apple,1302.48,5,s\n")
    rec = struct.Struct("<IQIq")
    (tmp_path / "cloud.oracleGeneral.bin").write_bytes(
        rec.pack(10, 7, 512, 1) + rec.pack(11, 8, 512, -1) + rec.pack(12, 7, 512, -1))
    return tmp_path


@pytest.mark.parametrize("name,fmt,n", [
    ("magento.csv", "magento", 3), ("twitter.csv", "twitter", 3), ("libcachesim.csv", "libcachesim", 3),
    ("access.log", "access_log", 2), ("rees46.csv.gz", "rees46", 2),
    ("cloud.oracleGeneral.bin", "libcachesim", 3),
])
def test_detect_and_load(folder, name, fmt, n):
    assert detect(folder / name) == fmt
    trace = load_trace(folder / name)
    assert len(trace) == n
    assert trace[0].ts == 0 and all(r.size > 0 for r in trace)


def test_magento_categories_become_routes(folder):
    product, cart, _ = load_trace(folder / "magento.csv")
    median = {k: m for k, (m, _) in Magento1Config().costs.items()}
    assert (product.kind, product.cacheable, product.cost_ms) == (PRODUCT, True, median[PRODUCT])
    assert (cart.kind, cart.cacheable, cart.ts) == (CART, False, 1.0)


def test_overrides(folder):
    trace = load_trace(folder / "magento.csv", costs={"api": 90, "product": 10}, uncacheable=[],
                       max_requests=2)
    assert [(r.cost_ms, r.cacheable) for r in trace] == [(10, True), (90, True)]


def test_key_keeps_its_first_size(tmp_path):
    f = tmp_path / "m.csv"
    f.write_text("timestamp,url,size,category\n0,/product/1,500,product\n1,/product/1,700,product\n",
                 encoding="utf-8")
    assert [r.size for r in load_trace(f)] == [500, 500]
    assert [r.size for r in load_trace(f, stable_sizes=False)] == [500, 700]


def test_twitter_gets_take_size_from_writes(folder):
    sizes = [(r.key, r.size) for r in load_trace(folder / "twitter.csv")]
    assert sizes == [("key:a", 105), ("key:a", 105), ("key:b", 55)]


def test_common_csv_round_trip(folder, tmp_path):
    out = tmp_path / "out" / "common.csv"
    write_csv(load_trace(folder / "magento.csv"), out)
    assert detect(out) == "cachebench"
    assert load_trace(out) == load_trace(folder / "magento.csv")


def test_missing_file_is_an_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_trace(tmp_path / "absent.csv", format="magento")


def test_experiment_expands_glob_and_folder(folder):
    cfg = {"traces": [{"name": "m", "path": str(folder / "*.csv")}],
           "cache_sizes": ["50%"], "policies": ["lru"], "engine": {"warmup": 0}}
    names = {r["trace"] for r in experiment.run(cfg, progress=lambda *_: None)}
    assert names == {"m-magento", "m-twitter", "m-libcachesim"}
    assert len(experiment._expand_traces([{"path": str(folder)}])) == 6
