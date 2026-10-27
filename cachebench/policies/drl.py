"""Éviction apprise, sur le modèle de DRL-Cache (ayushgupta4897/DRL-Cache).

Ce n'est PAS le code de DRL-Cache : celui-ci est lié à NGINX et à PyTorch. On en reprend
la conception, adaptée au benchmark et exportable vers PHP :

- au moment d'évincer, on regarde les K objets les moins récemment utilisés (comme
  DRL-Cache, K=16 par défaut) ;
- chaque candidat est décrit par des features proches des siennes (âge, taille, nombre
  de hits, temps depuis le dernier accès, coût de recalcul), plus le type de page Magento ;
- un réseau note chaque candidat ; on évince le mieux noté ;
- la récompense d'une éviction est celle de DRL-Cache : -(hits futurs perdus dans un
  horizon), ou +0,1 si l'objet ne revient pas. Comme cette récompense se calcule pour
  chaque candidat à partir de la trace, l'apprentissage est un bandit contextuel
  (horizon d'un pas), entraîné hors ligne sur une trace DIFFÉRENTE de celle d'évaluation.
"""
from __future__ import annotations

import bisect
import math
from itertools import islice
from pathlib import Path
from typing import Callable, Sequence

import numpy as np

from ..ml import MLP
from ..traces.request import GET, Request
from .base import KeyedPolicy, register
from .classic import LRU

FEATURES = ["log_age_s", "log_size_kb", "sqrt_hits", "log_idle_s", "log_cost_ms", "lru_rank",
            "is_product", "is_category", "is_search", "is_home"]
KINDS = ["catalog_product_view", "catalog_category_view", "catalogsearch_result_index", "cms_index_index"]


@register("drl")
class DRLEviction(LRU):
    """Paramètres : model (chemin du JSON entraîné), k (nombre de candidats)."""

    def __init__(self, capacity_bytes: int, model: str | None = None, k: int = 16, **params) -> None:
        super().__init__(capacity_bytes, **params)
        self.k = int(k)
        self._state: dict[str, list] = {}   # clé -> [insertion_ts, dernier_ts, hits, coût, taille, type]
        self._now = 0.0
        self.net: MLP | None = None
        if model is not None:
            self.net, meta = MLP.load(model)
            if meta.get("features") != FEATURES:
                raise ValueError(f"{model} a été entraîné avec d'autres features")
            self.k = int(meta.get("k", self.k))
        # Hooks utilisés seulement pendant l'entraînement.
        self.explore_rng: np.random.Generator | None = None
        self.recorder: Callable[[int, list[str], np.ndarray], None] | None = None
        self._pos = -1

    def access(self, req: Request) -> bool:
        self._now = req.ts
        self._pos += 1
        return super().access(req)

    def _on_hit(self, key, req):
        super()._on_hit(key, req)
        st = self._state[key]
        st[1] = req.ts
        st[2] += 1

    def _on_insert(self, key, req):
        super()._on_insert(key, req)
        self._state[key] = [req.ts, req.ts, 0, req.cost_ms, req.size, req.kind]

    def _on_remove(self, key):
        super()._on_remove(key)
        del self._state[key]

    def features(self, keys: list[str]) -> np.ndarray:
        X = np.empty((len(keys), len(FEATURES)))
        n = max(1, len(keys) - 1)
        for i, k in enumerate(keys):
            ins, last, hits, cost, size, kind = self._state[k]
            X[i, 0] = math.log1p(max(0.0, self._now - ins))
            X[i, 1] = math.log1p(size / 1024)
            X[i, 2] = math.sqrt(hits)
            X[i, 3] = math.log1p(max(0.0, self._now - last))
            X[i, 4] = math.log1p(cost)
            X[i, 5] = i / n
            for j, kd in enumerate(KINDS):
                X[i, 6 + j] = 1.0 if kind == kd else 0.0
        return X

    def _victim(self):
        keys = list(islice(iter(self._order), self.k))
        if len(keys) == 1:
            return keys[0]
        if self.recorder is not None:
            self.recorder(self._pos, keys, self.features(keys))
        if self.explore_rng is not None:
            return keys[int(self.explore_rng.integers(len(keys)))]
        if self.net is None:
            raise RuntimeError("drl a besoin d'un modèle entraîné : params: {model: models/....json} "
                               "(cachebench train-drl)")
        return keys[int(np.argmax(self.net.predict(self.features(keys))))]


def train(trace: Sequence[Request], capacity: int, out: str | Path, *, k: int = 16,
          horizon: int = 5000, hidden: int = 32, epochs: int = 8, seed: int = 0,
          log=print, meta: dict | None = None) -> dict:
    """Entraîne le réseau sur `trace` (déjà en mode de taille voulu) et l'écrit en JSON."""
    played = [r for r in trace if r.op == GET and r.cacheable]
    positions: dict[str, list[int]] = {}
    for i, r in enumerate(played):
        positions.setdefault(r.key, []).append(i)

    samples_X: list[np.ndarray] = []
    samples_y: list[np.ndarray] = []

    def record(pos: int, keys: list[str], X: np.ndarray) -> None:
        y = np.empty(len(keys))
        for j, key in enumerate(keys):
            p = positions[key]
            a = bisect.bisect_right(p, pos)
            b = bisect.bisect_right(p, pos + horizon)
            future = b - a
            y[j] = -min(future, 10) if future else 0.1   # récompense de DRL-Cache, bornée
        samples_X.append(X)
        samples_y.append(y)

    pol = DRLEviction(capacity, k=k)
    pol.explore_rng = np.random.default_rng(seed)   # politique de collecte : candidat au hasard
    pol.recorder = record
    from ..engine import EngineConfig, simulate
    simulate(pol, trace, EngineConfig(warmup=0, check_invariants=False))

    X = np.vstack(samples_X)
    y = np.concatenate(samples_y)
    log(f"{len(samples_X)} décisions d'éviction, {len(X)} candidats notés")
    net = MLP([len(FEATURES), hidden, hidden, 1], seed=seed, features=FEATURES)
    losses = net.fit(X, y, epochs=epochs, seed=seed, log=log)
    info = {"k": k, "horizon": horizon, "capacity": capacity, "decisions": len(samples_X),
            "final_loss": losses[-1], **(meta or {})}
    net.save(out, **info)
    return info
