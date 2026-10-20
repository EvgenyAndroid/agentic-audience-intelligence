import numpy as np
import pytest

from aip.modeling.affinity import centroid_affinity, multi_prototype_affinity, standardize_apply, standardize_fit
from aip.modeling.metrics import average_precision, brier_score, heldout_seed_recall_at, log_loss, reliability_bins
from aip.monitoring import population_stability_index

RNG = np.random.default_rng(7)


def synthetic(n_seed=60, n_pool=400, d=8):
    """Synthetic fixture: tests software behavior only, not market performance."""
    seed = RNG.normal(1.0, 1.0, (n_seed, d))
    pool = np.vstack([RNG.normal(1.0, 1.0, (40, d)), RNG.normal(-1.0, 1.0, (n_pool - 40, d))])
    is_like = np.r_[np.ones(40, bool), np.zeros(n_pool - 40, bool)]
    return seed, pool, is_like


def test_centroid_affinity_ranks_seed_like_entities_higher():
    seed, pool, is_like = synthetic()
    mean, std = standardize_fit(np.vstack([seed, pool]))
    result = centroid_affinity(standardize_apply(seed, mean, std), standardize_apply(pool, mean, std), min_coverage=0.5)
    assert heldout_seed_recall_at(result.scores, is_like, 0.10) > 0.5
    assert np.all(result.scores[~result.abstained] <= 1) and np.all(result.scores[~result.abstained] >= -1)


def test_abstention_for_low_coverage_and_zero_vectors():
    seed = np.ones((5, 4))
    pool = np.array([[np.nan, np.nan, np.nan, 1.0], [0.0, 0.0, 0.0, 0.0], [1.0, 1.0, 1.0, 1.0]])
    result = centroid_affinity(seed, pool, min_coverage=0.5)
    assert result.abstain_reasons == ["entity_feature_coverage_insufficient", "zero_vector", None]
    assert np.isnan(result.scores[:2]).all() and result.scores[2] == pytest.approx(1.0)


def test_multi_prototype_is_deterministic_for_a_seed():
    seed, pool, _ = synthetic()
    a = multi_prototype_affinity(seed, pool, k=3, min_coverage=0.5, rng_seed=1)
    b = multi_prototype_affinity(seed, pool, k=3, min_coverage=0.5, rng_seed=1)
    assert np.array_equal(a.scores, b.scores)


def test_probability_metrics():
    y = np.array([0, 0, 1, 1])
    p = np.array([0.1, 0.4, 0.35, 0.8])
    assert average_precision(y, p) == pytest.approx((1 + 2 / 3) / 2)
    assert brier_score(y, p) == pytest.approx(np.mean((p - y) ** 2))
    assert log_loss(y, p) > 0
    assert sum(b["count"] for b in reliability_bins(y, p, 5)) == 4


def test_propensity_baselines_fit_when_sklearn_is_installed():
    pytest.importorskip("sklearn")
    from aip.modeling.propensity import fit_boosted_candidate, fit_logistic_baseline

    x = RNG.normal(size=(300, 4))
    x[RNG.random(x.shape) < 0.05] = np.nan
    y = (np.nan_to_num(x[:, 0]) + RNG.normal(scale=0.5, size=300) > 0).astype(int)
    for model in (fit_logistic_baseline(x, y, 0), fit_boosted_candidate(x, y, 0, max_iter=50)):
        p = model.predict_proba(x)[:, 1]
        assert p.min() >= 0 and p.max() <= 1


def test_psi_detects_shift():
    base = RNG.normal(size=5000)
    assert population_stability_index(base, RNG.normal(size=5000), 10) < 0.05
    assert population_stability_index(base, RNG.normal(1.0, size=5000), 10) > 0.25


def test_multi_prototype_reasons_agree_with_scores():
    # Candidate 1 is observed only on dimension 0: it has zero norm against the [0, 1] prototype but scores
    # against the [1, 0] one. Its reason must follow the score whichever prototype the RNG orders first.
    seed = np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0], [0.0, 1.0]])
    pool = np.array([[0.0, 0.0], [1.0, np.nan]])
    for rng_seed in range(8):
        result = multi_prototype_affinity(seed, pool, k=2, min_coverage=0.5, rng_seed=rng_seed)
        for score, reason in zip(result.scores, result.abstain_reasons, strict=True):
            assert np.isnan(score) == (reason is not None), rng_seed
        assert result.abstain_reasons == ["zero_vector", None]


def test_every_abstention_carries_a_registered_inclusion_reason():
    from aip.registry import ReasonCodeRegistry

    registry = ReasonCodeRegistry.load()
    seed = np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0], [0.0, 1.0]])
    pool = np.array([[0.0, 0.0], [np.nan, np.nan], [1.0, 0.0]])
    result = multi_prototype_affinity(seed, pool, k=2, min_coverage=0.5, rng_seed=0)
    assert np.isfinite(result.scores[~result.abstained]).all()
    for reason in result.abstain_reasons[:2]:
        assert reason is not None
        registry.require(reason, "inclusion")


@pytest.mark.parametrize("bad", ["seed", "pool"])
def test_infinite_features_are_rejected(bad):
    seed = np.ones((3, 2))
    pool = np.ones((2, 2))
    (seed if bad == "seed" else pool)[0, 0] = np.inf
    with pytest.raises(ValueError):
        centroid_affinity(seed, pool, min_coverage=0.5)
    with pytest.raises(ValueError):
        multi_prototype_affinity(seed, pool, k=1, min_coverage=0.5, rng_seed=0)


# Finding D: average precision treats tied scores as one threshold, so row order cannot change it.


def test_average_precision_is_order_invariant_under_ties():
    y = np.array([1, 0, 1, 0, 0, 1, 0, 1, 0, 0])
    p = np.array([0.9, 0.9, 0.7, 0.7, 0.7, 0.4, 0.4, 0.4, 0.1, 0.1])
    values = set()
    for seed in (1, 2, 3):
        order = np.random.default_rng(seed).permutation(len(y))
        values.add(average_precision(y[order], p[order]))
    values.add(average_precision(y, p))
    assert len(values) == 1


@pytest.mark.parametrize(
    ("y", "p"),
    [
        ([1, 0, 1, 0, 0], [0.5, 0.5, 0.5, 0.5, 0.5]),  # every score tied
        ([0, 0, 1, 0, 0], [0.9, 0.8, 0.7, 0.6, 0.5]),  # a single positive
        ([0, 1, 0, 1, 0, 1], [0.9, 0.9, 0.9, 0.4, 0.3, 0.2]),  # positives tied with negatives at the top
        ([1, 0, 1, 1, 0, 0], [0.95, 0.85, 0.75, 0.65, 0.55, 0.45]),  # no ties
    ],
)
def test_average_precision_matches_sklearn_on_edge_cases(y, p):
    metrics = pytest.importorskip("sklearn.metrics")
    assert average_precision(np.array(y), np.array(p)) == pytest.approx(
        metrics.average_precision_score(y, p), abs=1e-12
    )


def test_average_precision_without_positives_raises():
    with pytest.raises(ValueError, match="without positives"):
        average_precision(np.zeros(5), np.linspace(0, 1, 5))


def test_reach_selection_takes_a_tied_group_whole():
    from aip.modeling.metrics import precision_at_reach

    # A 20% reach of 10 rows is 2, but three rows tie at the top: all three are selected, in any row order.
    y = np.array([1, 0, 0, 1, 0, 0, 1, 0, 0, 0])
    p = np.array([0.9, 0.9, 0.9, 0.5, 0.4, 0.3, 0.2, 0.1, 0.05, 0.0])
    for seed in (1, 2, 3):
        order = np.random.default_rng(seed).permutation(len(y))
        assert precision_at_reach(y[order], p[order], 0.2) == pytest.approx(1 / 3)
