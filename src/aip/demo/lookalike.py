"""Synthetic look-alike run for the demonstrator. Behavior evidence only; synthetic results are not market evidence."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

import numpy as np

from aip.modeling.affinity import (
    AffinityResult,
    centroid_affinity,
    multi_prototype_affinity,
    standardize_apply,
    standardize_fit,
)

BINS = np.linspace(-1.0, 1.0, 21)


def _synthetic(p: Mapping[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(p["rng_seed"])
    d = p["n_features"]
    prototypes = rng.normal(0.0, 1.0, size=(2, d)) * 1.5

    def around(n: int) -> np.ndarray:
        return prototypes[rng.integers(0, 2, size=n)] + rng.normal(0.0, 0.8, size=(n, d))

    seed = around(p["n_seed"])
    n_heldout = int(round(p["heldout_fraction"] * p["n_seed"]))
    train_seed, heldout = seed[n_heldout:], seed[:n_heldout]
    n_background = p["n_pool"] - p["n_lookalikes"] - n_heldout
    pool = np.vstack([around(p["n_lookalikes"]), heldout, rng.normal(0.0, 1.5, size=(n_background, d))])
    is_heldout = np.zeros(len(pool), dtype=bool)
    is_heldout[p["n_lookalikes"] : p["n_lookalikes"] + n_heldout] = True
    # Unknowns stay NaN; a small share of entities is mostly unobserved so the coverage rule abstains.
    pool[rng.random(pool.shape) < p["missing_rate"]] = np.nan
    sparse = rng.random(len(pool)) < p["missing_rate"] / 2
    pool[sparse, : d - 2] = np.nan
    order = rng.permutation(len(pool))
    return train_seed, pool[order], is_heldout[order]


def _summary(name: str, result: AffinityResult, is_heldout: np.ndarray, reach: float) -> dict[str, Any]:
    scored = ~np.isnan(result.scores)
    k = max(1, int(np.floor(reach * scored.sum())))
    ranked = np.argsort(-np.where(scored, result.scores, -np.inf), kind="stable")[:k]
    hits = int(is_heldout[ranked].sum())
    heldout_total, heldout_scored = int(is_heldout.sum()), int((is_heldout & scored).sum())
    counts, _ = np.histogram(result.scores[scored], bins=BINS)
    return {
        "method": name,
        "pool": int(len(result.scores)),
        "scored": int(scored.sum()),
        "abstained": {k: v for k, v in sorted(Counter(r for r in result.abstain_reasons if r).items())},
        "reach_fraction": reach,
        "selected": k,
        "heldout_seed": {
            "total": heldout_total,
            "scored": heldout_scored,
            "found_in_selection": hits,
            "recall_all": round(hits / heldout_total, 4),
            "recall_scored_only": round(hits / heldout_scored, 4) if heldout_scored else None,
            "random_expectation": round(k / int(scored.sum()), 4),
        },
        "histogram": {"edges": [round(float(e), 2) for e in BINS], "counts": [int(c) for c in counts]},
    }


def run(params: Mapping[str, Any]) -> dict[str, Any]:
    train_seed, pool, is_heldout = _synthetic(params)
    mean, std = standardize_fit(pool)  # fit on the unlabeled universe, never on held-out labels
    seed_z, pool_z = standardize_apply(train_seed, mean, std), standardize_apply(pool, mean, std)
    reach = params["reach_fraction"]
    return {
        "synthetic": True,
        "parameters": dict(params),
        "score_type": "seed_affinity",
        "scale": "cosine",
        "claim": "exploratory",
        "methods": [
            _summary("centroid", centroid_affinity(seed_z, pool_z, params["min_coverage"]), is_heldout, reach),
            _summary(
                "multi_prototype",
                multi_prototype_affinity(
                    seed_z, pool_z, params["prototypes"], params["min_coverage"], params["rng_seed"]
                ),
                is_heldout,
                reach,
            ),
        ],
    }
