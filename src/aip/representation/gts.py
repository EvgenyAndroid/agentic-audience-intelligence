"""Golden Test Set evaluation reusing the GTS pair fields (pair_id, concept_a/b, expected_min/max)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any


def evaluate_gts(test_set: Mapping[str, Any], similarity: Callable[[str, str], float]) -> dict[str, Any]:
    """Score each pair with a caller-supplied similarity function. expected_max is exclusive, expected_min inclusive."""
    results = []
    for pair in test_set["pairs"]:
        value = similarity(pair["concept_a"], pair["concept_b"])
        low_ok = pair["expected_min"] is None or value >= pair["expected_min"]
        high_ok = pair["expected_max"] is None or value < pair["expected_max"]
        results.append({"pair_id": pair["pair_id"], "similarity": value, "passed": bool(low_ok and high_ok)})
    passed = sum(r["passed"] for r in results)
    return {
        "gts_version": test_set["gts_version"],
        "pairs": results,
        "passed": passed,
        "total": len(results),
        "all_passed": passed == len(results),
    }
