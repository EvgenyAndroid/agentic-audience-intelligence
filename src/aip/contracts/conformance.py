"""Contract conformance: valid examples must pass; invalid cases must fail for the expected reason."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aip.canonical import StrictJSONError, load_path, loads
from aip.contracts.semantic import semantic_issues
from aip.contracts.validator import Issue, SchemaSet


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    passed: bool
    detail: str


def _split(pointer: str) -> list[str]:
    return [p.replace("~1", "/").replace("~0", "~") for p in pointer.split("/")[1:]] if pointer else []


def apply_patch(document: Any, operations: list[dict[str, Any]]) -> Any:
    """Minimal JSON Patch (add, replace, remove) sufficient for conformance cases."""
    doc = copy.deepcopy(document)
    for op in operations:
        parts = _split(op["path"])
        parent = doc
        for part in parts[:-1]:
            parent = parent[int(part)] if isinstance(parent, list) else parent[part]
        last = parts[-1]
        if isinstance(parent, list):
            index = len(parent) if last == "-" else int(last)
            if op["op"] == "add":
                parent.insert(index, op["value"])
            elif op["op"] == "replace":
                parent[index] = op["value"]
            else:
                del parent[index]
        elif op["op"] in ("add", "replace"):
            parent[last] = op["value"]
        else:
            del parent[last]
    return doc


def all_issues(schemas: SchemaSet, document: Any) -> list[Issue]:
    issues = schemas.issues(document)
    return issues or semantic_issues(document)


def check_valid(schemas: SchemaSet, files: list[Path]) -> list[CaseResult]:
    results = []
    for path in files:
        issues = all_issues(schemas, load_path(path))
        detail = "; ".join(f"{i.path} [{i.keyword}] {i.message}" for i in issues[:3])
        results.append(CaseResult(path.as_posix(), not issues, detail))
    return results


def check_invalid(schemas: SchemaSet, cases_file: Path, root: Path) -> list[CaseResult]:
    results = []
    for case in load_path(cases_file)["cases"]:
        expect = case["expect"]
        if expect["layer"] == "strict_json":
            try:
                loads(case["raw"])
                results.append(CaseResult(case["id"], False, "strict loader accepted the text"))
            except StrictJSONError as exc:
                results.append(CaseResult(case["id"], True, str(exc)))
            continue
        document = apply_patch(load_path(root / case["base"]), case["patch"])
        if expect["layer"] == "schema":
            issues = schemas.issues(document)
        else:
            issues = [] if schemas.issues(document) else semantic_issues(document)
        matched = any(i.keyword == expect["keyword"] and i.path == expect["path"] for i in issues)
        found = "; ".join(f"{i.path} [{i.keyword}]" for i in issues[:6]) or "no issues"
        results.append(CaseResult(case["id"], matched, found))
    return results
