"""Workbench modeling: candidate models per method, evaluated on held-out data.

Every method returns, per candidate model, a score for each entity (None where the model abstains or the
entity is already in the seed), an evaluation on held-out data, and feature drivers at a grid of reach
levels. Entities used to fit a model never count toward its evaluation.
"""

from __future__ import annotations

import warnings
from typing import Any

import numpy as np

from aip.modeling.affinity import (
    AffinityResult,
    centroid_affinity,
    multi_prototype_affinity,
    standardize_apply,
    standardize_fit,
)
from aip.modeling.metrics import average_precision, brier_score, log_loss, reliability_bins
from aip.modeling.propensity import fit_boosted_candidate, fit_logistic_baseline
from aip.workbench.generate import Synthetic

MIN_COVERAGE = 0.6
HOLDOUT_FRACTION = 0.3
PROTOTYPES = 4
MIN_POSITIVES = 100
REACH_GRID = (0.01, 0.05, 0.1, 0.2, 0.5)
DRIVER_COUNT = 5


def used_features(data: Synthetic, families: tuple[str, ...] | None = None) -> list[int]:
    """Columns a model may use: never a sensitive one; optionally only some signal families."""
    return [
        i for i, f in enumerate(data.spec.features) if not f.sensitive and (families is None or f.family in families)
    ]


def _split(indices: np.ndarray, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    shuffled = rng.permutation(indices)
    cut = int(round(len(shuffled) * (1 - HOLDOUT_FRACTION)))
    return np.sort(shuffled[:cut]), np.sort(shuffled[cut:])


def _round(scores: np.ndarray) -> list[float | None]:
    return [None if not np.isfinite(s) else round(float(s), 4) for s in scores]


def _drivers(
    data: Synthetic, cols: list[int], scores: np.ndarray, x: np.ndarray | None = None
) -> dict[str, list[dict[str, Any]]]:
    """Standardized mean difference between the audience at each reach level and the scored pool (the rows of
    `x`, the dataset's own records unless given)."""
    x = data.x if x is None else x
    scored = np.flatnonzero(np.isfinite(scores))
    order = scored[np.argsort(-scores[scored], kind="stable")]
    pool = x[scored][:, cols]
    mean, sd = np.nanmean(pool, axis=0), np.nanstd(pool, axis=0)
    sd[~np.isfinite(sd) | (sd == 0)] = 1.0
    out: dict[str, list[dict[str, Any]]] = {}
    for reach in REACH_GRID:
        top = order[: max(1, int(round(reach * len(order))))]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)  # a column with no values in a small audience
            smd = (np.nanmean(x[top][:, cols], axis=0) - mean) / sd
        # A column the audience has no values for has no difference to report (and NaN is not valid JSON).
        ranked = [j for j in np.argsort(-np.abs(np.nan_to_num(smd)), kind="stable") if np.isfinite(smd[j])]
        ranked = ranked[:DRIVER_COUNT]
        out[str(reach)] = [
            {"feature": data.spec.features[cols[j]].name, "smd": round(float(smd[j]), 3)} for j in ranked
        ]
    return out


def _affinity_candidates(
    data: Synthetic, positives: np.ndarray, cols: list[int], rng_seed: int
) -> tuple[list[dict[str, Any]], np.ndarray, np.ndarray]:
    rng = np.random.default_rng(rng_seed)
    train, held = _split(positives, rng)
    x = data.x[:, cols]
    mean, std = standardize_fit(x)
    z = standardize_apply(x, mean, std)
    candidates_mask = np.ones(len(z), dtype=bool)
    candidates_mask[train] = False
    results: list[tuple[str, str, AffinityResult]] = [
        ("centroid", "Centroid similarity", centroid_affinity(z[train], z, MIN_COVERAGE)),
        (
            "multi_prototype",
            f"Multi-prototype similarity (k-means, {PROTOTYPES} prototypes)",
            multi_prototype_affinity(z[train], z, PROTOTYPES, MIN_COVERAGE, rng_seed),
        ),
    ]
    models = []
    for model_id, label, result in results:
        scores = np.where(candidates_mask, result.scores, np.nan)
        reasons = [r for r, c in zip(result.abstain_reasons, candidates_mask, strict=True) if c and r]
        models.append(
            {
                "model_id": model_id,
                "label": label,
                "scale": "cosine",
                "scores": _round(scores),
                "abstained": {r: reasons.count(r) for r in sorted(set(reasons))},
                "drivers": _drivers(data, cols, scores),
                "_scores": scores,
            }
        )
    return models, train, held


def _recall_at(scores: np.ndarray, held: np.ndarray, reach: float) -> float:
    """Share of held-out positives in the top `reach` of the candidate pool (abstentions count as misses)."""
    candidates = np.flatnonzero(~np.isnan(scores) | np.isin(np.arange(len(scores)), held))
    finite = candidates[np.isfinite(scores[candidates])]
    top = finite[np.argsort(-scores[finite], kind="stable")][: int(round(reach * len(candidates)))]
    return float(np.isin(held, top).mean()) if len(held) else 0.0


def _affinity_setup(data: Synthetic, kind: str) -> tuple[np.ndarray, list[int], int]:
    if kind == "lookalike":
        return data.seed, used_features(data), data.spec.rng_seed + 1
    return data.behavior, used_features(data, ("behavioral",)), data.spec.rng_seed + 2


def affinity(data: Synthetic, kind: str) -> dict[str, Any]:
    """kind 'lookalike' models the seed list on all permitted features; 'actalike' models the behavior
    pattern on behavioral features only."""
    positives, cols, rng_seed = _affinity_setup(data, kind)
    models, train, held = _affinity_candidates(data, positives, cols, rng_seed)
    for m in models:
        m["evaluation"] = {
            "kind": "heldout_recall",
            "heldout_count": int(len(held)),
            "recall_at": {str(r): round(_recall_at(m["_scores"], held, r), 4) for r in REACH_GRID},
        }
    return {
        "features": [data.spec.features[i].name for i in cols],
        "fit_count": int(len(train)),
        "heldout": [int(i) for i in held],
        "models": models,
    }


def _propensity_metrics(y: np.ndarray, p: np.ndarray) -> dict[str, Any]:
    return {
        "average_precision": round(average_precision(y, p), 4),
        "brier": round(brier_score(y, p), 4),
        "log_loss": round(log_loss(y, p), 4),
        "base_rate": round(float(y.mean()), 4),
        "reliability": [{k: round(v, 4) for k, v in b.items()} for b in reliability_bins(y, p, 10)],
    }


def propensity(data: Synthetic) -> dict[str, Any]:
    assert data.outcome is not None
    rng = np.random.default_rng(data.spec.rng_seed + 3)
    train, test = _split(np.arange(data.spec.n), rng)
    cols = used_features(data)
    x, y = data.x[:, cols], data.outcome.astype(int)
    fitted = [
        ("logistic", "Logistic regression", fit_logistic_baseline(x[train], y[train], data.spec.rng_seed)),
        ("boosted", "Gradient-boosted trees", fit_boosted_candidate(x[train], y[train], data.spec.rng_seed, 150)),
    ]
    models: list[dict[str, Any]] = []
    for model_id, label, model in fitted:
        p = model.predict_proba(x)[:, 1]
        models.append(
            {
                "model_id": model_id,
                "label": label,
                "scale": "probability",
                "scores": _round(p),
                "abstained": {},
                "drivers": _drivers(data, cols, p),
                "evaluation": {
                    "kind": "heldout_outcome",
                    "test_count": int(len(test)),
                    **_propensity_metrics(y[test], p[test]),
                },
            }
        )
    return {
        "features": [data.spec.features[i].name for i in cols],
        "fit_count": int(len(train)),
        "heldout": [int(i) for i in test],
        "heldout_labels": [int(v) for v in y[test]],
        "models": models,
    }


def expand(data: Synthetic, kind: str, universe: np.ndarray, exclude: np.ndarray) -> dict[str, Any]:
    """Score a universe of new records with the same candidate models `affinity` or `propensity` fit on `data`.

    The fit is repeated with the same split and seeds, so the models are the ones evaluated on held-out
    records. `universe` has one column per feature of `data` (sensitive ones are never read); rows flagged in
    `exclude` (already positive in the uploaded file) get no score. The universe has no labels, so there is
    no evaluation here: the held-out evaluation on `data` is the expected quality."""
    models: list[dict[str, Any]] = []
    if kind == "byom":
        cols, known, p = _byom_scores(data, universe)
        p = np.where(exclude, np.nan, p)
        missing = int((~known & ~exclude).sum())
        models.append(
            {
                "model_id": "registered",
                "label": "Your registered model (supplied weights)",
                "scale": "probability",
                "scores": _round(p),
                "abstained": {"required_feature_missing": missing} if missing else {},
                "drivers": _drivers(data, cols, p, universe),
            }
        )
    elif kind == "semantic":
        cols, _, scores = _brief_scores(data, universe)
        scores = np.where(exclude, np.nan, scores)
        models.append(
            {
                "model_id": "brief_similarity",
                "label": "Similarity to the content brief",
                "scale": "cosine",
                "scores": _round(scores),
                "abstained": {},
                "drivers": _drivers(data, cols, scores, universe),
            }
        )
    elif kind == "propensity":
        assert data.outcome is not None
        train, _ = _split(np.arange(data.spec.n), np.random.default_rng(data.spec.rng_seed + 3))
        cols = used_features(data)
        x, y = data.x[:, cols], data.outcome.astype(int)
        fitted = [
            ("logistic", "Logistic regression", fit_logistic_baseline(x[train], y[train], data.spec.rng_seed)),
            ("boosted", "Gradient-boosted trees", fit_boosted_candidate(x[train], y[train], data.spec.rng_seed, 150)),
        ]
        for model_id, label, model in fitted:
            p = np.where(exclude, np.nan, model.predict_proba(universe[:, cols])[:, 1])
            models.append(
                {
                    "model_id": model_id,
                    "label": label,
                    "scale": "probability",
                    "scores": _round(p),
                    "abstained": {},
                    "drivers": _drivers(data, cols, p, universe),
                }
            )
    else:
        positives, cols, rng_seed = _affinity_setup(data, kind)
        train, _ = _split(positives, np.random.default_rng(rng_seed))
        mean, std = standardize_fit(data.x[:, cols])
        seed_z = standardize_apply(data.x[train][:, cols], mean, std)
        z = standardize_apply(universe[:, cols], mean, std)
        results = [
            ("centroid", "Centroid similarity", centroid_affinity(seed_z, z, MIN_COVERAGE)),
            (
                "multi_prototype",
                f"Multi-prototype similarity (k-means, {PROTOTYPES} prototypes)",
                multi_prototype_affinity(seed_z, z, PROTOTYPES, MIN_COVERAGE, rng_seed),
            ),
        ]
        for model_id, label, result in results:
            scores = np.where(exclude, np.nan, result.scores)
            reasons = [r for r, e in zip(result.abstain_reasons, exclude, strict=True) if r and not e]
            models.append(
                {
                    "model_id": model_id,
                    "label": label,
                    "scale": "cosine",
                    "scores": _round(scores),
                    "abstained": {r: reasons.count(r) for r in sorted(set(reasons))},
                    "drivers": _drivers(data, cols, scores, universe),
                }
            )
    return {"features": [data.spec.features[i].name for i in cols], "excluded": int(exclude.sum()), "models": models}


def labels_qualified(data: Synthetic) -> tuple[bool, int]:
    positives = int(data.outcome.sum()) if data.outcome is not None else 0
    return positives * (1 - HOLDOUT_FRACTION) >= MIN_POSITIVES, positives


# The registered bring-your-own model: weights the owner supplied, over standardized features.
BYOM_WEIGHTS = {"crm": {"orders_12m": 0.9, "aov_index": 0.5, "loyalty_member": 0.5, "days_since_order_log": -0.8}}
BYOM_INTERCEPT = {"crm": -2.6}


def _byom_scores(data: Synthetic, x_all: np.ndarray) -> tuple[list[int], np.ndarray, np.ndarray]:
    """The registered model's probabilities for the rows of `x_all`, standardized on `data`'s own records."""
    weights, names = BYOM_WEIGHTS[data.spec.dataset_id], [f.name for f in data.spec.features]
    cols = [names.index(f) for f in weights]
    x = x_all[:, cols]
    known = ~np.isnan(x).any(axis=1)
    mean, sd = np.nanmean(data.x[:, cols], axis=0), np.nanstd(data.x[:, cols], axis=0)
    linear = BYOM_INTERCEPT[data.spec.dataset_id] + ((x - mean) / sd) @ np.array(list(weights.values()))
    return cols, known, np.where(known, 1 / (1 + np.exp(-linear)), np.nan)


def byom(data: Synthetic) -> dict[str, Any]:
    assert data.outcome is not None
    weights = BYOM_WEIGHTS[data.spec.dataset_id]
    cols, known, p = _byom_scores(data, data.x)
    rng = np.random.default_rng(data.spec.rng_seed + 3)
    _, test = _split(np.arange(data.spec.n), rng)
    test_known = test[known[test]]
    y = data.outcome.astype(int)
    return {
        "features": list(weights),
        "fit_count": 0,
        "heldout": [int(i) for i in test],
        "heldout_labels": [int(v) for v in y[test]],
        "models": [
            {
                "model_id": "registered",
                "label": "Your registered model (supplied weights)",
                "scale": "probability",
                "scores": _round(p),
                "abstained": {"required_feature_missing": int((~known).sum())} if (~known).any() else {},
                "drivers": _drivers(data, cols, p),
                "evaluation": {
                    "kind": "heldout_outcome",
                    "test_count": int(len(test_known)),
                    **_propensity_metrics(y[test_known], p[test_known]),
                },
            }
        ],
    }


def _brief_scores(data: Synthetic, x_all: np.ndarray) -> tuple[list[int], list[str], np.ndarray]:
    """Similarity of the rows of `x_all` to the content brief, standardized on `data`'s own pages."""
    cols = used_features(data, ("contextual",))
    mean, std = standardize_fit(data.x[:, cols])
    z = standardize_apply(x_all[:, cols], mean, std)
    names = [data.spec.features[i].name for i in cols]
    brief = np.zeros(len(cols))
    for name, weight in {"topic_food": 2.0, "tone_positive": 0.6, "brand_safety": 0.8}.items():
        if name in names:
            brief[names.index(name)] = weight
    return cols, names, centroid_affinity(brief[None, :], z, MIN_COVERAGE).scores


def semantic(data: Synthetic) -> dict[str, Any]:
    """Cosine similarity of each page to a content-brief vector over contextual features. The brief is the
    mean profile of the brief's topic, a stand-in for an embedded brief; relevance uses the hidden topic."""
    assert data.spec.brief_segment is not None
    cols, names, scores = _brief_scores(data, data.x)
    relevant = np.flatnonzero(data.segment == data.spec.brief_segment)
    return {
        "features": names,
        "fit_count": 0,
        "heldout": [int(i) for i in relevant],
        "models": [
            {
                "model_id": "brief_similarity",
                "label": "Similarity to the content brief",
                "scale": "cosine",
                "scores": _round(scores),
                "abstained": {},
                "drivers": _drivers(data, cols, scores),
                "evaluation": {
                    "kind": "brief_relevance",
                    "relevant_count": int(len(relevant)),
                    "recall_at": {str(r): round(_recall_at(scores, relevant, r), 4) for r in REACH_GRID},
                },
            }
        ],
    }


def strip_private(result: dict[str, Any]) -> dict[str, Any]:
    for m in result["models"]:
        m.pop("_scores", None)
    return result
