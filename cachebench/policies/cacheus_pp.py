"""Adaptateur vers CACHEUS++ (projet cache_benchmark, algorithms/cacheus_pp.py).

Le code est importé tel quel depuis cachebench/_cache_benchmark/. Il suit l'interface de cache_benchmark
(get, should_cache, put) ; on l'appelle dans le même ordre que son runner : get, puis en
cas de miss should_cache et put.

Correspondances :
- category  = route Magento (kind) : alimente le modèle d'admission et l'expert GDSF ;
- miss_cost = cost_ms de la requête (temps de rendu), le coût utilisé par GDSF. Sans coût
  dans la trace, on retombe sur tier_costs ou 1.0, comme dans le code d'origine ;
- la graine de l'expérience est passée à seed ; les autres paramètres YAML vont au
  constructeur (learning_rate, window_size, tier_costs...).

Fonctionne en octets comme en unités (sizes: unit). Attention à max_object_fraction
(0,1 par défaut) : un objet plus gros que 10 % du cache n'est jamais admis, donc en mode
« unit » il faut au moins 10 objets de capacité.

Le code d'origine ne sait pas retirer une entrée. Une purge (invalidation eager) ou une
page qui change de taille passe donc par sa méthode interne _evict, sans historique
fantôme ni apprentissage : ce n'est pas une éviction choisie par l'algorithme.
"""
from __future__ import annotations

from typing import Iterable

from .._cache_benchmark.algorithms.cacheus_pp import CACHEUSPlusPlus
from .._cache_benchmark.models import CacheRequest
from ..traces.request import Request
from .base import CachePolicy, register


@register("cacheus_pp")
class CacheusPP(CachePolicy):

    def __init__(self, capacity_bytes: int, **params) -> None:
        super().__init__(capacity_bytes, **params)
        self._alg = CACHEUSPlusPlus(self.capacity, **params)
        self._by_tag: dict[str, set[str]] = {}

    def access(self, req: Request) -> bool:
        key = req.key
        cached = self._alg.cache.get(key)
        if cached is not None and cached.size != req.size:
            # La page a changé de taille : nouvelle version, comme dans KeyedPolicy.
            self._drop(key)
        creq = CacheRequest(timestamp=req.ts, key=key, size=req.size, category=req.kind,
                            metadata={"miss_cost": req.cost_ms} if req.cost_ms > 0 else {})
        if self._alg.get(creq):
            return True
        if self._alg.should_cache(creq):
            self.evictions += self._alg.put(creq)
            if key in self._alg.cache:
                for t in req.tags:
                    self._by_tag.setdefault(t, set()).add(key)
        return False

    def _drop(self, key: str) -> None:
        # Retrait imposé de l'extérieur : il ne doit pas compter comme un échec d'admission.
        self._alg._meta[key].labeled = True
        self._alg._evict(key)

    def invalidate(self, tags: Iterable[str]) -> int:
        keys: set[str] = set()
        for t in tags:
            keys |= self._by_tag.pop(t, set())
        n = 0
        for k in keys:
            if k in self._alg.cache:
                self._drop(k)
                n += 1
        return n

    def used_bytes(self) -> int:
        return self._alg.current_size

    def __contains__(self, key: str) -> bool:
        return key in self._alg.cache
