"""Deterministic recommendations over current task decisions (FR46).

The requested task always keeps its own card and verdict. Only ELIGIBLE tasks are ranked; PROVISIONAL tasks are
listed with what would unlock them and BLOCKED tasks with their remedies. Task families answer different questions,
so there is no claim-strength ladder: alternatives are ordered only by known cost, and unknown cost is never zero.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from aip import SERVICE_VERSION
from aip.canonical import sha256_of
from aip.contracts.validator import default_schema_set
from aip.timeutil import format_ts, parse_ts

FAMILY_CLAIM = {
    "semantic_similarity": "semantic_similarity",
    "seed_affinity": "seed_affinity",
    "behavioral_affinity": "behavioral_affinity",
    "outcome_propensity": "outcome_probability",
    "cohort": "cohort_pattern",
    "aggregate_measurement": "aggregate_measurement",
}
TIER = {"requested": 0, "exact": 1, "alternative": 2}
SECTION = {"ELIGIBLE": "recommended_options", "PROVISIONAL": "unlock_options", "BLOCKED": "blocked_options"}
BASIS = (
    "The requested task is listed first. Eligible options matching the requested task family follow, then "
    "alternatives that answer a different question. Within a group, options are ordered by known cost only; "
    "options with unknown cost share a position."
)


@dataclass(frozen=True)
class Candidate:
    task: Mapping[str, Any]
    decision: Mapping[str, Any]
    cost: Mapping[str, Any] | None = None  # {"amount", "currency", "usage_record_refs"}; None means unknown


def _check(c: Candidate, objective: Mapping[str, Any], now: datetime) -> None:
    task, decision = c.task, c.decision
    if decision["task_ref"] != {"id": task["task_id"], "version": task["task_version"]}:
        raise ValueError(f"decision {decision['decision_id']} is not for task {task['task_id']}")
    if decision["task_checksum"] != sha256_of(task):
        raise ValueError(f"task {task['task_id']} changed after decision {decision['decision_id']}")
    if task["objective_ref"] != {"id": objective["objective_id"], "version": objective["objective_version"]}:
        raise ValueError(f"task {task['task_id']} belongs to another objective")
    if task["tenant_id"] != objective["tenant_id"]:
        raise ValueError(f"task {task['task_id']} belongs to another tenant")
    if now >= parse_ts(decision["valid_until"]):
        raise ValueError(f"decision {decision['decision_id']} has lapsed; reassess before recommending")


def _fit(c: Candidate, requested: Candidate, objective: Mapping[str, Any]) -> tuple[str, list[str]]:
    family = c.task["task_family"]
    claim_basis = ["accepted_claim"] if FAMILY_CLAIM.get(family) == objective["claim_sought"] else []
    if c is requested:
        return "requested", ["requested_task", *claim_basis]
    if family == objective["task_family"]:
        return "exact", ["requested_task_family", *claim_basis]
    return "alternative", ["different_question"]


def _cost(c: Candidate) -> dict[str, Any]:
    if c.cost is None:
        return {"status": "unknown"}
    return {"status": "known", **c.cost}


def _option(c: Candidate) -> dict[str, Any]:
    return {
        "task_ref": dict(c.decision["task_ref"]),
        "decision_ref": c.decision["decision_id"],
        "task_family": c.task["task_family"],
    }


def recommend(
    *,
    recommendation_id: str,
    objective: Mapping[str, Any],
    requested: Candidate,
    alternatives: Sequence[Candidate],
    now: datetime,
    service_version: str = SERVICE_VERSION,
) -> dict[str, Any]:
    candidates = [requested, *alternatives]
    for c in candidates:
        _check(c, objective, now)
    ids = [c.decision["decision_id"] for c in candidates]
    if len(set(ids)) != len(ids):
        raise ValueError("each candidate needs its own decision")

    eligible = [c for c in candidates if c.decision["verdict"] == "ELIGIBLE"]
    fits = {id(c): _fit(c, requested, objective) for c in eligible}

    def cost_key(c: Candidate) -> Decimal | None:
        return Decimal(c.cost["amount"]) if c.cost is not None else None

    recommended: list[dict[str, Any]] = []
    position, tie_seen = 0, False
    for tier in ("requested", "exact", "alternative"):
        group = [c for c in eligible if fits[id(c)][0] == tier]
        if not group:
            continue
        currencies = {c.cost["currency"] for c in group if c.cost is not None}
        comparable = all(c.cost is not None for c in group) and len(currencies) == 1
        if comparable:
            ordered = sorted(group, key=lambda c: (cost_key(c), c.decision["decision_id"]))
            last: Decimal | None = None
            for c in ordered:
                if cost_key(c) != last:
                    position += 1
                    last = cost_key(c)
                else:
                    tie_seen = True
                recommended.append({**_option(c), "position": position, "c": c})
        else:
            position += 1
            tie_seen = tie_seen or len(group) > 1
            for c in sorted(group, key=lambda c: c.decision["decision_id"]):
                recommended.append({**_option(c), "position": position, "c": c})
    for entry in recommended:
        c = entry.pop("c")
        fit, basis = fits[id(c)]
        entry.update(claim_type=FAMILY_CLAIM.get(c.task["task_family"], "cohort_pattern"), fit=fit, fit_basis=basis)
        entry["cost"] = _cost(c)

    if not eligible:
        status = "no_eligible_options"
    elif len(eligible) > 1 and all(e["position"] == 1 for e in recommended):
        status = "insufficient_evidence_to_rank"
    elif tie_seen:
        status = "partial_order"
    else:
        status = "ranked"

    def listed(verdict: str, extra: str) -> list[dict[str, Any]]:
        out = []
        for c in candidates:
            if c.decision["verdict"] == verdict:
                values = c.decision["next_actions"]
                out.append(
                    {**_option(c), "reason_codes": [r["code"] for r in c.decision["reasons"]], extra: list(values)}
                )
        return out

    recommendation = {
        "kind": "recommendation",
        "schema_version": "1.0.0",
        "recommendation_id": recommendation_id,
        "tenant_id": objective["tenant_id"],
        "objective_ref": {"id": objective["objective_id"], "version": objective["objective_version"]},
        "requested_task": {**_option(requested), "verdict": requested.decision["verdict"]},
        "recommended_options": recommended,
        "unlock_options": listed("PROVISIONAL", "next_actions"),
        "blocked_options": listed("BLOCKED", "remedies"),
        "ranking_status": status,
        "ranking_basis": BASIS,
        "decision_refs": ids,
        "generated_at": format_ts(now),
        "valid_until": format_ts(min(parse_ts(c.decision["valid_until"]) for c in candidates)),
        "generated_by": {
            "service_id": "aip-recommender",
            "service_version": service_version,
            "authority": "deterministic_ranker",
        },
    }
    default_schema_set().validate(recommendation, "recommendation")
    return recommendation


def admissibility_issues(
    recommendation: Mapping[str, Any], decisions: Mapping[str, Mapping[str, Any]], now: datetime
) -> list[str]:
    """Checks any proposed recommendation against current decisions. Admissible is not the same as optimal."""
    issues = []
    if now >= parse_ts(recommendation["valid_until"]):
        issues.append("recommendation has lapsed")
    cited = set(recommendation["decision_refs"])
    seen: dict[str, str] = {}
    for section in SECTION.values():
        for option in recommendation[section]:
            ref = option["decision_ref"]
            decision = decisions.get(ref)
            if ref not in cited or decision is None:
                issues.append(f"{ref}: decision not cited or not found")
                continue
            if SECTION[decision["verdict"]] != section:
                issues.append(f"{ref}: {decision['verdict']} decision listed under {section}")
            if now >= parse_ts(decision["valid_until"]):
                issues.append(f"{ref}: decision has lapsed")
            if ref in seen:
                issues.append(f"{ref}: listed in both {seen[ref]} and {section}")
            seen[ref] = section
    requested = recommendation["requested_task"]
    decision = decisions.get(requested["decision_ref"])
    if decision is None or decision["verdict"] != requested["verdict"]:
        issues.append("requested task verdict does not match its decision")
    if requested["decision_ref"] not in seen:
        issues.append("requested task is missing from its section")
    positions = [o["position"] for o in recommendation["recommended_options"]]
    if positions != sorted(positions):
        issues.append("recommended positions are not in order")
    return issues
