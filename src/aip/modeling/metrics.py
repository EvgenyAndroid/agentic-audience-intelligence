"""Evaluation metrics in numpy. Brier score and log loss do not isolate calibration; use reliability bins too."""

from __future__ import annotations

import numpy as np


def heldout_seed_recall_at(scores: np.ndarray, is_heldout_seed: np.ndarray, reach_fraction: float) -> float:
    """Share of held-out seed members ranked within the top reach_fraction of the scored pool (NaN scores excluded)."""
    valid = ~np.isnan(scores)
    s, y = scores[valid], is_heldout_seed[valid].astype(bool)
    if y.sum() == 0:
        raise ValueError("no held-out seed members among scored entities")
    k = max(1, int(np.floor(reach_fraction * len(s))))
    top = np.argsort(-s, kind="stable")[:k]
    return float(y[top].sum()) / float(y.sum())


def precision_at_reach(y: np.ndarray, p: np.ndarray, reach_fraction: float) -> float:
    k = max(1, int(np.floor(reach_fraction * len(p))))
    top = np.argsort(-p, kind="stable")[:k]
    return float(np.asarray(y)[top].mean())


def average_precision(y: np.ndarray, p: np.ndarray) -> float:
    y = np.asarray(y).astype(bool)
    if y.sum() == 0:
        raise ValueError("average precision is undefined without positives")
    order = np.argsort(-np.asarray(p), kind="stable")
    hits = y[order]
    precision = np.cumsum(hits) / np.arange(1, len(hits) + 1)
    return float((precision * hits).sum() / hits.sum())


def brier_score(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean((np.asarray(p) - np.asarray(y)) ** 2))


def log_loss(y: np.ndarray, p: np.ndarray, eps: float = 1e-15) -> float:
    q = np.clip(np.asarray(p, dtype=float), eps, 1 - eps)
    y = np.asarray(y, dtype=float)
    return float(-np.mean(y * np.log(q) + (1 - y) * np.log(1 - q)))


def reliability_bins(y: np.ndarray, p: np.ndarray, n_bins: int) -> list[dict[str, float]]:
    edges = np.linspace(0, 1, n_bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, n_bins - 1)
    out = []
    for b in range(n_bins):
        m = idx == b
        if m.any():
            out.append(
                {
                    "bin_low": float(edges[b]),
                    "bin_high": float(edges[b + 1]),
                    "count": int(m.sum()),
                    "mean_predicted": float(np.mean(p[m])),
                    "observed_rate": float(np.mean(y[m])),
                }
            )
    return out
