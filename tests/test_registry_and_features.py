from datetime import UTC, datetime

import pytest
from conftest import example

from aip.features import check_feature_rows, relationship_usable

CUTOFF = datetime(2026, 9, 30, tzinfo=UTC)


def test_reason_codes_have_one_dimension_and_resolve_aliases(reasons):
    assert reasons.resolve("leakage_detected").code == "temporal_leakage"
    assert reasons.require("unsupported_outcome_probability", "task_decision", "missing")
    with pytest.raises(ValueError):
        reasons.require("budget_exceeded", "task_decision")
    with pytest.raises(KeyError):
        reasons.resolve("not_a_code")


def test_type_registry_sets_grain_and_blocks_identifier_semantics(types):
    cookie = {"type_id": "browser_cookie", "type_version": "1.0.0", "namespace": "x"}
    assert types.grain(cookie) == "browser" and types.is_confirmed(cookie)
    assert not types.semantic_feature_allowed("browser_cookie", "1.0.0")
    assert not types.is_confirmed({"type_id": "acr_id", "type_version": "1.0.0", "namespace": "x"})


def test_late_availability_is_leakage_even_when_event_precedes_cutoff():
    rows = [{"event_time": "2026-09-29T00:00:00Z", "available_at": "2026-10-02T00:00:00Z"}]
    assert check_feature_rows(rows, CUTOFF).reason_code == "temporal_leakage"


def test_missing_availability_is_provisional_evidence():
    rows = [{"event_time": "2026-09-29T00:00:00Z", "available_at": None}]
    assert check_feature_rows(rows, CUTOFF).reason_code == "missing_availability_evidence"


def test_clean_rows_pass():
    rows = [{"event_time": "2026-09-01T00:00:00Z", "available_at": "2026-09-02T00:00:00Z"}]
    assert check_feature_rows(rows, CUTOFF).outcome == "satisfied"


def test_relationship_discovered_after_cutoff_is_unusable():
    rel = dict(example("relationship/relationship_browser_household"))
    assert relationship_usable(rel, datetime(2026, 9, 1, tzinfo=UTC), CUTOFF)
    rel["available_at"] = "2026-10-05T00:00:00Z"
    assert not relationship_usable(rel, datetime(2026, 9, 1, tzinfo=UTC), CUTOFF)
