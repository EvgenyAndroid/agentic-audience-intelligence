"""Wrap raw model output as an advisory agent_proposal document (FR38)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from aip.contracts.validator import default_schema_set
from aip.registry.reason_codes import ReasonCodeRegistry
from aip.timeutil import format_ts


def make_proposal(
    *,
    proposal_id: str,
    task_ref: Mapping[str, str],
    role: str,
    provider: str,
    model_id: str,
    prompt_template_ref: Mapping[str, str],
    input_refs: Sequence[Mapping[str, str]],
    raw: Mapping[str, Any],
    reasons: ReasonCodeRegistry,
    now: datetime,
    usage_record_ref: str | None = None,
) -> dict[str, Any]:
    proposed_reasons = [dict(r) for r in raw.get("proposed_reasons", [])]
    for reason in proposed_reasons:
        reasons.require(reason["code"], "task_decision")  # unknown or wrong-dimension codes are rejected
    proposal = {
        "kind": "agent_proposal",
        "schema_version": "1.0.0",
        "proposal_id": proposal_id,
        "task_ref": dict(task_ref),
        "role": role,
        "model": {"provider": provider, "model_id": model_id, "revision": None},
        "prompt_template_ref": dict(prompt_template_ref),
        "input_refs": [dict(r) for r in input_refs],
        "proposed_verdict": raw["proposed_verdict"],
        "proposed_reasons": proposed_reasons,
        "proposed_next_actions": list(raw.get("proposed_next_actions", [])),
        "proposed_artifacts": [],
        "authority": "advisory",
        "usage_record_ref": usage_record_ref,
        "created_at": format_ts(now),
    }
    default_schema_set().validate(proposal, "agent_proposal")
    return proposal
