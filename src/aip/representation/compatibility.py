"""Representation compatibility (FR24). Matching dimensions alone never establishes compatibility."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from aip.policy.compose import Outcome
from aip.timeutil import parse_ts

DIRECT_FIELDS = (
    "model_id",
    "model_family",
    "model_revision",
    "space_id",
    "dimensions",
    "encoding",
    "normalization",
    "distance_metric",
    "transformation_version",
)
PID = "P-REPRESENTATION-COMPATIBLE"


def _valid_at(descriptor: Mapping[str, Any], at: datetime) -> bool:
    window = descriptor["time_validity"]
    end = window["valid_until"]
    return parse_ts(window["valid_from"]) <= at and (end is None or at < parse_ts(end))


def check_compatibility(a: Mapping[str, Any], b: Mapping[str, Any], at: datetime) -> Outcome:
    if "nonsemantic" in (a["representation_semantics"], b["representation_semantics"]):
        return Outcome(
            PID,
            "violated",
            "representation_nonsemantic",
            detail="pseudo or nonsemantic vectors cannot support semantic similarity",
        )
    if not (_valid_at(a, at) and _valid_at(b, at)):
        return Outcome(PID, "violated", "representation_expired")
    if all(a[f] == b[f] for f in DIRECT_FIELDS):
        return Outcome(PID, "satisfied", None, (a["descriptor_id"], b["descriptor_id"]), detail="direct")
    for src in (a, b):
        alignment = src["alignment"]
        if alignment["route"] == "projector" and alignment["projector_ref"] and alignment["alignment_evidence_ref"]:
            return Outcome(
                PID,
                "satisfied",
                None,
                (alignment["projector_ref"]["id"], alignment["alignment_evidence_ref"]["id"]),
                detail="projector with held-out alignment evidence",
            )
    differing = [f for f in DIRECT_FIELDS if a[f] != b[f]]
    return Outcome(PID, "violated", "representation_incompatible", detail="differs on " + ", ".join(differing))
