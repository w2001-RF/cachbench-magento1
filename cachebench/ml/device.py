"""Choix du calcul : processeur (numpy) ou carte graphique NVIDIA (CuPy, même API que numpy).

CuPy est facultatif : `pip install -e ".[gpu]"` (CUDA 13) ou `pip install cupy-cuda12x`
(CUDA 12). Sans lui, seul `cpu` est disponible et `auto` se replie sur le processeur.
"""
from __future__ import annotations

import numpy as np

DEVICES = ("cpu", "gpu", "auto")


def _cupy():
    """Le module cupy s'il est installé et qu'une carte CUDA répond, sinon la raison de l'échec."""
    try:
        import cupy as cp
    except ImportError:
        return None, "CuPy n'est pas installé (pip install -e \".[gpu]\", ou cupy-cuda12x pour CUDA 12)"
    try:
        if cp.cuda.runtime.getDeviceCount() < 1:
            return None, "aucune carte CUDA détectée"
    except Exception as e:  # noqa: BLE001 - pilote absent ou trop ancien : on explique, on ne plante pas
        return None, f"CUDA indisponible ({e})"
    return cp, None


def get_xp(device: str = "cpu"):
    """(module de calcul, nom lisible) pour `cpu`, `gpu` ou `auto`."""
    if device not in DEVICES:
        raise ValueError(f"calcul inconnu : {device!r} ({', '.join(DEVICES)})")
    if device == "cpu":
        return np, "cpu (numpy)"
    cp, why = _cupy()
    if cp is None:
        if device == "gpu":
            raise RuntimeError(f"calcul sur GPU impossible : {why}")
        return np, f"cpu (numpy) ; GPU non utilisé : {why}"
    name = cp.cuda.runtime.getDeviceProperties(cp.cuda.Device().id)["name"]
    return cp, f"gpu ({name.decode() if isinstance(name, bytes) else name}, CuPy {cp.__version__})"


def to_numpy(a) -> np.ndarray:
    return a.get() if hasattr(a, "get") else np.asarray(a)
