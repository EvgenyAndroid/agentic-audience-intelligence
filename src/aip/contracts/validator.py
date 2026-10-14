"""Validate documents against the normative JSON Schema 2020-12 contracts."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from aip import paths
from aip.canonical import load_path


@dataclass(frozen=True)
class Issue:
    path: str  # JSON pointer into the instance
    keyword: str
    message: str


class ContractError(ValueError):
    def __init__(self, kind: str | None, issues: list[Issue]):
        self.kind = kind
        self.issues = issues
        summary = "; ".join(f"{i.path or '/'} [{i.keyword}] {i.message}" for i in issues[:5])
        super().__init__(f"{kind or 'document'} failed validation: {summary}")


def _pointer(parts: Iterable[Any]) -> str:
    return "".join("/" + str(p).replace("~", "~0").replace("/", "~1") for p in parts)


class SchemaSet:
    """All schemas in one directory, resolved through a shared referencing registry."""

    def __init__(self, schema_dir: Path | None = None):
        directory = schema_dir or paths.schema_dir()
        self.schemas: dict[str, dict[str, Any]] = {}
        resources = []
        for path in sorted(directory.glob("*.schema.json")):
            schema = load_path(path)
            Draft202012Validator.check_schema(schema)
            self.schemas[path.name.removesuffix(".schema.json")] = schema
            resources.append((schema["$id"], Resource.from_contents(schema, default_specification=DRAFT202012)))
        registry = Registry().with_resources(resources)
        self._validators = {
            kind: Draft202012Validator(schema, registry=registry, format_checker=FormatChecker())
            for kind, schema in self.schemas.items()
            if kind != "common"
        }

    @property
    def kinds(self) -> list[str]:
        return sorted(self._validators)

    def issues(self, document: Any, kind: str | None = None) -> list[Issue]:
        kind = kind or (document.get("kind") if isinstance(document, dict) else None)
        validator = self._validators.get(kind or "")
        if validator is None:
            return [Issue("/kind", "kind", f"unknown document kind {kind!r}")]
        errors = sorted(
            validator.iter_errors(document), key=lambda e: (list(map(str, e.absolute_path)), str(e.validator))
        )
        return [Issue(_pointer(e.absolute_path), str(e.validator), e.message) for e in errors]

    def validate(self, document: Any, kind: str | None = None) -> None:
        found = self.issues(document, kind)
        if found:
            raise ContractError(kind or (document.get("kind") if isinstance(document, dict) else None), found)


@lru_cache(maxsize=1)
def default_schema_set() -> SchemaSet:
    return SchemaSet()
