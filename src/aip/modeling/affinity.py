"""Seed-affinity baselines with typed abstention (FR14, FR23, FR24).

Inputs are standardized feature matrices (fit on the training partition). NaN means unknown:
similarity uses only dimensions observed in both vectors, and low coverage abstains instead of scoring.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class AffinityResult:
    scores: np.ndarray  # cosine in [-1, 1]; NaN where abstained
    abstain_reasons: list[str | None]

    @property
    def abstained(self) -> np.ndarray:
        return np.array([r is not None for r in self.abstain_reasons])


def standardize_fit(train: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean = np.nanmean(train, axis=0)
    std = np.nanstd(train, axis=0)
    std[~np.isfinite(std) | (std == 0)] = 1.0
    return mean, std


def standardize_apply(x: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    return (x - mean) / std


def _masked_cosine(candidates: np.ndarray, prototype: np.ndarray, min_coverage: float) -> AffinityResult:
    scores = np.full(candidates.shape[0], np.nan)
    reasons: list[str | None] = []
    proto_known = ~np.isnan(prototype)
    for i, row in enumerate(candidates):
        mask = ~np.isnan(row) & proto_known
        coverage = mask.sum() / candidates.shape[1]
        if coverage < min_coverage:
            reasons.append("entity_feature_coverage_insufficient")
            continue
        a, b = row[mask], prototype[mask]
        denom = np.linalg.norm(a) * np.linalg.norm(b)
        if denom == 0:
            reasons.append("zero_vector")
            continue
        scores[i] = float(np.clip(a @ b / denom, -1.0, 1.0))
        reasons.append(None)
    return AffinityResult(scores, reasons)


def centroid_affinity(seed: np.ndarray, candidates: np.ndarray, min_coverage: float) -> AffinityResult:
    """Cosine to the seed centroid. min_coverage is a required parameter (no platform default)."""
    return _masked_cosine(candidates, np.nanmean(seed, axis=0), min_coverage)


def _kmeans(x: np.ndarray, k: int, rng: np.random.Generator, iterations: int = 50) -> np.ndarray:
    centers = [x[rng.integers(len(x))]]
    for _ in range(1, k):
        d2 = np.min([((x - c) ** 2).sum(axis=1) for c in centers], axis=0)
        probs = d2 / d2.sum() if d2.sum() > 0 else np.full(len(x), 1 / len(x))
        centers.append(x[rng.choice(len(x), p=probs)])
    centers_arr = np.array(centers)
    for _ in range(iterations):
        labels = np.argmin(((x[:, None, :] - centers_arr[None]) ** 2).sum(axis=2), axis=1)
        updated = np.array([x[labels == j].mean(axis=0) if np.any(labels == j) else centers_arr[j] for j in range(k)])
        if np.allclose(updated, centers_arr):
            break
        centers_arr = updated
    return centers_arr


def multi_prototype_affinity(
    seed: np.ndarray, candidates: np.ndarray, k: int, min_coverage: float, rng_seed: int
) -> AffinityResult:
    """Max cosine over k seed prototypes. Seed rows with unknowns are mean-filled for clustering only."""
    filled = np.where(np.isnan(seed), np.nanmean(seed, axis=0), seed)
    prototypes = _kmeans(filled, k, np.random.default_rng(rng_seed))
    results = [_masked_cosine(candidates, p, min_coverage) for p in prototypes]
    stacked = np.vstack([r.scores for r in results])
    all_nan = np.all(np.isnan(stacked), axis=0)
    best = np.full(stacked.shape[1], np.nan)
    best[~all_nan] = np.nanmax(stacked[:, ~all_nan], axis=0)
    return AffinityResult(best, results[0].abstain_reasons)
