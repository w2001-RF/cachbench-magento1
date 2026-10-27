"""Interface des politiques de cache et registre.

Ajouter un algorithme :
    @register("mon_algo")
    class MonAlgo(KeyedPolicy):
        def _victim(self) -> str: ...

Une politique qui gère elle-même son stockage (code officiel enveloppé, par
exemple) hérite directement de CachePolicy et implémente access().
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Iterable, Sequence

from ..traces.request import Request

_REGISTRY: dict[str, type["CachePolicy"]] = {}


def register(name: str) -> Callable[[type["CachePolicy"]], type["CachePolicy"]]:
    def deco(cls: type["CachePolicy"]) -> type["CachePolicy"]:
        if name in _REGISTRY:
            raise ValueError(f"politique déjà enregistrée : {name}")
        cls.name = name
        _REGISTRY[name] = cls
        return cls
    return deco


def get_policy(name: str) -> type["CachePolicy"]:
    try:
        return _REGISTRY[name]
    except KeyError:
        raise KeyError(f"politique inconnue : {name} (disponibles : {', '.join(available())})") from None


def available() -> list[str]:
    return sorted(_REGISTRY)


class CachePolicy(ABC):
    """Contrat minimal : une requête entre, hit ou miss sort."""

    name = "abstract"
    measuring = True   # mis à False par le moteur pendant la chauffe

    def __init__(self, capacity_bytes: int, **params) -> None:
        if capacity_bytes <= 0:
            raise ValueError("la capacité doit être positive")
        self.capacity = int(capacity_bytes)
        self.params = params
        self.evictions = 0

    def prepare(self, requests: Sequence[Request]) -> None:
        """Appelé une fois avec les requêtes qui seront jouées. Seul OPT s'en sert."""

    @abstractmethod
    def access(self, req: Request) -> bool:
        """Traite une requête cachable. Renvoie True si c'est un hit."""

    @abstractmethod
    def invalidate(self, tags: Iterable[str]) -> int:
        """Retire les entrées portant un de ces tags. Renvoie le nombre retiré."""

    @abstractmethod
    def used_bytes(self) -> int: ...

    @abstractmethod
    def __contains__(self, key: str) -> bool: ...


class KeyedPolicy(CachePolicy):
    """Base pratique : stockage, tags et comptage d'octets déjà gérés.

    Une sous-classe ne fournit que ses hooks d'ordre :
      _on_hit(key, req), _on_insert(key, req), _on_remove(key), _victim() -> key
    """

    def __init__(self, capacity_bytes: int, **params) -> None:
        super().__init__(capacity_bytes, **params)
        self._sizes: dict[str, int] = {}
        self._tags: dict[str, tuple[str, ...]] = {}
        self._by_tag: dict[str, set[str]] = {}
        self._used = 0

    # --- hooks -------------------------------------------------------------
    def _on_hit(self, key: str, req: Request) -> None: ...
    def _on_insert(self, key: str, req: Request) -> None: ...
    def _on_remove(self, key: str) -> None: ...

    @abstractmethod
    def _victim(self) -> str: ...

    def _admit(self, req: Request) -> bool:
        return req.size <= self.capacity

    # --- contrat -----------------------------------------------------------
    def access(self, req: Request) -> bool:
        key = req.key
        if key in self._sizes:
            if self._sizes[key] != req.size:
                # La page a changé de taille : on la traite comme une nouvelle version.
                self._remove(key)
            else:
                self._on_hit(key, req)
                return True
        if not self._admit(req):
            return False
        while self._used + req.size > self.capacity:
            self._remove(self._victim())
            self.evictions += 1
        self._sizes[key] = req.size
        self._tags[key] = req.tags
        for t in req.tags:
            self._by_tag.setdefault(t, set()).add(key)
        self._used += req.size
        self._on_insert(key, req)
        return False

    def invalidate(self, tags: Iterable[str]) -> int:
        keys: set[str] = set()
        for t in tags:
            keys |= self._by_tag.get(t, set())
        for k in keys:
            self._remove(k)
        return len(keys)

    def _remove(self, key: str) -> None:
        self._used -= self._sizes.pop(key)
        for t in self._tags.pop(key):
            s = self._by_tag.get(t)
            if s is not None:
                s.discard(key)
                if not s:
                    del self._by_tag[t]
        self._on_remove(key)

    def used_bytes(self) -> int:
        return self._used

    def __contains__(self, key: str) -> bool:
        return key in self._sizes

    def __len__(self) -> int:
        return len(self._sizes)
