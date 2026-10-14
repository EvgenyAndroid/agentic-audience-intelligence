"""Point-in-time checks (FR07): event time and availability time must both precede the cutoff."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any

from aip.policy.compose import Outcome
from aip.timeutil import parse_ts


def check_feature_rows(rows: Iterable[Mapping[str, Any]], cutoff: datetime) -> Outcome:
    """Rows carry event_time and available_at (contract timestamps). Returns the P-FEATURE-TIMING outcome."""
    late, unknown, total = 0, 0, 0
    for row in rows:
        total += 1
        if row.get("available_at") is None:
            unknown += 1
            continue
        if parse_ts(row["event_time"]) > cutoff or parse_ts(row["available_at"]) > cutoff:
            late += 1
    if late:
        return Outcome(
            "P-FEATURE-TIMING", "violated", "temporal_leakage", detail=f"{late} of {total} rows after cutoff"
        )
    if unknown:
        return Outcome(
            "P-FEATURE-TIMING", "missing", "missing_availability_evidence", detail=f"{unknown} rows lack available_at"
        )
    return Outcome("P-FEATURE-TIMING", "satisfied", detail=f"{total} rows checked")


def relationship_usable(relationship: Mapping[str, Any], use_time: datetime, cutoff: datetime) -> bool:
    """A relationship may enter a historical feature only if valid at use_time and known by the cutoff."""
    start = parse_ts(relationship["valid_from"])
    end = relationship["valid_until"]
    valid = start <= use_time and (end is None or use_time < parse_ts(end))
    return valid and parse_ts(relationship["available_at"]) <= cutoff
