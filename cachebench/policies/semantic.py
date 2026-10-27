"""Cache sémantique pour les pages de recherche, sur le modèle de GPTCache et upstash/semantic-cache.

Même chaîne que GPTCache (embedding -> recherche du plus proche -> seuil de similarité),
avec le seuil `threshold` qui joue le rôle du `minProximity` d'Upstash. Les autres pages
passent par un LRU exact.

Un « hit approché » sert la page d'une autre recherche jugée équivalente. Il peut être
faux : le générateur Magento 1 marque l'intention réelle de chaque recherche (tag
intent_*), ce qui permet de compter les faux hits. Le moteur publie :
  approx_hit_rate : part des requêtes servies par un hit approché ;
  false_hit_rate  : part des requêtes servies avec la page d'une autre intention.

L'embedding par défaut est un hachage de trigrammes de caractères, mot par mot : il
absorbe les fautes de frappe, l'ordre des mots et les pluriels, sans dépendance. Il ne
comprend pas les synonymes ; un modèle de phrases (sentence-transformers) pourra se
brancher via `embed()` quand on aura de vraies recherches.
"""
from __future__ import annotations

import zlib

import numpy as np

from ..traces.request import Request
from .base import register
from .classic import LRU


def counts(text: str, dim: int = 1024, n: int = 3) -> np.ndarray:
    """Nombre d'occurrences de chaque trigramme haché (entiers, donc produits scalaires exacts)."""
    v = np.zeros(dim)
    for word in text.lower().split():
        w = f" {word} "
        for i in range(len(w) - n + 1):
            v[zlib.crc32(w[i:i + n].encode()) % dim] += 1.0
    return v


def embed(text: str, dim: int = 1024, n: int = 3) -> np.ndarray:
    v = counts(text, dim, n)
    norm = np.linalg.norm(v)
    return v / norm if norm else v


def _intent(req: Request) -> str | None:
    for t in req.tags:
        if t.startswith("intent_"):
            return t
    return None


@register("semantic")
class SemanticCache(LRU):
    """Paramètres : threshold (similarité cosinus minimale, 0-1), dim."""

    def __init__(self, capacity_bytes: int, threshold: float = 0.85, dim: int = 1024, **params) -> None:
        super().__init__(capacity_bytes, **params)
        self.threshold = float(threshold)
        self.dim = int(dim)
        # Comptes entiers et normes : cos = (a·b) / (|a| |b|) se calcule à l'identique en PHP,
        # ce qui garde le même départage quand deux recherches sont aussi proches l'une que l'autre.
        self._mat = np.zeros((64, self.dim))
        self._norm = np.ones(64)
        self._slot: dict[str, int] = {}
        self._slot_key: list[str | None] = [None] * 64
        self._free: list[int] = list(range(63, -1, -1))
        self._intent: dict[str, str | None] = {}
        self.approx_hits = 0
        self.false_hits = 0

    def access(self, req: Request) -> bool:
        if req.text is None or req.key in self:
            return super().access(req)
        v = counts(req.text, self.dim)
        nv = float(np.sqrt(v @ v))
        if self._slot and nv > 0:
            sims = (self._mat @ v) / (self._norm * nv)
            best = int(np.argmax(sims))
            if sims[best] >= self.threshold:
                key = self._slot_key[best]
                self._on_hit(key, req)
                if self.measuring:
                    self.approx_hits += 1
                    if self._intent.get(key) != _intent(req):
                        self.false_hits += 1
                return True
        hit = super().access(req)
        if req.key in self:
            self._store(req.key, v, _intent(req))
        return hit

    def _store(self, key: str, v: np.ndarray, intent: str | None) -> None:
        if not self._free:
            n = len(self._slot_key)
            self._mat = np.vstack([self._mat, np.zeros((n, self.dim))])
            self._norm = np.concatenate([self._norm, np.ones(n)])
            self._slot_key.extend([None] * n)
            self._free = list(range(2 * n - 1, n - 1, -1))
        i = self._free.pop()
        self._mat[i] = v
        self._norm[i] = np.sqrt(v @ v) or 1.0
        self._slot[key] = i
        self._slot_key[i] = key
        self._intent[key] = intent

    def _on_remove(self, key):
        super()._on_remove(key)
        i = self._slot.pop(key, None)
        if i is not None:
            self._mat[i] = 0.0
            self._norm[i] = 1.0
            self._slot_key[i] = None
            self._free.append(i)
            del self._intent[key]
