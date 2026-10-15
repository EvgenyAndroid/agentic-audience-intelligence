"""Workbench bundles: routed by the real router, modeled only where eligible, evaluated on held-out data."""

import math

import pytest
from conftest import ROOT

from aip.canonical import load_path, sha256_of
from aip.cli import _close, main
from aip.contracts.validator import default_schema_set
from aip.workbench.generate import generate
from aip.workbench.methods import REACH_GRID
from aip.workbench.specs import DATASETS

DATA = ROOT / "app" / "data" / "workbench"
BUNDLES = {
    p.stem: load_path(p)
    for p in sorted(DATA.glob("*.json"))
    if p.name != "index.json" and not p.name.endswith(".universe.json")
}
UNIVERSES = {p.name.split(".")[0]: load_path(p) for p in sorted(DATA.glob("*.universe.json"))}


def test_committed_bundles_match_a_fresh_build():
    assert main(["workbench-build", "--out", str(DATA), "--check"]) == 0


def test_close_tolerates_float_noise_only():
    assert _close({"a": [0.1234, 1], "bundle_sha256": "x"}, {"a": [0.1240, 1], "bundle_sha256": "y"})
    assert not _close({"a": [0.12]}, {"a": [0.13]})
    assert not _close({"a": "x"}, {"a": "y"})
    assert not _close({"a": 1}, {"b": 1})


def test_index_lists_every_dataset():
    index = load_path(DATA / "index.json")
    assert [d["dataset_id"] for d in index["datasets"]] == [s.dataset_id for s in DATASETS]
    assert sorted(BUNDLES) == sorted(s.dataset_id for s in DATASETS)


@pytest.mark.parametrize("dataset_id", sorted(BUNDLES))
def test_bundle_documents_validate_and_are_disclosed(dataset_id):
    bundle = BUNDLES[dataset_id]
    schemas = default_schema_set()
    for doc in bundle["documents"].values():
        schemas.validate(doc)
    for entry in bundle["decisions"].values():
        schemas.validate(entry["task"], "task")
        schemas.validate(entry["evidence"], "evidence_bundle")
        schemas.validate(entry["decision"], "task_decision")
    schemas.validate(bundle["recommendation"], "recommendation")
    manifest = bundle["manifest"]
    assert manifest["synthetic"] is True and manifest["computed"] == "build_time"
    assert manifest["bundle_sha256"] == sha256_of({k: v for k, v in bundle.items() if k != "manifest"})
    assert manifest["snapshot_sha256"] == generate(next(s for s in DATASETS if s.dataset_id == dataset_id)).sha256


def _verdicts(dataset_id):
    return {k: v["decision"]["verdict"] for k, v in BUNDLES[dataset_id]["decisions"].items()}


def test_router_verdicts_follow_the_data_and_policies():
    # Too few positive labels to train: provisional, with the reason, and no model is built.
    b2b = BUNDLES["b2b_accounts"]
    assert _verdicts("b2b_accounts")["propensity"] == "PROVISIONAL"
    assert [r["code"] for r in b2b["decisions"]["propensity"]["decision"]["reasons"]] == [
        "unsupported_outcome_probability"
    ]
    assert "propensity" not in b2b["results"]
    # The clean room forbids row-level export but permits the aggregate report.
    acr = _verdicts("acr_tv")
    assert acr["export_rows"] == "BLOCKED" and acr["export_aggregate"] == "ELIGIBLE"
    assert BUNDLES["acr_tv"]["aggregate_rules"]["min_distinct_count"] == 50
    # Everything else in the samples is eligible, including the registered model.
    for dataset_id in BUNDLES:
        for key, verdict in _verdicts(dataset_id).items():
            if (dataset_id, key) not in {("b2b_accounts", "propensity"), ("acr_tv", "export_rows")}:
                assert verdict == "ELIGIBLE", (dataset_id, key)


@pytest.mark.parametrize("dataset_id", sorted(BUNDLES))
def test_models_exist_only_for_eligible_methods(dataset_id):
    bundle = BUNDLES[dataset_id]
    eligible = {
        k for k, v in bundle["decisions"].items() if v["role"] == "method" and v["decision"]["verdict"] == "ELIGIBLE"
    }
    assert set(bundle["results"]) == eligible


def test_sensitive_attributes_never_reach_a_model():
    bundle = BUNDLES["demo_firmo"]
    assert bundle["assessment"]["sensitive_excluded"] == ["health_condition_inferred"]
    for result in bundle["results"].values():
        assert "health_condition_inferred" not in result["features"]
        for model in result["models"]:
            for drivers in model["drivers"].values():
                assert all(d["feature"] != "health_condition_inferred" for d in drivers)


@pytest.mark.parametrize("dataset_id", sorted(BUNDLES))
def test_scores_cover_every_row_and_fit_rows_are_not_scored(dataset_id):
    bundle = BUNDLES[dataset_id]
    rows = bundle["dataset"]["rows"]
    assert len(bundle["dataset"]["breakdown"]["codes"]) == rows
    for method, result in bundle["results"].items():
        for model in result["models"]:
            assert len(model["scores"]) == rows
            assert all(s is None or (isinstance(s, float) and math.isfinite(s)) for s in model["scores"])
        if method in ("lookalike", "actalike"):
            scored = sum(s is not None for s in result["models"][0]["scores"])
            abstained = sum(result["models"][0]["abstained"].values())
            assert scored + abstained + result["fit_count"] == rows  # seed rows used for fitting are excluded
            # Held-out rows were never fit on, so only an abstention leaves one unscored.
            unscored_held = sum(result["models"][0]["scores"][i] is None for i in result["heldout"])
            assert unscored_held <= abstained


@pytest.mark.parametrize("dataset_id", sorted(BUNDLES))
def test_models_beat_random_on_held_out_data(dataset_id):
    for method, result in BUNDLES[dataset_id]["results"].items():
        best = next(m for m in result["models"] if m["model_id"] == result["recommended"]["model_id"])
        evaluation = best["evaluation"]
        if "recall_at" in evaluation:
            assert evaluation["recall_at"]["0.1"] > 0.1 * 1.5, (method, evaluation["recall_at"])
            assert list(evaluation["recall_at"]) == [str(r) for r in REACH_GRID]
        else:
            assert evaluation["average_precision"] > 2 * evaluation["base_rate"], method


@pytest.mark.parametrize("dataset_id", sorted(BUNDLES))
def test_recommended_model_is_the_best_held_out(dataset_id):
    for method, result in BUNDLES[dataset_id]["results"].items():

        def quality(m):
            e = m["evaluation"]
            return e["recall_at"]["0.1"] if "recall_at" in e else e["average_precision"]

        best = max(quality(m) for m in result["models"])
        chosen = next(m for m in result["models"] if m["model_id"] == result["recommended"]["model_id"])
        assert quality(chosen) == best, method


def test_generation_is_deterministic():
    spec = DATASETS[0]
    assert generate(spec).sha256 == generate(spec).sha256


def test_every_open_dataset_has_a_universe_scored_by_every_built_method():
    index = load_path(DATA / "index.json")
    for entry in index["datasets"]:
        bundle, universe = BUNDLES[entry["dataset_id"]], UNIVERSES.get(entry["dataset_id"])
        if entry["dataset_id"] == "geo_areas":
            # postal areas are a closed set: nothing new to expand into
            assert entry["universe"] is None and universe is None
            continue
        assert universe is not None and entry["universe"]["rows"] == universe["rows"]
        assert set(universe["expansions"]) == set(bundle["results"])
        assert len(universe["breakdown_codes"]) == universe["rows"]
        for method, expansion in universe["expansions"].items():
            built = [m["model_id"] for m in bundle["results"][method]["models"]]
            assert [m["model_id"] for m in expansion["models"]] == built
            for model in expansion["models"]:
                assert len(model["scores"]) == universe["rows"]
                assert sum(s is not None for s in model["scores"]) > 0.5 * universe["rows"]


@pytest.mark.parametrize("dataset_id", ["crm", "url_content"])
def test_expand_reproduces_the_built_scores_on_the_dataset_itself(dataset_id):
    import numpy as np

    from aip.workbench import methods

    spec = next(s for s in DATASETS if s.dataset_id == dataset_id)
    data = generate(spec)
    for method in ("byom", "semantic"):
        if method not in spec.methods:
            continue
        built = methods.byom(data) if method == "byom" else methods.semantic(data)
        again = methods.expand(data, method, data.x, np.zeros(spec.n, dtype=bool))
        assert again["models"][0]["scores"] == built["models"][0]["scores"]
