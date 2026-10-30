"""Rejoue une trace en requêtes HTTP sur une boutique Magento 1 locale et mesure les temps.

    python scripts/http_replay.py TRACE BASE_URL --out run.csv [-n 4000] [-c 4] [--products 1-10000]

Les URLs de la trace sont projetées sur la boutique : les pages produit (/product/<id>,
/catalog/product/view/id/<id>) sont classées par popularité et la k-ième plus demandée devient
le k-ième produit de --products (au-delà, on reboucle) ; le panier (/checkout/...) devient
/checkout/cart/ ; les autres chemins sont demandés tels quels. Chaque client garde ses
cookies, comme un visiteur. Écrit une ligne par requête : i, url, kind, status, ms.
"""
from __future__ import annotations

import argparse
import csv
import http.cookiejar
import json
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cachebench.traces import load_trace  # noqa: E402

PRODUCT = re.compile(r"^/(?:product|catalog/product/view/id)/(\d+)")


def build_urls(trace, base: str, first: int, last: int) -> list[tuple[str, str]]:
    gets = [r for r in trace if r.op == "get"]
    ids = [m.group(1) for m in map(PRODUCT.match, (r.key for r in gets)) if m]
    rank = {k: i for i, (k, _) in enumerate(Counter(ids).most_common())}
    n = last - first + 1
    out = []
    for r in gets:
        m = PRODUCT.match(r.key)
        if m:
            out.append((f"{base}/index.php/catalog/product/view/id/{first + rank[m.group(1)] % n}", "product"))
        elif r.key.startswith("/checkout"):
            out.append((f"{base}/index.php/checkout/cart/", "cart"))
        else:
            out.append((f"{base}/index.php{r.key}", r.kind or "page"))
    return out


def run(urls: list[tuple[str, str]], concurrency: int, timeout: float) -> list[tuple]:
    results: list[tuple | None] = [None] * len(urls)
    nxt = iter(range(len(urls)))
    lock = threading.Lock()

    def worker():
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        while True:
            with lock:
                i = next(nxt, None)
            if i is None:
                return
            url, kind = urls[i]
            t0 = time.perf_counter()
            try:
                with opener.open(url, timeout=timeout) as resp:
                    resp.read()
                    status = resp.status
            except urllib.error.HTTPError as e:
                status = e.code
            except Exception:  # noqa: BLE001 - délai dépassé, connexion refusée : noté, pas fatal
                status = 0
            results[i] = (i, url, kind, status, (time.perf_counter() - t0) * 1000)

    threads = [threading.Thread(target=worker) for _ in range(concurrency)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("trace")
    p.add_argument("base", help="ex. http://127.0.0.1/magento")
    p.add_argument("--out", required=True)
    p.add_argument("-n", type=int, help="nombre de requêtes rejouées (début de la trace)")
    p.add_argument("-c", "--concurrency", type=int, default=4)
    p.add_argument("--products", default="1-10000", help="ids de produits de la boutique, ex. 1-10000")
    p.add_argument("--timeout", type=float, default=120)
    a = p.parse_args()

    first, last = map(int, a.products.split("-"))
    urls = build_urls(load_trace(a.trace, max_requests=a.n), a.base.rstrip("/"), first, last)
    t0 = time.perf_counter()
    rows = run(urls, a.concurrency, a.timeout)
    wall = time.perf_counter() - t0
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["i", "url", "kind", "status", "ms"])
        w.writerows(rows)
    ok = sum(1 for r in rows if r[3] == 200)
    print(json.dumps({"requests": len(rows), "ok": ok, "wall_s": round(wall, 1),
                      "req_per_s": round(len(rows) / wall, 2)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
