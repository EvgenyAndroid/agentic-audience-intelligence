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
