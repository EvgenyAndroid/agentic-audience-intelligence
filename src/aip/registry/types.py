"""Versioned type registry (FR31). Source names never set grain; registry entries do."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aip import paths
from aip.canonical import load_path
from aip.contracts.validator import default_schema_set


class TypeRegistry:
    def __init__(self, entries: list[dict[str, Any]]):
        schemas = default_schema_set()
        self._entries: dict[tuple[str, str], dict[str, Any]] = {}
        for entry in entries:
            schemas.validate(entry, "type_registry_entry")
            self._entries[(entry["type_id"], entry["type_version"])] = entry

    @classmethod
    def load(cls, directory: Path | None = None) -> TypeRegistry:
        folder = directory or paths.registry_dir() / "types"
        return cls([load_path(p) for p in sorted(folder.glob("*.json"))])

    def get(self, type_id: str, type_version: str) -> dict[str, Any] | None:
        return self._entries.get((type_id, type_version))

    def is_confirmed(self, unit: dict[str, Any]) -> bool:
        entry = self.get(unit["type_id"], unit["type_version"])
        return entry is not None and entry["registration_state"] == "confirmed"

    def grain(self, unit: dict[str, Any]) -> str | None:
        entry = self.get(unit["type_id"], unit["type_version"])
        return entry["grain"] if entry else None

    def relationship_allowed(self, a: dict[str, Any], b: dict[str, Any]) -> bool:
        """True when either unit's registry entry declares a permitted relationship to the other's type."""

        def declares(src: dict[str, Any], dst: dict[str, Any]) -> bool:
            entry = self.get(src["type_id"], src["type_version"])
            if entry is None:
                return False
            return any(r["target_type_id"] == dst["type_id"] for r in entry["allowed_relationships"])

        return declares(a, b) or declares(b, a)

    def semantic_feature_allowed(self, type_id: str, type_version: str) -> bool:
        entry = self.get(type_id, type_version)
        return bool(entry and entry["semantic_feature_allowed"])
