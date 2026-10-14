"""Delivery retry policy (FR17): unknown remote state is reconciled, never blindly retried."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal


def next_delivery_action(receipt: Mapping[str, Any]) -> Literal["none", "reconcile", "retry_same_idempotency_key"]:
    state = receipt["delivery_state"]
    if state == "unknown" or receipt["reconciliation_required"]:
        return "reconcile"
    if state == "failed" and not receipt["confirmed_by_destination"] and receipt["remote_ref"] is None:
        return "retry_same_idempotency_key"
    return "none"
