import copy
from datetime import UTC, datetime

from conftest import NOW, registry_doc

from aip.policy import artifact_permission, check_aggregate_release, compose_aggregation_rules, operation_permission

EXEC_CR = registry_doc("policies/exec_cleanroom_demo")
OUT_CR = registry_doc("policies/output_cleanroom_aggregate_only")
HH = "provider_household_key|acr_demo_hh"


def test_every_source_must_permit_and_prohibition_wins():
    permissive = copy.deepcopy(EXEC_CR)
    permissive["policy_id"] = "other"
    for op in permissive["operations"]:
        op["permission"] = "permitted"
    out = operation_permission({"a": [EXEC_CR], "b": [permissive]}, "loc_cleanroom_demo", "export_rows", NOW)
    assert out.outcome == "violated" and out.reason_code == "forbidden_operation"


def test_contradiction_within_one_source_blocks():
    flipped = copy.deepcopy(EXEC_CR)
    flipped["policy_id"] = "flipped"
    for op in flipped["operations"]:
        if op["operation"] == "train":
            op["permission"] = "prohibited"
    out = operation_permission({"a": [EXEC_CR, flipped]}, "loc_cleanroom_demo", "train", NOW)
    assert out.outcome == "violated" and out.reason_code == "contradictory_policies"


def test_silence_is_missing_not_permission():
    out = operation_permission({"a": [EXEC_CR]}, "loc_cleanroom_demo", "calibrate", NOW)
    assert out.outcome == "missing" and out.reason_code == "missing_execution_policy"


def test_expired_policy_is_not_current():
    later = datetime(2027, 2, 1, tzinfo=UTC)
    out = operation_permission({"a": [EXEC_CR]}, "loc_cleanroom_demo", "train", later)
    assert out.outcome == "missing" and out.reason_code == "policy_not_current"


def test_row_level_artifact_is_forbidden_egress():
    out = artifact_permission(
        {"a": [OUT_CR]}, "loc_cleanroom_demo", "score_file", "provider_household_key", "dest_demo_dsp", NOW
    )
    assert out.reason_code == "forbidden_row_level_egress"


def test_aggregation_composition_is_most_restrictive():
    stricter = copy.deepcopy(OUT_CR)
    stricter["policy_id"] = "stricter"
    stricter["aggregation_rules"][0].update(
        min_distinct_count=100, small_cell_handling="block_release", approved_dimensions=["genre"]
    )
    [rule] = compose_aggregation_rules([OUT_CR, stricter], "aggregate_report", NOW)
    assert (
        rule.min_distinct_count == 100 and rule.block_on_small_cell and rule.approved_dimensions == frozenset({"genre"})
    )


def test_small_cells_are_suppressed_when_permitted():
    rules = compose_aggregation_rules([OUT_CR], "aggregate_report", NOW)
    cells = [
        {"dimensions": {"genre": "cooking"}, "distinct_counts": {HH: 120}},
        {"dimensions": {"genre": "opera"}, "distinct_counts": {HH: 7}},
    ]
    outcome, releasable = check_aggregate_release(cells, rules)
    assert outcome.outcome == "satisfied" and len(releasable) == 1


def test_threshold_failure_blocks_when_nothing_is_releasable():
    rules = compose_aggregation_rules([OUT_CR], "aggregate_report", NOW)
    outcome, _ = check_aggregate_release([{"dimensions": {"genre": "opera"}, "distinct_counts": {HH: 7}}], rules)
    assert outcome.outcome == "violated" and outcome.reason_code == "aggregation_threshold_not_met"


def test_unapproved_dimension_and_missing_counts():
    rules = compose_aggregation_rules([OUT_CR], "aggregate_report", NOW)
    bad_dim, _ = check_aggregate_release([{"dimensions": {"zip": "10001"}, "distinct_counts": {HH: 500}}], rules)
    no_count, _ = check_aggregate_release([{"dimensions": {"genre": "x"}, "distinct_counts": {}}], rules)
    assert bad_dim.reason_code == "dimension_not_approved" and no_count.reason_code == "aggregate_counts_unavailable"
    unknown, _ = check_aggregate_release([], [])
    assert unknown.outcome == "missing" and unknown.reason_code == "aggregation_rules_unknown"
