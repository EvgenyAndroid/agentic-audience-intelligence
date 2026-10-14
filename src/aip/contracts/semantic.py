"""Cross-field rules that JSON Schema cannot express. Run after schema validation passes."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from typing import Any

from aip.contracts.validator import Issue
from aip.timeutil import parse_ts


def _order(doc: dict[str, Any], early: str, late: str, strict: bool = True) -> list[Issue]:
    a, b = doc.get(early), doc.get(late)
    if a is None or b is None:
        return []
    bad = parse_ts(b) <= parse_ts(a) if strict else parse_ts(b) < parse_ts(a)
    return (
        [Issue(f"/{late}", "semantic", f"{late} must be {'after' if strict else 'at or after'} {early}")] if bad else []
    )


def _unique(doc: dict[str, Any], array: str, key: str) -> list[Issue]:
    counts = Counter(item[key] for item in doc.get(array, []))
    return [Issue(f"/{array}", "semantic", f"duplicate {key} {value!r}") for value, n in counts.items() if n > 1]


def _policy(doc: dict[str, Any]) -> list[Issue]:
    issues = _order(doc, "effective_from", "effective_until")
    if doc["kind"] == "execution_policy":
        issues += _unique(doc, "operations", "operation")
    else:
        issues += _unique(doc, "artifact_rules", "artifact_type")
    return issues


RULES: dict[str, Callable[[dict[str, Any]], list[Issue]]] = {
    "event": lambda d: _order(d, "event_time", "available_at", strict=False),
    "observation": lambda d: _order(d, "observed_at", "available_at", strict=False),
    "outcome_label": lambda d: (
        _order(d, "prediction_cutoff", "horizon_end") + _order(d, "horizon_end", "available_at", strict=False)
    ),
    "relationship": lambda d: _order(d, "valid_from", "valid_until"),
    "execution_policy": _policy,
    "output_policy": _policy,
    "task_decision": lambda d: _order(d, "decided_at", "valid_until"),
    "authorization": lambda d: _order(d, "valid_from", "valid_until"),
    "entity": lambda d: _order(d, "valid_from", "valid_until"),
    "type_registry_entry": lambda d: [],
}


def semantic_issues(document: dict[str, Any]) -> list[Issue]:
    rule = RULES.get(document.get("kind", ""))
    return rule(document) if rule else []
