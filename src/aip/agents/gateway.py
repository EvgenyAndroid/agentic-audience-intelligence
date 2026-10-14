"""Tool gateway: allowlisted tools, server-derived tenant, budgets, injection resistance (FR19, NFR03, NFR07)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from aip.agents.roles import ROLES

AUTHORITY_KEYS = frozenset(
    {
        "tenant_id",
        "permissions",
        "policy",
        "policy_refs",
        "budget",
        "budget_refs",
        "authority",
        "verdict",
        "authorization",
        "release",
        "export_policy",
    }
)


class GatewayError(PermissionError):
    pass


@dataclass(frozen=True)
class ToolSpec:
    name: str
    handler: Callable[[str, Mapping[str, Any]], Any]  # receives the server-derived tenant id, never one from arguments
    cost_units: int = 1


@dataclass
class ActorContext:
    tenant_id: str  # derived by the platform from authentication, not from model output
    role: str
    budget_units: int
    spent_units: int = 0
    audit: list[dict[str, Any]] = field(default_factory=list)


class ToolGateway:
    def __init__(self, tools: Mapping[str, ToolSpec]):
        self._tools = dict(tools)

    def call(self, ctx: ActorContext, tool: str, arguments: Mapping[str, Any]) -> Any:
        role = ROLES.get(ctx.role)
        if role is None or tool not in role.tools:
            self._log(ctx, tool, "denied_tool")
            raise GatewayError(f"role {ctx.role!r} may not call {tool!r}")
        smuggled = AUTHORITY_KEYS & set(_all_keys(arguments))
        if smuggled:
            self._log(ctx, tool, "denied_authority_fields")
            raise GatewayError(f"arguments may not carry authority fields: {sorted(smuggled)}")
        spec = self._tools.get(tool)
        if spec is None:
            raise GatewayError(f"tool {tool!r} is not registered")
        if ctx.spent_units + spec.cost_units > ctx.budget_units:
            self._log(ctx, tool, "denied_budget")
            raise GatewayError("budget_exceeded")
        ctx.spent_units += spec.cost_units
        self._log(ctx, tool, "allowed")
        return spec.handler(ctx.tenant_id, arguments)

    @staticmethod
    def _log(ctx: ActorContext, tool: str, outcome: str) -> None:
        ctx.audit.append({"role": ctx.role, "tool": tool, "outcome": outcome, "spent_units": ctx.spent_units})


def _all_keys(value: Any) -> list[str]:
    if isinstance(value, Mapping):
        return [str(k) for k in value] + [k for v in value.values() for k in _all_keys(v)]
    if isinstance(value, list):
        return [k for v in value for k in _all_keys(v)]
    return []
