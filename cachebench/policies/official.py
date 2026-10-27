"""Adaptateurs vers le code OFFICIEL du dépôt sylab/cacheus (CACHEUS, LeCaR, ARC, LIRS).

Le code n'est pas modifié : il est récupéré par scripts/fetch_vendor.sh dans
vendor/cacheus, au commit indiqué dans ce script, puis importé tel quel.

Deux différences avec les politiques de base, à garder en tête en lisant les résultats :

1. Ces algorithmes comptent des OBJETS, pas des octets. Ils exigent donc
   `engine: {sizes: unit}` dans la config : chaque page pèse 1 et la taille du cache
   devient un nombre d'objets (« 5% » = 5 % des clés uniques).
2. Ils n'ont pas d'opération de suppression. Une purge Magento est donc appliquée de
   façon paresseuse : l'entrée reste en place mais la requête suivante sur cette clé
   compte comme un miss (la page doit être recalculée).
"""
from __future__ import annotations

import importlib
import os
import sys
import types
from pathlib import Path
from typing import Iterable, Sequence

from ..traces.request import Request
from .base import CachePolicy, register

PACKAGE = "_cacheus_official"


def vendor_dir() -> Path:
    env = os.environ.get("CACHEBENCH_CACHEUS_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "vendor" / "cacheus"


def _load_official(name: str):
    """Importe code/algs du dépôt cacheus sous un nom de paquet isolé, sans toucher sys.path."""
    algs = vendor_dir() / "code" / "algs"
    if not algs.is_dir():
        raise RuntimeError(
            f"code officiel de CACHEUS introuvable dans {algs}. "
            "Lancer scripts/fetch_vendor.sh (ou définir CACHEBENCH_CACHEUS_DIR).")
    if PACKAGE not in sys.modules:
        pkg = types.ModuleType(PACKAGE)
        pkg.__path__ = [str(algs)]
        sys.modules[PACKAGE] = pkg
    try:
        mod = importlib.import_module(f"{PACKAGE}.get_algorithm")
    except ModuleNotFoundError as e:
        raise RuntimeError(f"dépendance du code officiel manquante ({e.name}) : "
                           "pip install -e '.[official]'") from e
    cls = mod.get_algorithm(name)
    if cls is None:
        raise KeyError(f"algorithme absent du dépôt cacheus : {name}")
    return cls


class OfficialPolicy(CachePolicy):
    official_name = ""

    def __init__(self, capacity_bytes: int, window_size: int | None = None, **params) -> None:
        params.pop("seed", None)  # le code officiel fixe ses propres graines
        super().__init__(capacity_bytes, **params)
        self._window = window_size
        self._alg = None
        self._resident: set[str] = set()
        self._stale: set[str] = set()
        self._by_tag: dict[str, set[str]] = {}
        self._hit_op = None

    def prepare(self, requests: Sequence[Request]) -> None:
        # Même règle que run.py du dépôt : fenêtre = 1 % de la trace.
        window = self._window or max(100, len(requests) // 100)
        self._build(window)

    def _build(self, window: int) -> None:
        cls = _load_official(self.official_name)
        self._alg = cls(self.capacity, window, **self.params)
        self._hit_op = importlib.import_module(f"{PACKAGE}.lib.cacheop").CacheOp.HIT

    def access(self, req: Request) -> bool:
        if req.size != 1:
            raise ValueError(f"{self.name} compte des objets : mettre `engine: {{sizes: unit}}` dans la config")
        if self._alg is None:
            self._build(self._window or 100)
        key = req.key
        op, evicted = self._alg.request(key, req.ts)
        if evicted is not None:
            self._resident.discard(evicted)
            self._stale.discard(evicted)
            self.evictions += 1
        if key in self._alg:
            self._resident.add(key)
            for t in req.tags:
                self._by_tag.setdefault(t, set()).add(key)
        hit = op == self._hit_op and key not in self._stale
        self._stale.discard(key)
        return hit

    def invalidate(self, tags: Iterable[str]) -> int:
        n = 0
        for t in tags:
            keys = self._by_tag.pop(t, set())
            for k in keys & self._resident:
                self._stale.add(k)
                n += 1
        return n

    def used_bytes(self) -> int:
        return len(self._resident)

    def __contains__(self, key: str) -> bool:
        return key in self._resident and key not in self._stale


def _official(name: str, official: str) -> None:
    cls = type(f"Official_{official}", (OfficialPolicy,), {"official_name": official})
    register(name)(cls)


for _name in ("cacheus", "lecar", "arc", "lirs"):
    _official(_name, _name)
