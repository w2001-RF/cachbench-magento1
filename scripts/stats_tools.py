"""Statistiques des scripts d'évaluation : intervalles de confiance et tests appariés.

Toutes les comparaisons sont appariées : les deux politiques voient la même trace, la même
graine et la même taille de cache, et on teste la différence réplique par réplique.

- moyenne ± demi-largeur de l'intervalle à 95 % (loi de Student, n - 1 degrés de liberté) ;
- différence appariée : moyenne, IC 95 % de Student et IC 95 % bootstrap (percentiles, 10 000
  rééchantillonnages), p du test t apparié et du test des rangs signés de Wilcoxon (sans
  hypothèse de normalité), taille d'effet d_z de Cohen, victoires / égalités / défaites ;
- correction de Holm-Bonferroni quand on teste plusieurs scénarios à la fois.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import stats

LEVEL = 0.95


def mean_ci(x) -> tuple[float, float]:
    """(moyenne, demi-largeur de l'IC 95 %). Demi-largeur nulle pour une seule valeur."""
    x = np.asarray(x, dtype=float)
    if len(x) < 2:
        return float(x.mean()), 0.0
    half = stats.t.ppf((1 + LEVEL) / 2, len(x) - 1) * x.std(ddof=1) / math.sqrt(len(x))
    return float(x.mean()), float(half)


def paired(a, b, n_boot: int = 10_000, seed: int = 0) -> dict:
    """Compare b à a sur les mêmes répliques : différence b - a."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    d = b - a
    n = len(d)
    mean, half = mean_ci(d)
    out = {"n": n, "mean_a": float(a.mean()), "mean_b": float(b.mean()), "diff": mean,
           "ci_low": mean - half, "ci_high": mean + half,
           "wins": int((d > 0).sum()), "ties": int((d == 0).sum()), "losses": int((d < 0).sum())}
    sd = d.std(ddof=1) if n > 1 else 0.0
    out["dz"] = float(mean / sd) if sd > 0 else (math.inf if mean else 0.0)
    if n > 1 and sd > 0:
        out["p_t"] = float(stats.ttest_rel(b, a).pvalue)
    else:
        out["p_t"] = 0.0 if mean and n > 1 else 1.0
    nz = d[d != 0]
    out["p_wilcoxon"] = float(stats.wilcoxon(nz).pvalue) if len(nz) >= 1 else 1.0
    rng = np.random.default_rng(seed)
    boots = d[rng.integers(0, n, (n_boot, n))].mean(axis=1)
    out["boot_low"], out["boot_high"] = (float(v) for v in np.percentile(boots, [2.5, 97.5]))
    return out


def holm(pvalues: list[float]) -> list[float]:
    """p ajustés de Holm-Bonferroni (contrôle du risque global de faux positif)."""
    m = len(pvalues)
    order = sorted(range(m), key=lambda i: pvalues[i])
    adj = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvalues[i]))
        adj[i] = running
    return adj


def fmt_p(p: float) -> str:
    return "< 0.0001" if p < 1e-4 else f"{p:.4f}"


def fmt_ci(mean: float, half: float, scale: float = 100, digits: int = 2) -> str:
    return f"{mean * scale:.{digits}f} ± {half * scale:.{digits}f}"
