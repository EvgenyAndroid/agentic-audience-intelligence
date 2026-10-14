"""Single reason-code registry (FR41). Each code belongs to exactly one dimension."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aip import paths
from aip.canonical import load_path
from aip.contracts.validator import default_schema_set


@dataclass(frozen=True)
class ReasonCode:
    code: str
    dimension: str
    decision_effect: str | None
    description: str


class ReasonCodeRegistry:
    def __init__(self, document: dict):
        default_schema_set().validate(document, "reason_code_registry")
        self._codes: dict[str, ReasonCode] = {}
        self._aliases: dict[str, str] = {}
        for entry in document["codes"]:
            code = entry["code"]
            if code in self._codes or code in self._aliases:
                raise ValueError(f"reason code {code!r} declared twice")
            self._codes[code] = ReasonCode(code, entry["dimension"], entry["decision_effect"], entry["description"])
            for alias in entry["aliases"]:
                if alias in self._codes or alias in self._aliases:
                    raise ValueError(f"alias {alias!r} collides with an existing code")
                self._aliases[alias] = code

    @classmethod
    def load(cls, path: Path | None = None) -> ReasonCodeRegistry:
        return cls(load_path(path or paths.registry_dir() / "reason_codes.json"))

    def resolve(self, code: str) -> ReasonCode:
        canonical = self._aliases.get(code, code)
        if canonical not in self._codes:
            raise KeyError(f"unknown reason code {code!r}")
        return self._codes[canonical]

    def require(self, code: str, dimension: str, effect: str | None = None) -> ReasonCode:
        entry = self.resolve(code)
        if entry.dimension != dimension:
            raise ValueError(f"reason code {code!r} belongs to {entry.dimension}, not {dimension}")
        if effect is not None and entry.decision_effect != effect:
            raise ValueError(f"reason code {code!r} has effect {entry.decision_effect}, not {effect}")
        return entry

    def codes(self, dimension: str | None = None) -> list[str]:
        return sorted(c for c, e in self._codes.items() if dimension in (None, e.dimension))
