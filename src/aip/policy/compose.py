"""Policy composition across lineage (FR27, FR28, FR29).

Rules: every contributing source must permit an operation; any prohibition wins; silence is
missing evidence, never permission; contradictory statements within one source block the task.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from aip.timeutil import parse_ts

OutcomeValue = Literal["satisfied", "missing", "violated"]
ROW_LEVEL_ARTIFACTS = {"score_file", "cohort_membership", "feature_snapshot"}


@dataclass(frozen=True)
class Outcome:
    prerequisite_id: str
    outcome: OutcomeValue
    reason_code: str | None = None
    evidence_refs: tuple[str, ...] = ()
    established_by: str = "deterministic_check"
    detail: str = ""


@dataclass(frozen=True)
class AggregateRule:
    unit_key: tuple[str, str]
    min_distinct_count: int
    block_on_small_cell: bool
    approved_dimensions: frozenset[str]
    rule_ids: tuple[str, ...] = field(default=())


def combine(prerequisite_id: str, outcomes: Sequence[Outcome]) -> Outcome:
    for value in ("violated", "missing"):
        hits = [o for o in outcomes if o.outcome == value]
        if hits:
            refs = tuple(r for o in hits for r in o.evidence_refs)
            return Outcome(
                prerequisite_id, value, hits[0].reason_code, refs, detail="; ".join(o.detail for o in hits if o.detail)
            )
    return Outcome(prerequisite_id, "satisfied", None, tuple(r for o in outcomes for r in o.evidence_refs))


def _active(policy: Mapping[str, Any], at: datetime) -> bool:
    start = parse_ts(policy["effective_from"])
    end = policy["effective_until"]
    return start <= at and (end is None or at < parse_ts(end))


def _policy_ref(policy: Mapping[str, Any]) -> str:
    return f"{policy['policy_id']}@{policy['policy_version']}"


def operation_permission(
    policies_by_source: Mapping[str, Sequence[Mapping[str, Any]]], location_id: str, operation: str, at: datetime
) -> Outcome:
    pid = "P-EXEC-OPERATION"
    if not policies_by_source:
        return Outcome(pid, "missing", "missing_execution_policy", detail="no contributing sources")
    per_source = []
    for source, policies in policies_by_source.items():
        located = [p for p in policies if any(loc["location_id"] == location_id for loc in p["locations"])]
        active = [p for p in located if _active(p, at)]
        if located and not active:
            per_source.append(
                Outcome(pid, "missing", "policy_not_current", tuple(map(_policy_ref, located)), detail=source)
            )
            continue
        stated = {
            (op["permission"], _policy_ref(p)) for p in active for op in p["operations"] if op["operation"] == operation
        }
        permissions = {perm for perm, _ in stated}
        refs = tuple(sorted(ref for _, ref in stated))
        if permissions == {"permitted", "prohibited"}:
            per_source.append(Outcome(pid, "violated", "contradictory_policies", refs, detail=source))
        elif "prohibited" in permissions:
            per_source.append(Outcome(pid, "violated", "forbidden_operation", refs, detail=source))
        elif "permitted" in permissions:
            per_source.append(Outcome(pid, "satisfied", None, refs))
        else:
            per_source.append(
                Outcome(pid, "missing", "missing_execution_policy", tuple(map(_policy_ref, active)), detail=source)
            )
    return combine(pid, per_source)


def artifact_permission(
    policies_by_source: Mapping[str, Sequence[Mapping[str, Any]]],
    location_id: str,
    artifact_type: str,
    output_type_id: str | None,
    destination_ref: str | None,
    at: datetime,
) -> Outcome:
    pid = "P-OUTPUT-ARTIFACT"
    if not policies_by_source:
        return Outcome(pid, "missing", "missing_output_policy", detail="no contributing sources")
    per_source = []
    for source, policies in policies_by_source.items():
        located = [p for p in policies if location_id in p["applies_to_locations"]]
        active = [p for p in located if _active(p, at)]
        if located and not active:
            per_source.append(
                Outcome(pid, "missing", "policy_not_current", tuple(map(_policy_ref, located)), detail=source)
            )
            continue
        rules = [
            (r, _policy_ref(p)) for p in active for r in p["artifact_rules"] if r["artifact_type"] == artifact_type
        ]
        if not rules:
            per_source.append(Outcome(pid, "missing", "missing_output_policy", detail=source))
            continue
        refs = tuple(sorted({ref for _, ref in rules}))
        permissions = {r["permission"] for r, _ in rules}
        if permissions == {"permitted", "prohibited"}:
            per_source.append(Outcome(pid, "violated", "contradictory_policies", refs, detail=source))
        elif "prohibited" in permissions:
            code = "forbidden_row_level_egress" if artifact_type in ROW_LEVEL_ARTIFACTS else "forbidden_artifact_egress"
            per_source.append(Outcome(pid, "violated", code, refs, detail=source))
        else:
            violations = []
            for rule, _ in rules:
                allowed_types = rule["permitted_output_type_ids"]
                if allowed_types and output_type_id not in allowed_types:
                    violations.append(Outcome(pid, "violated", "output_grain_not_permitted", refs, detail=source))
                allowed_dest = rule["permitted_destinations"]
                if destination_ref is not None and allowed_dest and destination_ref not in allowed_dest:
                    violations.append(Outcome(pid, "violated", "destination_not_permitted", refs, detail=source))
            per_source.append(violations[0] if violations else Outcome(pid, "satisfied", None, refs))
    return combine(pid, per_source)


def compose_aggregation_rules(
    policies: Sequence[Mapping[str, Any]], artifact_type: str, at: datetime, location_id: str | None = None
) -> list[AggregateRule]:
    """Most restrictive composition per counted unit: max threshold, block beats suppress, intersect dimensions.

    With location_id, only policies that apply at that location contribute.
    """
    merged: dict[tuple[str, str], AggregateRule] = {}
    for policy in policies:
        if not _active(policy, at):
            continue
        if location_id is not None and location_id not in policy["applies_to_locations"]:
            continue
        for rule in policy["aggregation_rules"]:
            if artifact_type not in rule["applies_to"]:
                continue
            key = (rule["counted_unit"]["type_id"], rule["counted_unit"]["namespace"])
            current = AggregateRule(
                key,
                rule["min_distinct_count"],
                rule["small_cell_handling"] == "block_release",
                frozenset(rule["approved_dimensions"]),
                (rule["rule_id"],),
            )
            if key in merged:
                old = merged[key]
                current = AggregateRule(
                    key,
                    max(old.min_distinct_count, current.min_distinct_count),
                    old.block_on_small_cell or current.block_on_small_cell,
                    old.approved_dimensions & current.approved_dimensions,
                    old.rule_ids + current.rule_ids,
                )
            merged[key] = current
    return list(merged.values())


def check_aggregate_release(
    cells: Sequence[Mapping[str, Any]], rules: Sequence[AggregateRule]
) -> tuple[Outcome, list[Mapping[str, Any]]]:
    """Each cell: {"dimensions": {name: value}, "distinct_counts": {"type_id|namespace": int}}.

    Returns the threshold outcome and the releasable cells (small cells suppressed where permitted).
    """
    pid = "P-AGGREGATION-THRESHOLD"
    refs = tuple(r for rule in rules for r in rule.rule_ids)
    if not rules:
        return Outcome(pid, "missing", "aggregation_rules_unknown"), []
    approved = rules[0].approved_dimensions
    for rule in rules[1:]:
        approved = approved & rule.approved_dimensions
    releasable = []
    for cell in cells:
        unapproved = set(cell["dimensions"]) - approved
        if unapproved:
            return Outcome(pid, "violated", "dimension_not_approved", refs, detail=", ".join(sorted(unapproved))), []
        small = False
        for rule in rules:
            count = cell["distinct_counts"].get(f"{rule.unit_key[0]}|{rule.unit_key[1]}")
            if count is None:
                return Outcome(pid, "missing", "aggregate_counts_unavailable", refs), []
            if count < rule.min_distinct_count:
                if rule.block_on_small_cell:
                    return Outcome(pid, "violated", "aggregation_threshold_not_met", refs), []
                small = True
        if not small:
            releasable.append(cell)
    if not releasable:
        return Outcome(pid, "violated", "aggregation_threshold_not_met", refs, detail="every cell suppressed"), []
    suppressed = len(cells) - len(releasable)
    return Outcome(pid, "satisfied", None, refs, detail=f"{suppressed} cell(s) suppressed"), releasable
