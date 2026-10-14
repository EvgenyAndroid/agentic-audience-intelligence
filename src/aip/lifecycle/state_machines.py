"""Allowed state transitions. Each dimension has its own machine; none substitutes for a task verdict."""

from __future__ import annotations

from collections.abc import Mapping


class TransitionError(ValueError):
    pass


Machine = Mapping[str, frozenset[str]]

JOB: Machine = {
    "queued": frozenset({"running", "cancelled"}),
    "running": frozenset({"paused", "succeeded", "failed", "cancelled", "reconciling"}),
    "paused": frozenset({"running", "cancelled"}),
    "reconciling": frozenset({"running", "failed", "succeeded"}),
    "succeeded": frozenset(),
    "failed": frozenset(),
    "cancelled": frozenset(),
}
AUDIENCE: Machine = {
    "draft": frozenset({"prepared"}),
    "prepared": frozenset({"approved", "revoked"}),
    "approved": frozenset({"released", "revoked", "expired"}),
    "released": frozenset({"expired", "revoked"}),
    "expired": frozenset(),
    "revoked": frozenset(),
}
DELIVERY: Machine = {
    "submitted": frozenset({"accepted", "failed", "unknown"}),
    "unknown": frozenset({"submitted", "accepted", "failed"}),  # only after reconciliation establishes the remote state
    "accepted": frozenset({"matched", "live", "failed"}),
    "matched": frozenset({"live", "failed"}),
    "live": frozenset(),
    "failed": frozenset(),
}


def transition(machine: Machine, current: str, target: str) -> str:
    if target not in machine.get(current, frozenset()):
        raise TransitionError(f"transition {current} -> {target} is not allowed")
    return target
