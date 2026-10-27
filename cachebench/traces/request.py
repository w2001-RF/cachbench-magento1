"""Format de requête commun, partagé par le moteur Python et le module PHP."""
from __future__ import annotations

from dataclasses import dataclass

GET = "get"
PURGE = "purge"


@dataclass(frozen=True, slots=True)
class Request:
    """Un événement de trace.

    op="get"   : une page ou un bloc est demandé (hit ou miss).
    op="purge" : Magento nettoie le cache par tags (mise à jour de prix, de stock...).
    """

    ts: float                    # secondes depuis le début de la trace
    key: str                     # clé de cache : URL, id de bloc, requête de recherche
    size: int = 1                # octets
    cost_ms: float = 0.0         # temps de rendu si miss
    kind: str = ""               # route Magento 1, ex. catalog_product_view
    cacheable: bool = True
    tags: tuple[str, ...] = ()
    text: str | None = None      # texte de recherche (piste sémantique)
    op: str = GET
