"""Routing benchmark harness (FR32).

The harness (scorer) reads oracles; evaluated agents must never be given the oracle directory.
Local runs cannot enforce that isolation; record it as not verified unless the sandbox enforces it.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aip.canonical import load_path
from aip.contracts.validator import default_schema_set

VERDICTS = ("ELIGIBLE", "PROVISIONAL", "BLOCKED")


@dataclass(frozen=True)
class BenchmarkCase:
    case: dict[str, Any]
    oracle: dict[str, Any]
    suite_dir: Path

    def load(self, rel: str) -> dict[str, Any]:
        return load_path(self.suite_dir / rel)


@dataclass(frozen=True)
class Prediction:
    case_id: str
    verdict: str
    reason_codes: tuple[str, ...]


def load_suite(suite_dir: Path) -> list[BenchmarkCase]:
    schemas = default_schema_set()
    cases = []
    for case_path in sorted((suite_dir / "cases").glob("case-*/case.json")):
        case = load_path(case_path)
        schemas.validate(case, "routing_case")
        oracle = load_path(suite_dir / "oracle" / f"{case['case_id']}.json")
        schemas.validate(oracle, "routing_oracle")
        cases.append(BenchmarkCase(case, oracle, suite_dir))
    return cases


def run_router(
    cases: Sequence[BenchmarkCase], route: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]
) -> list[Prediction]:
    """route(task, bundle) -> task_decision. Used for the deterministic rules-router comparator."""
    out = []
    for c in cases:
        decision = route(c.load(c.case["task_path"]), c.load(c.case["evidence_bundle_path"]))
        out.append(Prediction(c.case["case_id"], decision["verdict"], tuple(r["code"] for r in decision["reasons"])))
    return out


def predictions_from_proposals(proposals: Mapping[str, Mapping[str, Any]]) -> list[Prediction]:
    return [
        Prediction(cid, p["proposed_verdict"], tuple(r["code"] for r in p["proposed_reasons"]))
        for cid, p in proposals.items()
    ]


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def score(cases: Sequence[BenchmarkCase], predictions: Sequence[Prediction]) -> dict[str, Any]:
    oracle = {c.case["case_id"]: c.oracle for c in cases}
    pred = {p.case_id: p for p in predictions}
    missing = sorted(set(oracle) - set(pred))
    rows = []
    for cid, o in oracle.items():
        p = pred.get(cid)
        verdict = p.verdict if p else "MISSING"
        reasons_ok = p is not None and set(o["mandatory_reason_codes"]) <= set(p.reason_codes)
        rows.append(
            {
                "case_id": cid,
                "expected": o["expected_verdict"],
                "predicted": verdict,
                "verdict_match": verdict == o["expected_verdict"],
                "mandatory_reasons_present": reasons_ok,
                "critical": o["critical"],
                "defect_pattern": o["defect_pattern"],
            }
        )
    n = len(rows)
    f1s = []
    for v in VERDICTS:
        tp = sum(r["expected"] == v and r["predicted"] == v for r in rows)
        fp = sum(r["expected"] != v and r["predicted"] == v for r in rows)
        fn = sum(r["expected"] == v and r["predicted"] != v for r in rows)
        precision, recall = _rate(tp, tp + fp), _rate(tp, tp + fn)
        f1s.append(0.0 if not precision or not recall else 2 * precision * recall / (precision + recall))
    expected = Counter(r["expected"] for r in rows)
    critical_unsafe = [r for r in rows if r["critical"] and r["expected"] != "ELIGIBLE"]
    return {
        "cases": n,
        "missing_predictions": missing,
        "verdict_accuracy": _rate(sum(r["verdict_match"] for r in rows), n),
        "verdict_and_reason_accuracy": _rate(
            sum(r["verdict_match"] and r["mandatory_reasons_present"] for r in rows), n
        ),
        "macro_f1": sum(f1s) / len(f1s),
        "critical_false_safe_rate": _rate(
            sum(r["predicted"] == "ELIGIBLE" for r in critical_unsafe), len(critical_unsafe)
        ),
        "premature_clearance_rate": _rate(
            sum(r["expected"] == "PROVISIONAL" and r["predicted"] == "ELIGIBLE" for r in rows), expected["PROVISIONAL"]
        ),
        "false_block_rate": _rate(
            sum(r["expected"] == "ELIGIBLE" and r["predicted"] == "BLOCKED" for r in rows), expected["ELIGIBLE"]
        ),
        "unnecessary_deferral_rate": _rate(
            sum(r["expected"] == "ELIGIBLE" and r["predicted"] == "PROVISIONAL" for r in rows), expected["ELIGIBLE"]
        ),
        "expected_distribution": dict(expected),
        "rows": rows,
    }
