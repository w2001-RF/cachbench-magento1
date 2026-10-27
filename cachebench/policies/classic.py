"""Politiques classiques : références basses (LRU, LFU, FIFO) et borne haute (OPT)."""
from __future__ import annotations

import heapq
import math
from collections import OrderedDict
from typing import Sequence

from ..traces.request import Request
from .base import KeyedPolicy, register


@register("lru")
class LRU(KeyedPolicy):
    def __init__(self, capacity_bytes: int, **params) -> None:
        super().__init__(capacity_bytes, **params)
        self._order: OrderedDict[str, None] = OrderedDict()

    def _on_hit(self, key, req):
        self._order.move_to_end(key)

    def _on_insert(self, key, req):
        self._order[key] = None

    def _on_remove(self, key):
        del self._order[key]

    def _victim(self):
        return next(iter(self._order))


@register("fifo")
class FIFO(LRU):
    def _on_hit(self, key, req):
        pass


@register("lfu")
class LFU(KeyedPolicy):
    """LFU, égalités départagées par ancienneté (LRU au sein d'une fréquence)."""

    def __init__(self, capacity_bytes: int, **params) -> None:
        super().__init__(capacity_bytes, **params)
        self._freq: dict[str, int] = {}
        self._buckets: dict[int, OrderedDict[str, None]] = {}
        self._min = 1

    def _bump(self, key: str, f: int) -> None:
        self._freq[key] = f
        self._buckets.setdefault(f, OrderedDict())[key] = None

    def _unlink(self, key: str) -> int:
        f = self._freq.pop(key)
        b = self._buckets[f]
        del b[key]
        if not b:
            del self._buckets[f]
        return f

    def _on_hit(self, key, req):
        self._bump(key, self._unlink(key) + 1)

    def _on_insert(self, key, req):
        self._bump(key, 1)
        self._min = 1

    def _on_remove(self, key):
        self._unlink(key)

    def _victim(self):
        f = self._min
        while f not in self._buckets:
            f += 1
        self._min = f
        return next(iter(self._buckets[f]))


@register("opt")
class Belady(KeyedPolicy):
    """Belady : évince l'objet redemandé le plus tard, n'admet pas un objet jamais redemandé.

    Optimal pour des objets de taille unitaire ; avec des tailles variables c'est une
    borne de référence, pas l'optimum exact (problème NP-difficile).
    Il connaît le futur : il sert de plafond, jamais de concurrent.
    """

    def __init__(self, capacity_bytes: int, **params) -> None:
        super().__init__(capacity_bytes, **params)
        self._next: list[float] = []
        self._keys: list[str] = []
        self._pos = -1
        self._due: dict[str, float] = {}
        self._heap: list[tuple[float, str]] = []

    def prepare(self, requests: Sequence[Request]) -> None:
        self._keys = [r.key for r in requests]
        self._next = [math.inf] * len(requests)
        last: dict[str, int] = {}
        for i in range(len(requests) - 1, -1, -1):
            k = self._keys[i]
            self._next[i] = last.get(k, math.inf)
            last[k] = i

    def access(self, req: Request) -> bool:
        self._pos += 1
        if not self._keys:
            raise RuntimeError("OPT a besoin de prepare() avant de jouer la trace")
        if self._keys[self._pos] != req.key:
            raise RuntimeError("OPT : la trace jouée diffère de celle passée à prepare()")
        return super().access(req)

    def _admit(self, req: Request) -> bool:
        due = self._next[self._pos]
        if req.size > self.capacity or due == math.inf:
            return False
        if self.used_bytes() + req.size <= self.capacity:
            return True
        # Plein : n'admettre que si l'objet revient avant le candidat à l'éviction.
        while self._due.get(self._heap[0][1]) != -self._heap[0][0]:
            heapq.heappop(self._heap)
        return due < -self._heap[0][0]

    def _schedule(self, key: str) -> None:
        due = self._next[self._pos]
        self._due[key] = due
        heapq.heappush(self._heap, (-due, key))

    def _on_hit(self, key, req):
        self._schedule(key)

    def _on_insert(self, key, req):
        self._schedule(key)

    def _on_remove(self, key):
        del self._due[key]

    def _victim(self):
        while True:
            neg_due, key = heapq.heappop(self._heap)
            if self._due.get(key) == -neg_due:
                return key
