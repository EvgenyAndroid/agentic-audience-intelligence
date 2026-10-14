"""AdCP boundary adapter, pinned to AdCP schema 3.1.20 (commit d033baef, see third_party/adcp/adcp.lock.json).

The canonical platform does not depend on this module. Only fields defined by the pinned schema are
emitted; platform evidence without a standard field travels under ext.<namespace>. Building an
activation request is not delivery: acceptance is recorded only from a destination receipt.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal

from jsonschema import Draft7Validator

from aip import paths

ADCP_SCHEMA_VERSION = "3.1.20"
SCHEMA_FILES = {
    "get_signals_response": "get-signals-response.json",
    "activate_signal_request": "activate-signal-request.json",
}

# claim type -> (AdCP methodology, modeling.method, audience_expansion)
CLAIM_MAPPING: dict[str, tuple[str, str, bool]] = {
    "seed_affinity": ("modeled", "lookalike", True),
    "behavioral_affinity": ("modeled", "lookalike", True),
    "outcome_probability": ("modeled", "supervised", False),
    "semantic_similarity": ("derived", "embedding", False),
    "cohort_pattern": ("derived", "rules", False),
}
UNSUPPORTED_CLAIMS = {"aggregate_measurement", "observed_association", "experimental_effect"}


class UnsupportedMapping(ValueError):
    """The canonical artifact has no faithful AdCP signal representation; use referenced artifacts or abstain."""


@dataclass(frozen=True)
class AdcpListingConfig:
    signal_source_url: str
    signal_type: Literal["marketplace", "custom", "owned"]
    data_sources_by_profile: Mapping[
        str, Sequence[str]
    ]  # declared per provider contract; never guessed from family names
    evidence_card_url: str | None = None
    seed_source_type: str | None = None  # AdCP modeling is emitted only when the seed source is declared
    seed_provider_signed: bool = False
    training_data_jurisdictions: Sequence[str] = ()
    ai_act_risk_class: Literal["minimal", "limited", "high_risk"] | None = None
    ext_namespace: str = "aip"


@lru_cache(maxsize=4)
def _validator(name: str) -> Draft7Validator:
    folder = paths.repo_root() / "third_party" / "adcp"
    lock = json.loads((folder / "adcp.lock.json").read_text(encoding="utf-8"))
    rel = f"{ADCP_SCHEMA_VERSION}/{SCHEMA_FILES[name]}"
    raw = (folder / rel).read_bytes()
    if hashlib.sha256(raw).hexdigest() != lock["files"][rel]["sha256"]:
        raise RuntimeError(f"vendored AdCP schema {rel} does not match the lock file")
    return Draft7Validator(json.loads(raw.decode("utf-8")))


def validate_adcp(document: Mapping[str, Any], name: str) -> list[str]:
    return [
        f"{'/'.join(map(str, e.absolute_path)) or '/'}: {e.message}" for e in _validator(name).iter_errors(document)
    ]


def build_signal(
    manifest: Mapping[str, Any], card: Mapping[str, Any], objective: Mapping[str, Any], cfg: AdcpListingConfig
) -> dict[str, Any]:
    claim = card["claim"]["type"]
    if claim in UNSUPPORTED_CLAIMS or claim not in CLAIM_MAPPING:
        raise UnsupportedMapping(f"claim type {claim!r} is not an AdCP audience signal")
    methodology, method, expansion = CLAIM_MAPPING[claim]
    data_sources: set[str] = set()
    for source in card["source_profiles"]:
        declared = cfg.data_sources_by_profile.get(source["profile_ref"]["id"])
        if not declared:
            raise UnsupportedMapping(f"no declared AdCP data_sources for profile {source['profile_ref']['id']!r}")
        data_sources.update(declared)
    membership = any(a["artifact_type"] == "cohort_membership" for a in manifest["artifacts"])
    signal: dict[str, Any] = {
        "signal_agent_segment_id": f"{manifest['release_id']}:{manifest['release_version']}",
        "signal_ref": {
            "scope": "signal_source",
            "signal_source_url": cfg.signal_source_url,
            "signal_id": manifest["release_id"],
        },
        "name": objective["statement"][:200],
        "description": f"{claim.replace('_', ' ')} ({card['claim']['qualifier']}). Limits: "
        + "; ".join(card["limitations"]),
        "value_type": "binary" if membership else "numeric",
        "signal_type": cfg.signal_type,
        "deployments": [],
        "methodology": methodology,
        "audience_expansion": expansion,
        "data_sources": sorted(data_sources),
        "last_updated": card["issued_at"],
        "ext": {
            cfg.ext_namespace: {
                "claim": card["claim"],
                "modeling_method": method,
                "output_unit": card["output_unit"],
                "evidence_card_ref": {"id": card["card_id"], "version": card["card_version"]},
                "task_decision_ref": card["task_decision_ref"],
                "release_checksum": manifest["content_checksum"],
                "populations": card["populations"],
                "limitations": card["limitations"],
            }
        },
    }
    if not membership:
        signal["range"] = {"min": 0, "max": 1} if claim == "outcome_probability" else {"min": -1, "max": 1}
    if cfg.evidence_card_url:
        signal["methodology_url"] = cfg.evidence_card_url
    if cfg.seed_source_type and cfg.training_data_jurisdictions and cfg.ai_act_risk_class:
        signal["modeling"] = {
            "method": method,
            "seed_source": {"type": cfg.seed_source_type, "provider_signed": cfg.seed_provider_signed},
            "training_data_jurisdictions": list(cfg.training_data_jurisdictions),
            "ai_act_risk_class": cfg.ai_act_risk_class,
        }
    errors = validate_adcp(get_signals_response([signal], cache_scope="account"), "get_signals_response")
    if errors:
        raise UnsupportedMapping("generated signal fails the pinned AdCP schema: " + "; ".join(errors[:3]))
    return signal


def get_signals_response(
    signals: Sequence[Mapping[str, Any]], cache_scope: Literal["public", "account"]
) -> dict[str, Any]:
    """Minimal completed get_signals response envelope (status and cache_scope are required in 3.1.x)."""
    return {"status": "completed", "cache_scope": cache_scope, "signals": [dict(s) for s in signals]}


def build_activation_request(
    signal: Mapping[str, Any],
    destinations: Sequence[Mapping[str, Any]],
    idempotency_key: str,
    pricing_option_id: str | None = None,
) -> dict[str, Any]:
    request: dict[str, Any] = {
        "action": "activate",
        "signal_agent_segment_id": signal["signal_agent_segment_id"],
        "destinations": [dict(d) for d in destinations],
        "idempotency_key": idempotency_key,
    }
    if pricing_option_id:
        request["pricing_option_id"] = pricing_option_id
    errors = validate_adcp(request, "activate_signal_request")
    if errors:
        raise UnsupportedMapping("activation request fails the pinned AdCP schema: " + "; ".join(errors[:3]))
    return request
