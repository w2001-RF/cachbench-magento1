"""Test de charge d'une boutique Magento 1 : trouve combien de visiteurs simultanés elle tient.

    python scripts/magento_load_test.py                               # paliers par défaut, 1 min chacun
    python scripts/magento_load_test.py --users 10,50,100,200 --step 120
    python scripts/magento_load_test.py --users 5,10,20,40 --think 0  # débit maximal, sans pause

Des visiteurs virtuels parcourent la boutique comme de vrais clients, chacun avec ses
cookies : page d'arrivée, catégories (pages suivantes, tris), recherche, fiches produit
(produits populaires plus souvent, loi de Zipf), ajout au panier, panier, connexion avec un
des comptes de data/magento_customers.csv (scripts/magento_seed_customers.py), espace
client, page de commande, déconnexion. Entre deux pages, chaque visiteur marque une pause
(--think), comme un humain qui lit. Aucune commande n'est passée.

Le nombre de visiteurs monte par paliers (--users), chacun tenu --step secondes. Pour chaque
palier : requêtes par seconde, temps de réponse (médiane, p95, p99), taux d'erreur, et, si
--apache-log est lisible, plantages d'Apache. Un palier « tient » si le taux d'erreur reste
sous --max-error et le p95 sous --max-p95 ; la limite est le dernier palier qui tient. Le test
s'arrête au premier palier qui ne tient pas (sauf --no-stop).

Seules les pages HTML sont demandées, pas les images, CSS et JS (servis par Apache sans PHP).
Résultats dans --out : requests.csv (une ligne par requête), steps.csv, summary.json, report.md.
Ctrl+C arrête le test proprement et écrit le rapport des paliers déjà faits.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import http.cookiejar
import json
import random
import re
import statistics
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ERROR_MARKERS = ("There has been an error processing your request", "Fatal error</b>", "Service Temporarily Unavailable")
SEARCH_WORDS = ["product", "test", "test product", "drill", "camera", "shirt", "sofa", "laptop", "phone", "kids",
                "audio", "sport", "shoes", "watch", "bag", "lamp", "chair", "tv", "headphones", "toy"]


# --- boutique ---------------------------------------------------------------------------------

class Shop:
    """Adresses de la boutique, découvertes une fois au départ."""

    def __init__(self, base: str, products: tuple[int, int], zipf: float, seed: int, timeout: float):
        self.base = base.rstrip("/")
        self.root = self.base + "/index.php"
        self.timeout = timeout
        first, last = products
        ids = list(range(first, last + 1))
        random.Random(seed).shuffle(ids)                      # rang de popularité -> id de produit
        self.product_ids = ids
        weights = [1 / (r + 1) ** zipf for r in range(len(ids))]
        total = sum(weights)
        acc, self.cum = 0.0, []
        for w in weights:
            acc += w / total
            self.cum.append(acc)
        self.categories: list[str] = []

    def product(self, rng: random.Random) -> int:
        return self.product_ids[min(bisect.bisect_left(self.cum, rng.random()), len(self.product_ids) - 1)]

    def discover_categories(self) -> list[str]:
        def links(url: str, pattern: str) -> list[str]:
            with urllib.request.urlopen(url, timeout=self.timeout) as r:
                html = r.read().decode("utf-8", "replace")
            return sorted({m.split("?")[0] for m in re.findall(pattern, html)})
        root = re.escape(self.root)
        top = links(self.root + "/", rf'href="({root}/[a-z0-9-]+\.html[^"]*)"')
        cats = list(top)
        for t in top:
            slug = re.escape(t[len(self.root) + 1:-5])
            try:
                cats += links(t, rf'href="({root}/{slug}/[a-z0-9-]+\.html[^"]*)"')
            except Exception:  # noqa: BLE001 - une catégorie illisible n'empêche pas le test
                pass
        self.categories = sorted(set(cats))
        return self.categories


# --- visiteur virtuel ----------------------------------------------------------------------------

class Recorder:
    def __init__(self):
        self.rows: list[tuple] = []           # (début, fin, palier, visiteur, page, statut, ms, octets, erreur)
        self.lock = threading.Lock()
        self.step = 0

    def add(self, *row):
        with self.lock:
            self.rows.append(row)


class User(threading.Thread):
    def __init__(self, uid: int, shop: Shop, rec: Recorder, accounts: list[dict], args, stop: threading.Event):
        super().__init__(daemon=True)
        self.uid, self.shop, self.rec, self.accounts, self.a, self.stop = uid, shop, rec, accounts, args, stop
        self.rng = random.Random(args.seed * 100_003 + uid)

    # une requête mesurée ; renvoie (corps, url finale) ou (None, None) en cas d'erreur
    def hit(self, page: str, url: str, data: dict | None = None):
        body = urllib.parse.urlencode(data).encode() if data else None
        t0 = time.time()
        status, size, err, html, final = 0, 0, "", None, None
        try:
            with self.opener.open(url, body, timeout=self.a.timeout) as r:
                raw = r.read()
                status, size, final = r.status, len(raw), r.geturl()
                html = raw.decode("utf-8", "replace")
                if any(m in html for m in ERROR_MARKERS):
                    err = "page d'erreur Magento"
        except urllib.error.HTTPError as e:
            status, err = e.code, f"HTTP {e.code}"
        except Exception as e:  # noqa: BLE001 - délai dépassé, connexion refusée ou coupée
            err = type(e).__name__
        t1 = time.time()
        self.rec.add(t0, t1, self.rec.step, self.uid, page, status, round((t1 - t0) * 1000, 1), size, err)
        return (None, None) if err else (html, final)

    def think(self) -> bool:
        lo, hi = self.a.think
        return not self.stop.wait(self.rng.uniform(lo, hi) if hi > 0 else 0)

    @staticmethod
    def form_key(html: str | None) -> str | None:
        m = html and re.search(r'name="form_key" type="hidden" value="([^"]+)"', html)
        return m.group(1) if m else None

    def session(self):
        rng, shop, root = self.rng, self.shop, self.shop.root
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        logged = False
        steps = []
        # arrivée
        land = rng.random()
        if land < 0.5 or not shop.categories:
            steps.append(("home", lambda: self.hit("home", root + "/")))
        elif land < 0.8:
            steps.append(("category", self.category))
        else:
            steps.append(("product", self.product_view))
        if rng.random() < self.a.login_rate and self.accounts:
            steps.append(("login", self.login))
        for _ in range(rng.randint(1, 3)):
            steps.append(("category", self.category))
        if rng.random() < self.a.search_rate:
            steps.append(("search", lambda: self.hit("search", f"{root}/catalogsearch/result/?" +
                                                     urllib.parse.urlencode({"q": rng.choice(SEARCH_WORDS)}))))
        for _ in range(rng.randint(1, 5)):
            steps.append(("product", self.product_view))
        for name, fn in steps:
            if self.stop.is_set():
                return
            result = fn()
            if name == "login" and result:
                logged = True
            if not self.think():
                return
        if self.cart and rng.random() < 0.6:
            self.hit("cart", root + "/checkout/cart/")
            if logged and rng.random() < self.a.checkout_rate and self.think():
                self.hit("checkout", root + "/checkout/onepage/")
            if not self.think():
                return
        if logged:
            self.hit("account", root + "/customer/account/")
            if self.think():
                self.hit("logout", root + "/customer/account/logout/")

    def category(self):
        rng = self.rng
        url = rng.choice(self.shop.categories)
        r = rng.random()
        if r < 0.25:
            url += f"?p={rng.randint(2, 5)}"
        elif r < 0.40:
            url += "?" + urllib.parse.urlencode({"order": rng.choice(["price", "name"]), "dir": rng.choice(["asc", "desc"])})
        return self.hit("category", url)[0]

    def product_view(self):
        pid = self.shop.product(self.rng)
        html, _ = self.hit("product", f"{self.shop.root}/catalog/product/view/id/{pid}")
        key = self.form_key(html)
        if key and self.rng.random() < self.a.cart_rate and self.think():
            html, _ = self.hit("add_to_cart", f"{self.shop.root}/checkout/cart/add/product/{pid}/",
                               {"form_key": key, "product": pid, "qty": 1})
            self.cart = self.cart or html is not None
        return html

    def login(self) -> bool:
        html, _ = self.hit("login_page", self.shop.root + "/customer/account/login/")
        key = self.form_key(html)
        if not key or not self.think():
            return False
        acc = self.rng.choice(self.accounts)
        html, final = self.hit("login", self.shop.root + "/customer/account/loginPost/",
                               {"form_key": key, "login[username]": acc["email"], "login[password]": acc["password"]})
        if html is not None and "/customer/account/login" in (final or ""):
            # revenu sur le formulaire : connexion refusée, comptée comme erreur fonctionnelle
            self.rec.add(time.time(), time.time(), self.rec.step, self.uid, "login", 200, 0, 0, "connexion refusée")
            return False
        return html is not None

    def run(self):
        while not self.stop.is_set():
            self.cart = False
            try:
                self.session()
            except Exception as e:  # noqa: BLE001 - un visiteur qui plante repart sur une nouvelle visite
                self.rec.add(time.time(), time.time(), self.rec.step, self.uid, "session", 0, 0, 0, f"{type(e).__name__}: {e}")
            self.stop.wait(self.rng.uniform(0, 2))      # nouvelle visite


# --- mesures -------------------------------------------------------------------------------------

def pct(vals: list[float], q: float) -> float:
    if not vals:
        return 0.0
    vals = sorted(vals)
    i = (len(vals) - 1) * q
    lo = int(i)
    return vals[lo] + (vals[min(lo + 1, len(vals) - 1)] - vals[lo]) * (i - lo)


def stats(rows: list[tuple], seconds: float) -> dict:
    ms = [r[6] for r in rows if not r[8]]
    errors = sum(1 for r in rows if r[8])
    return {"requests": len(rows), "errors": errors, "error_rate": errors / len(rows) if rows else 0.0,
            "rps": len(rows) / seconds if seconds > 0 else 0.0, "ok_rps": (len(rows) - errors) / seconds if seconds > 0 else 0.0,
            "mean_ms": statistics.fmean(ms) if ms else 0.0, "p50_ms": pct(ms, .5), "p95_ms": pct(ms, .95), "p99_ms": pct(ms, .99)}


def crash_count(log: Path | None) -> int | None:
    if not log or not log.is_file():
        return None
    with log.open("rb") as f:
        return f.read().count(b"exited with status")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("base", nargs="?", default="http://127.0.0.1/magento")
    p.add_argument("--users", default="10,25,50,100,150,200,300", help="paliers de visiteurs simultanés")
    p.add_argument("--step", type=float, default=60, help="durée de chaque palier (s)")
    p.add_argument("--settle", type=float, default=10, help="début de palier non mesuré (s), le temps que la charge s'installe")
    p.add_argument("--think", default="2,8", help="pause entre deux pages, min,max en secondes (0 : aucune)")
    p.add_argument("--customers", default="data/magento_customers.csv", help="comptes clients (e-mail, mot de passe)")
    p.add_argument("--login-rate", type=float, default=0.25, help="part des visites qui se connectent")
    p.add_argument("--cart-rate", type=float, default=0.15, help="probabilité d'ajouter au panier après une fiche produit")
    p.add_argument("--search-rate", type=float, default=0.3, help="part des visites qui font une recherche")
    p.add_argument("--checkout-rate", type=float, default=0.3, help="part des visites connectées avec panier qui ouvrent la commande")
    p.add_argument("--products", default="1-10000", help="ids des produits, ex. 1-10000")
    p.add_argument("--zipf", type=float, default=1.0, help="concentration de la popularité des produits")
    p.add_argument("--timeout", type=float, default=30, help="délai maximal d'une requête (s), au-delà : erreur")
    p.add_argument("--max-error", type=float, default=0.01, help="taux d'erreur maximal pour qu'un palier tienne")
    p.add_argument("--max-p95", type=float, default=3.0, help="p95 maximal (s) pour qu'un palier tienne")
    p.add_argument("--no-stop", action="store_true", help="faire tous les paliers même après la limite")
    p.add_argument("--apache-log", default="C:/wamp64/logs/apache_error.log", help="pour compter les plantages d'Apache")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--out", help="dossier des résultats (par défaut results/loadtest/<date>)")
    a = p.parse_args()
    lo, _, hi = a.think.partition(",")
    a.think = (float(lo), float(hi or lo))
    levels = [int(x) for x in a.users.split(",")]
    first, last = map(int, a.products.split("-"))
    out = Path(a.out or f"results/loadtest/{time.strftime('%Y%m%d-%H%M%S')}")
    out.mkdir(parents=True, exist_ok=True)

    accounts = []
    if Path(a.customers).is_file():
        with open(a.customers, newline="", encoding="utf-8") as f:
            accounts = list(csv.DictReader(f))
    shop = Shop(a.base, (first, last), a.zipf, a.seed, a.timeout)
    try:
        cats = shop.discover_categories()
    except Exception as e:  # noqa: BLE001
        print(f"boutique injoignable ({a.base}) : {e}")
        return 1
    log = Path(a.apache_log) if a.apache_log else None
    print(f"boutique {a.base} : {len(cats)} catégories, produits {first}-{last}, {len(accounts)} comptes clients")
    print(f"paliers {levels} visiteurs, {a.step:.0f} s chacun, pause {a.think[0]:g}-{a.think[1]:g} s ; résultats dans {out}\n")
    print(f"{'visiteurs':>9} {'req/s':>7} {'médiane':>9} {'p95':>9} {'p99':>9} {'erreurs':>8} {'plantages':>9}  verdict")

    rec, stop = Recorder(), threading.Event()
    users: list[User] = []
    steps = []
    started = time.time()
    try:
        for i, level in enumerate(levels, 1):
            rec.step = i
            crashes0 = crash_count(log)
            while len(users) < level:
                u = User(len(users) + 1, shop, rec, accounts, a, stop)
                users.append(u)
                u.start()
                time.sleep(min(0.05, a.step / 20 / max(level, 1)))   # arrivée étalée, pas en rafale
            t_step = time.time()
            time.sleep(a.step)
            t_end = time.time()
            window = [r for r in rec.rows if r[2] == i and r[0] >= t_step + a.settle]
            s = stats(window, t_end - t_step - a.settle)
            c1 = crash_count(log)
            s.update({"step": i, "users": level, "t_measured": t_step + a.settle, "t_end": t_end, "crashes": None if crashes0 is None or c1 is None else c1 - crashes0,
                      "pages": {k: stats([r for r in window if r[4] == k], t_end - t_step - a.settle)
                                for k in sorted({r[4] for r in window})}})
            s["holds"] = s["error_rate"] <= a.max_error and s["p95_ms"] <= a.max_p95 * 1000 and s["requests"] > 0
            steps.append(s)
            print(f"{level:>9} {s['rps']:>7.1f} {s['p50_ms']:>7.0f}ms {s['p95_ms']:>7.0f}ms {s['p99_ms']:>7.0f}ms "
                  f"{s['error_rate']:>7.1%} {'' if s['crashes'] is None else s['crashes']:>9}  "
                  f"{'tient' if s['holds'] else 'NE TIENT PAS'}", flush=True)
            if not s["holds"] and not a.no_stop:
                break
    except KeyboardInterrupt:
        print("\ninterrompu : rapport des paliers terminés")
    finally:
        stop.set()
        for u in users:
            u.join(timeout=a.timeout + 1)

    write_results(out, rec.rows, steps, a, levels, len(cats), len(accounts), time.time() - started)
    return 0


def write_results(out: Path, rows, steps, a, levels, n_cats, n_accounts, wall):
    with (out / "requests.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["start", "end", "step", "user", "page", "status", "ms", "bytes", "error"])
        w.writerows(rows)
    cols = ["step", "users", "requests", "rps", "ok_rps", "mean_ms", "p50_ms", "p95_ms", "p99_ms", "errors", "error_rate", "crashes", "holds"]
    with (out / "steps.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(steps)
    limit = None
    for s in steps:                       # dernier palier tenu avant le premier échec
        if not s["holds"]:
            break
        limit = s
    peak = max(steps, key=lambda s: s["ok_rps"], default=None)
    summary = {"base": a.base, "levels": levels, "step_s": a.step, "think_s": list(a.think), "max_error": a.max_error,
               "max_p95_s": a.max_p95, "categories": n_cats, "accounts": n_accounts, "wall_s": round(wall, 1),
               "max_users_holding": limit["users"] if limit else 0,
               "first_failing_users": next((s["users"] for s in steps if not s["holds"]), None),
               "peak_ok_rps": peak["ok_rps"] if peak else 0, "peak_at_users": peak["users"] if peak else None,
               "steps": steps}
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [f"# Test de charge — {a.base}", "",
             f"Paliers de {a.step:.0f} s ({a.settle:.0f} s d'installation non mesurés), pause entre pages "
             f"{a.think[0]:g}-{a.think[1]:g} s, {n_cats} catégories, {n_accounts} comptes clients. "
             f"Un palier tient si les erreurs restent sous {a.max_error:.0%} et le p95 sous {a.max_p95:g} s.", "",
             "| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |",
             "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    for s in steps:
        lines.append(f"| {s['users']} | {s['rps']:.1f} | {s['p50_ms']:.0f} ms | {s['p95_ms']:.0f} ms | {s['p99_ms']:.0f} ms | "
                     f"{s['error_rate']:.1%} ({s['errors']}) | {'—' if s['crashes'] is None else s['crashes']} | "
                     f"{'tient' if s['holds'] else '**ne tient pas**'} |")
    lines += ["", f"**Limite** : {summary['max_users_holding']} visiteurs simultanés"
              + (f" (le palier suivant, {summary['first_failing_users']}, ne tient pas)" if summary["first_failing_users"] else
                 " (aucun palier n'a échoué : relancer avec des paliers plus hauts)"),
              f"**Débit maximal sans erreur** : {summary['peak_ok_rps']:.1f} pages/s, à {summary['peak_at_users']} visiteurs.", ""]
    if steps:
        last = steps[-1]
        lines += [f"## Par type de page (palier de {last['users']} visiteurs)", "",
                  "| Page | Requêtes | Médiane | p95 | Erreurs |", "| --- | ---: | ---: | ---: | ---: |"]
        lines += [f"| {k} | {v['requests']} | {v['p50_ms']:.0f} ms | {v['p95_ms']:.0f} ms | {v['error_rate']:.1%} |"
                  for k, v in last["pages"].items()]
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nlimite : {summary['max_users_holding']} visiteurs simultanés ; débit maximal sans erreur : "
          f"{summary['peak_ok_rps']:.1f} pages/s à {summary['peak_at_users']} visiteurs")
    print(f"résultats : {out} (report.md, steps.csv, requests.csv, summary.json)")


if __name__ == "__main__":
    sys.exit(main())
