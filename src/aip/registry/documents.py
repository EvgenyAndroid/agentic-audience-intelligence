"""In-memory index of validated documents keyed by (kind, id, version)."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from aip.canonical import load_path
from aip.contracts.validator import SchemaSet, default_schema_set

ID_FIELDS: dict[str, tuple[str, str]] = {
    "source_profile": ("profile_id", "profile_version"),
    "execution_policy": ("policy_id", "policy_version"),
    "output_policy": ("policy_id", "policy_version"),
    "dataset_manifest": ("dataset_id", "dataset_version"),
    "objective": ("objective_id", "objective_version"),
    "task": ("task_id", "task_version"),
    "release_manifest": ("release_id", "release_version"),
    "representation_descriptor": ("descriptor_id", "descriptor_version"),
    "type_registry_entry": ("type_id", "type_version"),
    "feature_plan": ("feature_plan_id", "feature_plan_version"),
    "evidence_card": ("card_id", "card_version"),
}


class DocumentIndex:
    def __init__(self, documents: Iterable[dict[str, Any]] = (), schemas: SchemaSet | None = None):
        self._schemas = schemas or default_schema_set()
        self._docs: dict[tuple[str, str, str], dict[str, Any]] = {}
        for doc in documents:
            self.add(doc)

    def add(self, doc: dict[str, Any]) -> None:
        self._schemas.validate(doc)
        kind = doc["kind"]
        if kind not in ID_FIELDS:
            return
        id_field, version_field = ID_FIELDS[kind]
        key = (kind, doc[id_field], doc[version_field])
        if key in self._docs and self._docs[key] != doc:
            raise ValueError(f"conflicting documents for {key}")
        self._docs[key] = doc

    def add_paths(self, paths: Iterable[Path]) -> None:
        for path in paths:
            self.add(load_path(path))

    def get(self, kind: str, ref: dict[str, str]) -> dict[str, Any] | None:
        return self._docs.get((kind, ref["id"], ref["version"]))

    def all(self, kind: str) -> list[dict[str, Any]]:
        return [d for (k, _, _), d in self._docs.items() if k == kind]
