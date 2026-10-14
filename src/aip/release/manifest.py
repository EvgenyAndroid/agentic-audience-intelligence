"""Prepared releases, reviewer authorization and commit-time rechecks (FR15, FR16, FR18)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from typing import Any

from aip.canonical import sha256_of
from aip.contracts.validator import default_schema_set
from aip.routing.router import is_decision_current
from aip.timeutil import format_ts, parse_ts


class CommitError(RuntimeError):
    """The release cannot be committed as prepared; a new prepared version or decision is required."""


def prepare_release(
    *,
    release_id: str,
    release_version: str,
    tenant_id: str,
    artifacts: Sequence[tuple[Mapping[str, str], str, Any]],
    evidence_card_ref: Mapping[str, str],
    decision: Mapping[str, Any],
    populations: Sequence[Mapping[str, Any]],
    destination_ref: str | None,
    expires_at: datetime,
    prepared_by: Mapping[str, str],
    now: datetime,
) -> dict[str, Any]:
    if decision["verdict"] != "ELIGIBLE":
        raise CommitError(f"release task verdict is {decision['verdict']}, not ELIGIBLE")
    entries = [
        {"artifact_ref": dict(ref), "artifact_type": a_type, "sha256": sha256_of(payload)}
        for ref, a_type, payload in artifacts
    ]
    policy_versions = [dict(p) for p in decision["policy_versions"]]
    manifest = {
        "kind": "release_manifest",
        "schema_version": "1.0.0",
        "release_id": release_id,
        "release_version": release_version,
        "tenant_id": tenant_id,
        "artifacts": entries,
        "content_checksum": sha256_of(
            {
                "artifacts": [e["sha256"] for e in entries],
                "policy_versions": policy_versions,
                "destination_ref": destination_ref,
            }
        ),
        "evidence_card_ref": dict(evidence_card_ref),
        "task_decision_ref": decision["decision_id"],
        "populations": [dict(p) for p in populations],
        "policy_versions": policy_versions,
        "destination_ref": destination_ref,
        "expires_at": format_ts(expires_at),
        "lifecycle_state": "prepared",
        "prepared_by": dict(prepared_by),
        "prepared_at": format_ts(now),
    }
    default_schema_set().validate(manifest, "release_manifest")
    return manifest


def authorize(
    manifest: Mapping[str, Any],
    *,
    authorization_id: str,
    reviewer: Mapping[str, str],
    decision: str,
    purpose: str,
    valid_from: datetime,
    valid_until: datetime,
    now: datetime,
    notes: str | None = None,
) -> dict[str, Any]:
    record = {
        "kind": "authorization",
        "schema_version": "1.0.0",
        "authorization_id": authorization_id,
        "release_ref": {"id": manifest["release_id"], "version": manifest["release_version"]},
        "release_checksum": manifest["content_checksum"],
        "decision": decision,
        "destination_ref": manifest["destination_ref"],
        "purpose": purpose,
        "policy_versions": manifest["policy_versions"],
        "authorized_by": dict(reviewer),
        "authorized_at": format_ts(now),
        "valid_from": format_ts(valid_from),
        "valid_until": format_ts(valid_until),
        "notes": notes,
    }
    default_schema_set().validate(record, "authorization")  # rejects non-human reviewers
    return record


def commit(
    manifest: Mapping[str, Any],
    authorization: Mapping[str, Any],
    decision: Mapping[str, Any],
    *,
    now: datetime,
    current_policy_versions: Sequence[Mapping[str, str]],
    member_keys: Iterable[str],
    suppressed_keys: Iterable[str],
) -> None:
    """Raise CommitError unless every commit-time recheck passes; the caller then records the release."""
    if authorization["decision"] != "approved":
        raise CommitError("authorization is not an approval")
    if authorization["release_checksum"] != manifest["content_checksum"]:
        raise CommitError("authorization is bound to a different prepared checksum")
    if authorization["destination_ref"] != manifest["destination_ref"]:
        raise CommitError("authorization destination differs from the prepared destination")
    if not parse_ts(authorization["valid_from"]) <= now < parse_ts(authorization["valid_until"]):
        raise CommitError("authorization is outside its validity window")
    if now >= parse_ts(manifest["expires_at"]):
        raise CommitError("prepared release has expired")
    if decision["decision_id"] != manifest["task_decision_ref"] or decision["verdict"] != "ELIGIBLE":
        raise CommitError("release decision is missing or not ELIGIBLE")
    if not is_decision_current(decision, now, current_policy_versions):
        raise CommitError("release decision lapsed or a bound policy changed; reassess before commit")
    newly_suppressed = set(member_keys) & set(suppressed_keys)
    if newly_suppressed:
        raise CommitError(f"{len(newly_suppressed)} member(s) now suppressed; prepare a new version")
