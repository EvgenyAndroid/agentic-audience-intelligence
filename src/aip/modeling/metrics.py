"""Evaluation metrics in numpy. Brier score and log loss do not isolate calibration; use reliability bins too."""

from __future__ import annotations

import numpy as np


def _top_with_ties(scores: np.ndarray, k: int) -> np.ndarray:
    """Indices of the top k scores, where a cut-off that falls inside a group of tied scores takes the whole
    group: everything scoring at least the k-th highest score is selected. The selection therefore depends only
    on the scores, never on the order of the rows, and can hold more than k entries when scores tie."""
    if len(scores) == 0:
        return np.array([], dtype=int)
    threshold = np.sort(scores)[::-1][min(k, len(scores)) - 1]
    return np.flatnonzero(scores >= threshold)


def heldout_seed_recall_at(scores: np.ndarray, is_heldout_seed: np.ndarray, reach_fraction: float) -> float:
    """Share of held-out seed members ranked within the top reach_fraction of the scored pool (NaN scores excluded).
    Ties at the cut-off are selected together (see _top_with_ties)."""
    valid = ~np.isnan(scores)
    s, y = scores[valid], is_heldout_seed[valid].astype(bool)
    if y.sum() == 0:
        raise ValueError("no held-out seed members among scored entities")
    k = max(1, int(np.floor(reach_fraction * len(s))))
    top = _top_with_ties(s, k)
    return float(y[top].sum()) / float(y.sum())


def precision_at_reach(y: np.ndarray, p: np.ndarray, reach_fraction: float) -> float:
    """Positive rate among the top reach_fraction by score. Ties at the cut-off are selected together (see
    _top_with_ties)."""
    p = np.asarray(p, dtype=float)
    k = max(1, int(np.floor(reach_fraction * len(p))))
    top = _top_with_ties(p, k)
    return float(np.asarray(y)[top].mean())


def average_precision(y: np.ndarray, p: np.ndarray) -> float:
    """Step-function average precision, sum over distinct thresholds of (recall gained) x (precision there), as
    sklearn.metrics.average_precision_score computes it. Tied scores form one threshold: they are selected
    together, so the value does not depend on the order of the rows."""
    y = np.asarray(y).astype(bool)
    if y.sum() == 0:
        raise ValueError("average precision is undefined without positives")
    p = np.asarray(p, dtype=float)
    order = np.argsort(-p, kind="stable")
    ranked, hits = p[order], y[order]
    # The last position of each run of equal scores: one threshold per distinct score.
    ends = np.r_[np.flatnonzero(np.diff(ranked)), len(ranked) - 1]
    true_positives = np.cumsum(hits)[ends]
    precision = true_positives / (ends + 1)
    recall = true_positives / hits.sum()
    return float(np.sum(np.diff(np.r_[0.0, recall]) * precision))


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
