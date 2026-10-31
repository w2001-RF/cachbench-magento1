"""Petit réseau dense en numpy (ReLU), entraîné par Adam.

Volontairement sans PyTorch : le modèle s'exporte en JSON et le module PHP Magento 1
refait le même calcul (quelques produits matrice-vecteur) sans dépendance.

Format JSON :
  {"format": "cachebench-mlp-1", "features": [...noms...],
   "mean": [...], "std": [...],
   "layers": [{"W": [[...], ...], "b": [...]}, ...]}   # ReLU entre les couches, sortie linéaire
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .device import get_xp, to_numpy

FORMAT = "cachebench-mlp-1"


class MLP:
    def __init__(self, sizes: list[int], seed: int = 0, features: list[str] | None = None) -> None:
        rng = np.random.default_rng(seed)
        self.W = [rng.normal(0, np.sqrt(2 / a), (a, b)) for a, b in zip(sizes, sizes[1:])]
        self.b = [np.zeros(b) for b in sizes[1:]]
        self.mean = np.zeros(sizes[0])
        self.std = np.ones(sizes[0])
        self.features = features or [f"x{i}" for i in range(sizes[0])]

    # --- inférence --------------------------------------------------------------
    def predict(self, X: np.ndarray) -> np.ndarray:
        h = (X - self.mean) / self.std
        for i, (W, b) in enumerate(zip(self.W, self.b)):
            h = h @ W + b
            if i < len(self.W) - 1:
                h = np.maximum(h, 0)
        return h[:, 0]

    # --- entraînement -------------------------------------------------------------
    def fit(self, X: np.ndarray, y: np.ndarray, epochs: int = 8, batch: int = 512,
            lr: float = 1e-3, seed: int = 0, log=None, device: str = "cpu") -> list[float]:
        """device : « cpu » (numpy), « gpu » (CuPy) ou « auto ». Mêmes lots, même ordre, même
        Adam ; sur GPU les sommes ne se font pas dans le même ordre, d'où des poids très proches
        mais pas identiques au bit près."""
        xp, name = get_xp(device)
        if log:
            log(f"calcul : {name}")
        rng = np.random.default_rng(seed)
        self.mean = X.mean(axis=0)
        self.std = X.std(axis=0) + 1e-6
        Xn = xp.asarray((X - self.mean) / self.std)
        y = xp.asarray(y)
        Ws = [xp.asarray(W) for W in self.W]
        bs = [xp.asarray(b) for b in self.b]
        params = Ws + bs
        m = [xp.zeros_like(p) for p in params]
        v = [xp.zeros_like(p) for p in params]
        t = 0
        losses = []
        for ep in range(epochs):
            idx = xp.asarray(rng.permutation(len(Xn)))
            total = 0.0
            for s in range(0, len(idx), batch):
                bi = idx[s:s + batch]
                xb, yb = Xn[bi], y[bi]
                # passe avant
                acts = [xb]
                h = xb
                for i, (W, b) in enumerate(zip(Ws, bs)):
                    h = h @ W + b
                    if i < len(Ws) - 1:
                        h = xp.maximum(h, 0)
                    acts.append(h)
                err = h[:, 0] - yb
                total += (err ** 2).sum()   # reste sur la carte : pas de synchronisation par lot
                # passe arrière (erreur quadratique)
                g = (2 * err / len(bi))[:, None]
                gW, gb = [], []
                for i in range(len(Ws) - 1, -1, -1):
                    gW.insert(0, acts[i].T @ g)
                    gb.insert(0, g.sum(axis=0))
                    if i > 0:
                        g = (g @ Ws[i].T) * (acts[i] > 0)
                grads = gW + gb
                t += 1
                for p, gr, mi, vi in zip(params, grads, m, v):
                    mi *= 0.9
                    mi += 0.1 * gr
                    vi *= 0.999
                    vi += 0.001 * gr * gr
                    p -= lr * (mi / (1 - 0.9 ** t)) / (xp.sqrt(vi / (1 - 0.999 ** t)) + 1e-8)
            losses.append(float(total) / len(Xn))
            if log:
                log(f"époque {ep + 1}/{epochs} : erreur quadratique moyenne {losses[-1]:.4f}")
        self.W = [to_numpy(W) for W in Ws]
        self.b = [to_numpy(b) for b in bs]
        return losses

    # --- export ---------------------------------------------------------------------
    def to_dict(self, **meta) -> dict:
        return {"format": FORMAT, **meta, "features": self.features,
                "mean": self.mean.tolist(), "std": self.std.tolist(),
                "layers": [{"W": W.tolist(), "b": b.tolist()} for W, b in zip(self.W, self.b)]}

    def save(self, path: str | Path, **meta) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(**meta)), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> tuple["MLP", dict]:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        if d.get("format") != FORMAT:
            raise ValueError(f"{path} n'est pas un modèle {FORMAT}")
        sizes = [len(d["mean"])] + [len(l["b"]) for l in d["layers"]]
        net = cls(sizes, features=d["features"])
        net.W = [np.asarray(l["W"], dtype=float) for l in d["layers"]]
        net.b = [np.asarray(l["b"], dtype=float) for l in d["layers"]]
        net.mean = np.asarray(d["mean"], dtype=float)
        net.std = np.asarray(d["std"], dtype=float)
        return net, d
