"""Générateur de traces synthétiques façon Magento 1.

Le générateur simule des sessions de clients qui naviguent dans une boutique, au lieu
de tirer des URL indépendantes. Toutes les valeurs par défaut sont des HYPOTHÈSES à
calibrer sur les traces réelles enregistrées par le module PHP.
"""
from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from typing import Iterator

import numpy as np

from .request import GET, PURGE, Request

DAY = 86_400.0

# Routes Magento 1 et clés d'URL correspondantes.
HOME, CATEGORY, PRODUCT, SEARCH, CART, ACCOUNT = (
    "cms_index_index", "catalog_category_view", "catalog_product_view",
    "catalogsearch_result_index", "checkout_cart_index", "customer_account_index",
)
NOT_CACHEABLE = {CART, ACCOUNT}
EXIT = "exit"


# Vocabulaire de recherche (combinaisons produit + attribut) pour la piste sémantique.
NOUNS = ["robe", "chemise", "jean", "veste", "manteau", "pull", "jupe", "short", "basket",
         "sandale", "botte", "sac", "ceinture", "montre", "lunette", "casquette", "echarpe",
         "pyjama", "maillot", "costume", "blouson", "gilet", "legging", "sweat", "polo",
         "cravate", "chaussette", "gant", "bonnet", "parfum", "portefeuille", "valise",
         "bijou", "collier", "bracelet", "bague", "tshirt", "debardeur", "doudoune", "imperméable"]
ATTRS = ["rouge", "noir", "blanc", "bleu", "vert", "rose", "gris", "beige", "marron", "jaune",
         "homme", "femme", "enfant", "cuir", "coton", "lin", "laine", "soie", "sport", "ete",
         "hiver", "slim", "large", "vintage", "promo", "taille 38", "taille 42", "xl", "luxe", "bio"]


def _default_transitions() -> dict[str, dict[str, float]]:
    return {
        "start":  {HOME: 0.40, CATEGORY: 0.25, PRODUCT: 0.25, SEARCH: 0.10},
        HOME:     {CATEGORY: 0.50, SEARCH: 0.15, PRODUCT: 0.15, EXIT: 0.20},
        CATEGORY: {PRODUCT: 0.55, CATEGORY: 0.15, SEARCH: 0.05, HOME: 0.05, EXIT: 0.20},
        PRODUCT:  {PRODUCT: 0.20, CATEGORY: 0.25, CART: 0.10, SEARCH: 0.05, EXIT: 0.40},
        SEARCH:   {PRODUCT: 0.55, SEARCH: 0.15, CATEGORY: 0.05, EXIT: 0.25},
        CART:     {PRODUCT: 0.15, ACCOUNT: 0.25, EXIT: 0.60},
        ACCOUNT:  {HOME: 0.20, EXIT: 0.80},
    }


def _default_sizes() -> dict[str, tuple[float, float]]:
    # (médiane en octets, sigma log-normal)
    return {HOME: (60_000, 0.2), CATEGORY: (80_000, 0.3), PRODUCT: (70_000, 0.35),
            SEARCH: (75_000, 0.3), CART: (40_000, 0.2), ACCOUNT: (35_000, 0.2)}


def _default_costs() -> dict[str, tuple[float, float]]:
    # (médiane du temps de rendu en ms, sigma log-normal)
    return {HOME: (300, 0.4), CATEGORY: (450, 0.4), PRODUCT: (400, 0.4),
            SEARCH: (600, 0.5), CART: (350, 0.3), ACCOUNT: (300, 0.3)}


@dataclass
class Magento1Config:
    n_requests: int = 100_000          # nombre de requêtes GET générées
    seed: int = 1
    n_products: int = 5_000
    n_categories: int = 150
    n_queries: int = 1_200             # recherches distinctes (au plus 40 × 30 combinaisons)
    product_alpha: float = 0.9         # Zipf de la popularité des produits
    category_alpha: float = 0.8
    query_alpha: float = 1.0
    in_category_alpha: float = 1.0     # position dans la liste d'une catégorie
    follow_category: float = 0.7       # depuis une catégorie, part des produits vus dans celle-ci
    sessions_per_hour: float = 600.0   # moyenne sur la journée
    diurnal_amplitude: float = 0.6     # 0 = trafic plat, 1 = creux à zéro la nuit
    think_time_s: float = 25.0         # temps moyen entre deux pages d'une session
    promo_every_s: float = DAY         # une promotion par jour
    promo_products: int = 20
    promo_share: float = 0.25          # part des vues produit qui vont aux produits en promo
    updates_per_hour: float = 30.0     # mises à jour prix/stock -> purge par tags
    new_products_per_day: float = 40.0 # nouveaux produits, affichés en tête de leur catégorie
    query_variant_rate: float = 0.15   # recherches avec une faute ou un synonyme
    transitions: dict = field(default_factory=_default_transitions)
    sizes: dict = field(default_factory=_default_sizes)
    costs: dict = field(default_factory=_default_costs)


class _Zipf:
    """Tirage de rangs selon une loi de Zipf, extensible quand la liste grandit."""

    def __init__(self, alpha: float, rng: np.random.Generator) -> None:
        self.alpha, self.rng = alpha, rng
        self._cdfs: dict[int, np.ndarray] = {}

    def draw(self, n: int) -> int:
        cdf = self._cdfs.get(n)
        if cdf is None:
            w = 1.0 / np.arange(1, n + 1) ** self.alpha
            cdf = self._cdfs[n] = np.cumsum(w) / w.sum()
        return int(min(np.searchsorted(cdf, self.rng.random()), n - 1))


class Magento1Generator:
    def __init__(self, cfg: Magento1Config) -> None:
        self.cfg = cfg
        self.rng = np.random.default_rng(cfg.seed)
        rng = self.rng
        # Popularité globale : ranked[i] = id du produit de rang i.
        self.ranked = list(rng.permutation(cfg.n_products))
        self.category_of = {p: int(rng.integers(cfg.n_categories)) for p in range(cfg.n_products)}
        self.cat_products: dict[int, list[int]] = {c: [] for c in range(cfg.n_categories)}
        for p in self.ranked:  # listes de catégorie triées par popularité
            self.cat_products[self.category_of[p]].append(p)
        self.cat_ranked = list(rng.permutation(cfg.n_categories))
        self.z_product = _Zipf(cfg.product_alpha, rng)
        self.z_category = _Zipf(cfg.category_alpha, rng)
        self.z_query = _Zipf(cfg.query_alpha, rng)
        self.z_in_cat = _Zipf(cfg.in_category_alpha, rng)
        self.promo: list[int] = []
        self.next_promo = 0.0
        self._key_size: dict[str, int] = {}
        self._next_pid = cfg.n_products
        # Générateur séparé pour le texte des recherches : le flux principal reste inchangé.
        self.qrng = np.random.default_rng([cfg.seed, 7])
        combos = [f"{n} {a}" for n in NOUNS for a in ATTRS]
        order = self.qrng.permutation(len(combos))
        self.queries = [combos[int(i)] for i in order[: cfg.n_queries]]

    # --- tirages ------------------------------------------------------------
    def _lognormal(self, median: float, sigma: float) -> float:
        return float(median * math.exp(sigma * self.rng.standard_normal()))

    def _size(self, key: str, kind: str) -> int:
        # Une même page garde sa taille d'une requête à l'autre.
        s = self._key_size.get(key)
        if s is None:
            s = max(1, int(self._lognormal(*self.cfg.sizes[kind])))
            self._key_size[key] = s
        return s

    def _product(self, category: int | None) -> int:
        cfg = self.cfg
        if category is not None and self.rng.random() < cfg.follow_category:
            items = self.cat_products[category]
            if items:
                return items[self.z_in_cat.draw(len(items))]
        if self.promo and self.rng.random() < cfg.promo_share:
            return self.promo[int(self.rng.integers(len(self.promo)))]
        return self.ranked[self.z_product.draw(len(self.ranked))]

    def _query(self) -> tuple[str, str]:
        """Renvoie (id d'intention, texte tapé). Une variante garde la même intention."""
        q = self.z_query.draw(len(self.queries))
        canonical = self.queries[q]
        intent = f"q{q}"
        if self.rng.random() < self.cfg.query_variant_rate:
            return intent, self._variant(canonical, int(self.rng.integers(3)))
        return intent, canonical

    def _variant(self, text: str, kind: int) -> str:
        words = text.split(" ")
        if kind == 0:   # faute de frappe : deux lettres voisines inversées
            w = int(self.qrng.integers(len(words)))
            word = words[w]
            if len(word) > 2:
                i = int(self.qrng.integers(len(word) - 1))
                words[w] = word[:i] + word[i + 1] + word[i] + word[i + 2:]
            return " ".join(words)
        if kind == 1:   # ordre des mots inversé
            return " ".join(reversed(words))
        return f"{words[0]}s " + " ".join(words[1:])   # pluriel

    def _page(self, ts: float, kind: str, category: int | None) -> tuple[Request, int | None]:
        cost = self._lognormal(*self.cfg.costs[kind])
        tags: tuple[str, ...] = ()
        text = None
        if kind == HOME:
            key, tags = "/", ("cms_page_home",)
        elif kind == CATEGORY:
            category = self.cat_ranked[self.z_category.draw(self.cfg.n_categories)]
            key, tags = f"/catalog/category/view/id/{category}", (f"catalog_category_{category}",)
        elif kind == PRODUCT:
            p = self._product(category)
            category = self.category_of[p]
            key, tags = f"/catalog/product/view/id/{p}", (f"catalog_product_{p}",)
        elif kind == SEARCH:
            canonical, text = self._query()
            key, tags = f"/catalogsearch/result/?q={text.replace(' ', '+')}", ("catalogsearch", f"intent_{canonical}")
        elif kind == CART:
            key = "/checkout/cart"
        else:
            key = "/customer/account"
        req = Request(ts=ts, key=key, size=self._size(key, kind), cost_ms=cost, kind=kind,
                      cacheable=kind not in NOT_CACHEABLE, tags=tags, text=text, op=GET)
        return req, category

    # --- événements de fond ---------------------------------------------------
    def _new_product(self) -> None:
        p = self._next_pid
        self._next_pid += 1
        c = int(self.rng.integers(self.cfg.n_categories))
        self.category_of[p] = c
        self.cat_products[c].insert(0, p)
        top = max(1, len(self.ranked) // 10)
        self.ranked.insert(int(self.rng.integers(top)), p)

    def _purge(self, ts: float) -> Request:
        p = self.ranked[self.z_product.draw(len(self.ranked))]
        tags = (f"catalog_product_{p}", f"catalog_category_{self.category_of[p]}")
        return Request(ts=ts, key="", size=0, kind="catalog_product_save", tags=tags, op=PURGE)

    def _session_rate(self, ts: float) -> float:
        cfg = self.cfg
        phase = 2 * math.pi * (ts / DAY - 0.25)   # pic l'après-midi, creux la nuit
        return cfg.sessions_per_hour / 3600 * max(0.05, 1 + cfg.diurnal_amplitude * math.sin(phase))

    # --- génération -------------------------------------------------------------
    def __iter__(self) -> Iterator[Request]:
        cfg, rng = self.cfg, self.rng
        # File d'événements : (ts, ordre, type, état)
        events: list = []
        order = 0

        def push(ts, kind, state=None):
            nonlocal order
            heapq.heappush(events, (ts, order, kind, state))
            order += 1

        push(rng.exponential(1 / self._session_rate(0.0)), "session")
        if cfg.updates_per_hour > 0:
            push(rng.exponential(3600 / cfg.updates_per_hour), "update")
        if cfg.new_products_per_day > 0:
            push(rng.exponential(DAY / cfg.new_products_per_day), "new_product")

        emitted = 0
        while emitted < cfg.n_requests:
            ts, _, kind, state = heapq.heappop(events)
            if ts >= self.next_promo:
                self.promo = [self.ranked[int(i)] for i in
                              rng.integers(len(self.ranked) // 2, len(self.ranked), cfg.promo_products)]
                self.next_promo = ts + cfg.promo_every_s
            if kind == "session":
                push(ts + rng.exponential(1 / self._session_rate(ts)), "session")
                push(ts, "page", ("start", None))
            elif kind == "update":
                push(ts + rng.exponential(3600 / cfg.updates_per_hour), "update")
                yield self._purge(ts)
            elif kind == "new_product":
                push(ts + rng.exponential(DAY / cfg.new_products_per_day), "new_product")
                self._new_product()
            else:
                prev, category = state
                nxt = self._step(prev)
                if nxt == EXIT:
                    continue
                req, category = self._page(ts, nxt, category)
                yield req
                emitted += 1
                push(ts + rng.exponential(cfg.think_time_s), "page", (nxt, category))

    def _step(self, state: str) -> str:
        options = self.cfg.transitions[state]
        names = list(options)
        p = np.asarray([options[n] for n in names], dtype=float)
        return names[int(self.rng.choice(len(names), p=p / p.sum()))]


def generate(cfg: Magento1Config | None = None, **overrides) -> list[Request]:
    cfg = cfg or Magento1Config()
    for k, v in overrides.items():
        if not hasattr(cfg, k):
            raise TypeError(f"paramètre inconnu du générateur Magento 1 : {k}")
        setattr(cfg, k, v)
    return list(Magento1Generator(cfg))
