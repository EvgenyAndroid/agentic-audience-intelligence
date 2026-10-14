"""Post-release drift (FR42, P1). Thresholds are supplied by policy; results propose reassessment only."""

from __future__ import annotations

import numpy as np


def population_stability_index(expected: np.ndarray, actual: np.ndarray, n_bins: int, eps: float = 1e-6) -> float:
    """PSI with quantile bins from the expected (reference) distribution. NaNs are dropped."""
    e, a = expected[~np.isnan(expected)], actual[~np.isnan(actual)]
    edges = np.unique(np.quantile(e, np.linspace(0, 1, n_bins + 1)))
    if len(edges) < 3:
        raise ValueError("reference distribution has too few distinct values for binning")
    edges[0], edges[-1] = -np.inf, np.inf
    pe = np.histogram(e, edges)[0] / len(e) + eps
    pa = np.histogram(a, edges)[0] / len(a) + eps
    return float(np.sum((pa - pe) * np.log(pa / pe)))
