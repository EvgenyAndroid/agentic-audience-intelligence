"""Task router: assembles the authoritative task decision (FR25, FR38, FR39).

Precedence: any violated prerequisite -> BLOCKED; else any missing -> PROVISIONAL; else ELIGIBLE.
Agent proposals may be referenced for audit but never change the verdict.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from aip import SERVICE_VERSION
from aip.canonical import sha256_of
from aip.contracts.validator import SchemaSet, default_schema_set
from aip.registry.documents import DocumentIndex
from aip.registry.reason_codes import ReasonCodeRegistry
from aip.registry.types import TypeRegistry
from aip.routing.checks import RoutingContext
from aip.routing.prerequisites import CATALOG, required_prerequisites
from aip.timeutil import format_ts, parse_ts

CONTRACT_VERSION = {"id": "aip-contracts", "version": "1.0.0"}


@dataclass(frozen=True)
class RouterConfig:
    max_decision_ttl: timedelta  # required: the platform supplies no default validity period
    service_id: str = "aip-task-router"
    service_version: str = SERVICE_VERSION


def decide(
    task: dict[str, Any],
    *,
    documents: DocumentIndex,
    bundle: dict[str, Any] | None,
    types: TypeRegistry,
    reasons: ReasonCodeRegistry,
    config: RouterConfig,
    now: datetime,
    agent_proposal_refs: Sequence[str] = (),
    supersedes: str | None = None,
    schemas: SchemaSet | None = None,
) -> dict[str, Any]:
    schemas = schemas or default_schema_set()
    facts: dict[str, dict[str, Any]] = {}
    if bundle is not None:
        schemas.validate(bundle, "evidence_bundle")
        if bundle["task_ref"] != {"id": task.get("task_id"), "version": task.get("task_version")}:
            raise ValueError("evidence bundle does not belong to this task version")
        facts = {f["prerequisite_id"]: f for f in bundle["facts"]}

    ctx = RoutingContext(task, documents, facts, types, schemas, now)
    outcomes = [ctx.evaluate(pid) for pid in required_prerequisites(task)]
    for o in outcomes:
        if o.outcome != "satisfied":
            reasons.require(o.reason_code or "", "task_decision", o.outcome)

    if any(o.outcome == "violated" for o in outcomes):
        verdict = "BLOCKED"
    elif any(o.outcome == "missing" for o in outcomes):
        verdict = "PROVISIONAL"
    else:
        verdict = "ELIGIBLE"

    ordered = [o for o in outcomes if o.outcome == "violated"] + [o for o in outcomes if o.outcome == "missing"]
    reason_list, seen = [], set()
    for o in ordered:
        canonical = reasons.resolve(o.reason_code or "").code
        if canonical not in seen:
            seen.add(canonical)
            reason_list.append(
                {
                    "code": canonical,
                    "detail": o.detail or CATALOG[o.prerequisite_id].description,
                    "evidence_refs": list(o.evidence_refs),
                }
            )
    next_actions = list(dict.fromkeys(CATALOG[o.prerequisite_id].remedy for o in ordered))

    ttl_end = now + config.max_decision_ttl
    bounds = [
        parse_ts(p["effective_until"])
        for p in ctx.policies_used.values()
        if p["effective_until"] and parse_ts(p["effective_until"]) > now
    ]
    valid_until = min([ttl_end, *bounds])
    policy_versions = [{"id": pid, "version": ver} for pid, ver in sorted(ctx.policies_used)]

    decision = {
        "kind": "task_decision",
        "schema_version": "1.0.0",
        "decision_id": f"dec_{task['task_id']}_{task['task_version']}_{now.strftime('%Y%m%dT%H%M%SZ')}",
        "task_ref": {"id": task["task_id"], "version": task["task_version"]},
        "task_checksum": sha256_of(task),
        "verdict": verdict,
        "prerequisites": [
            {
                "prerequisite_id": o.prerequisite_id,
                "outcome": o.outcome,
                "established_by": o.established_by,
                "check_ref": f"{config.service_id}:{o.prerequisite_id}",
                "evidence_refs": list(o.evidence_refs),
                "reason_code": reasons.resolve(o.reason_code).code if o.reason_code else None,
            }
            for o in outcomes
        ],
        "reasons": reason_list,
        "next_actions": next_actions,
        "decided_at": format_ts(now),
        "valid_until": format_ts(valid_until),
        "validity_basis": ["max_decision_ttl"] + [f"{p['id']}@{p['version']}" for p in policy_versions],
        "policy_versions": policy_versions,
        "contract_versions": [CONTRACT_VERSION],
        "supersedes": supersedes,
        "agent_proposal_refs": list(agent_proposal_refs),
        "decided_by": {
            "service_id": config.service_id,
            "service_version": config.service_version,
            "authority": "router",
        },
    }
    schemas.validate(decision, "task_decision")
    return decision


def is_decision_current(
    decision: Mapping[str, Any], now: datetime, current_policy_versions: Sequence[Mapping[str, str]]
) -> bool:
    """A decision lapses at valid_until or when any bound policy version changes (FR39, NFR06)."""
    if now >= parse_ts(decision["valid_until"]):
        return False
    bound = {(p["id"], p["version"]) for p in decision["policy_versions"]}
    current = {(p["id"], p["version"]) for p in current_policy_versions}
    return bound <= current
