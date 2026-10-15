"""Demonstrator bundles: reproducible, honest about what they are, and consistent with the engine."""

import hashlib

import pytest
from conftest import ROOT

from aip.canonical import canonical_bytes, load_path, sha256_of
from aip.cli import main
from aip.contracts.validator import default_schema_set
from aip.recommendation import admissibility_issues
from aip.timeutil import parse_ts

DATA = ROOT / "app" / "data"
BUNDLES = sorted(p for p in DATA.glob("*.json") if p.name != "index.json")


def test_committed_bundles_match_a_fresh_build():
    assert main(["demo-build", "--out", str(DATA), "--check"]) == 0


def test_index_lists_every_bundle():
    index = load_path(DATA / "index.json")
    assert sorted(s["file"] for s in index["scenarios"]) == sorted(p.name for p in BUNDLES)
    assert len(BUNDLES) == 4


@pytest.mark.parametrize("path", BUNDLES, ids=lambda p: p.stem)
def test_bundle_is_disclosed_and_consistent(path):
    bundle = load_path(path)
    manifest = bundle["manifest"]
    assert manifest["synthetic"] is True and manifest["computed"] == "build_time"
    assert "nothing runs while you browse" in manifest["disclosure"]
    assert manifest["bundle_sha256"] == sha256_of({k: v for k, v in bundle.items() if k != "manifest"})
    for entry in manifest["inputs"]:
        digest = "sha256:" + hashlib.sha256(canonical_bytes(load_path(ROOT / entry["path"]))).hexdigest()
        assert digest == entry["sha256"], entry["path"]

    schemas = default_schema_set()
    decisions = {}
    for row in bundle["tasks"]:
        schemas.validate(row["decision"], "task_decision")
        decisions[row["decision"]["decision_id"]] = row["decision"]
        for reason in row["decision"]["reasons"]:
            assert reason["code"] in bundle["reason_codes"]
    rec = bundle["recommendation"]
    schemas.validate(rec, "recommendation")
    assert admissibility_issues(rec, decisions, parse_ts(manifest["evaluated_at"])) == []
    assert rec["requested_task"]["task_ref"]["id"] == bundle["scenario"]["requested_task"]


def test_synthetic_scores_only_for_an_eligible_lookalike_and_denominators_include_abstentions():
    bundle = load_path(DATA / "web_lookalike.json")
    look = bundle["lookalike"]
    verdicts = {r["task"]["task_id"]: r["decision"]["verdict"] for r in bundle["tasks"]}
    assert verdicts[look["task_id"]] == "ELIGIBLE" and look["claim"] == "exploratory"
    for method in look["methods"]:
        assert method["scored"] + sum(method["abstained"].values()) == method["pool"]
        held = method["heldout_seed"]
        assert held["recall_all"] == round(held["found_in_selection"] / held["total"], 4)
        assert held["recall_all"] <= held["recall_scored_only"]
    others = [load_path(p)["lookalike"] for p in BUNDLES if p.stem != "web_lookalike"]
    assert others == [None, None, None]


def test_blocked_request_with_eligible_alternative_in_the_clean_room():
    rec = load_path(DATA / "acr_clean_room.json")["recommendation"]
    assert rec["requested_task"]["verdict"] == "BLOCKED"
    assert [o["fit"] for o in rec["recommended_options"]] == ["alternative"]
    assert "forbidden_row_level_egress" in rec["blocked_options"][0]["reason_codes"]
