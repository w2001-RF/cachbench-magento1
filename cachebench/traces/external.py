"""Traces sur fichier, dans le format commun ou dans celui d'un jeu de données externe.

Formats (détectés d'après le nom et la première ligne du fichier, ou forcés par `format`) :
  cachebench    CSV commun ts,op,key,size,... (ce dépôt et le module PHP)
  magento       timestamp,url,size,category (magento_trace_*.csv)
  rees46        event_time,event_type,product_id,... (.csv ou .csv.gz), tailles synthétiques
                (alias : kaggle)
  retailrocket  events.csv : timestamp,visitorid,event,itemid,transactionid
  twitter       traces de production Twitter : timestamp,key,key_size,value_size,client,op,ttl
  libcachesim   oracleGeneral binaire (.bin) ou sa forme CSV « # time, object, size, ... »
  access_log    journaux Apache / Nginx / Varnish (Common ou Combined Log Format)

Hors format commun, la lecture est faite par loaders.py du projet cache_benchmark, copié
sans modification ; `options` est passé à son lecteur (event_types, include_writes,
strip_query...). Ses CacheRequest sont convertis en Request :
- ts        : secondes depuis la première requête ;
- kind      : la catégorie traduite en route Magento 1 (product -> catalog_product_view,
              api -> checkout_cart_index...) ; une catégorie inconnue (kv, object) reste telle quelle ;
- cacheable : faux pour les routes non cachables du générateur (panier, compte), donc pour api ;
              `uncacheable` donne une autre liste de routes ou de catégories ;
- size      : avec stable_sizes (par défaut), chaque clé garde la taille de sa première
              requête. Les magento_trace_*.csv tirent une taille différente à chaque ligne
              pour la même URL ; le moteur y verrait une nouvelle version de la page, donc un
              miss, à chaque requête ;
- cost_ms   : ces jeux n'ont pas de temps de rendu. Par défaut, la médiane du générateur
              pour la route (Magento1Config.costs), 0 sinon ; `costs` la remplace, par
              catégorie ou par route.
Ces traces ne contiennent ni purge ni tags.
"""
from __future__ import annotations

from itertools import islice
from pathlib import Path
from typing import Iterable

from .._cache_benchmark.loaders import LOADERS, _read_lines, detect_format, load_trace
from .io import read_csv
from .magento1 import CART, CATEGORY, HOME, NOT_CACHEABLE, PRODUCT, SEARCH, Magento1Config
from .request import Request

FORMATS = ["cachebench", *sorted(LOADERS)]

CATEGORY_KINDS = {"product": PRODUCT, "category": CATEGORY, "search": SEARCH,
                  "cms_page": HOME, "api": CART}


def detect(path: str | Path) -> str:
    if "oraclegeneral" not in Path(path).name.lower():
        lines = _read_lines(str(path))
        try:
            first = next((line.strip() for line in lines if line.strip()), "")
        finally:
            lines.close()
        if first.startswith("ts,"):
            return "cachebench"
    return detect_format(str(path))


def load(path: str | Path, format: str | None = None, max_requests: int | None = None,
         costs: dict[str, float] | None = None, uncacheable: Iterable[str] | None = None,
         options: dict | None = None, stable_sizes: bool = True) -> list[Request]:
    if not Path(path).is_file():
        # Le lecteur magento d'origine génère des données synthétiques si le fichier manque.
        raise FileNotFoundError(f"trace introuvable : {path}")
    fmt = format or detect(path)
    if fmt == "cachebench":
        return list(islice(read_csv(path), max_requests))
    if fmt not in LOADERS:
        raise ValueError(f"format de trace inconnu : {fmt} (disponibles : {', '.join(FORMATS)})")
    raw = load_trace(str(path), fmt, max_requests=max_requests, **(options or {}))

    cost_of = {kind: median for kind, (median, _) in Magento1Config().costs.items()}
    cost_of.update(costs or {})
    skip = set(NOT_CACHEABLE if uncacheable is None else uncacheable)
    t0 = min((r.timestamp for r in raw), default=0.0)
    first_size: dict[str, int] = {}
    out = []
    for r in raw:
        kind = CATEGORY_KINDS.get(r.category, r.category)
        size = first_size.setdefault(r.key, r.size) if stable_sizes else r.size
        out.append(Request(
            ts=r.timestamp - t0, key=r.key, size=size,
            cost_ms=float(cost_of.get(r.category, cost_of.get(kind, 0.0))),
            kind=kind, cacheable=kind not in skip and r.category not in skip,
        ))
    return out
