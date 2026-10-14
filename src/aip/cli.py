"""Command line entry point: `aip <command>`. Paths are handled with pathlib for Windows compatibility."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path

from aip import paths
from aip.canonical import dump_path, load_path
from aip.contracts.conformance import check_invalid, check_valid
from aip.contracts.semantic import semantic_issues
from aip.contracts.validator import default_schema_set
from aip.registry import DocumentIndex, ReasonCodeRegistry, TypeRegistry
from aip.routing import RouterConfig, decide
from aip.timeutil import parse_ts


def _json_files(targets: list[str]) -> list[Path]:
    files: list[Path] = []
    for target in targets:
        p = Path(target)
        files.extend(sorted(p.rglob("*.json")) if p.is_dir() else [p])
    return files


def world_index(extra_dirs: list[str]) -> DocumentIndex:
    root = paths.repo_root()
    index = DocumentIndex()
    index.add_paths(
        sorted((root / "registry" / "policies").glob("*.json"))
        + sorted((root / "registry" / "profiles").glob("*.json"))
    )
    for d in extra_dirs:
        index.add_paths(
            p
            for p in sorted(Path(d).rglob("*.json"))
            if load_path(p).get("kind")
            in {"dataset_manifest", "objective", "source_profile", "execution_policy", "output_policy"}
        )
    return index


def cmd_validate(args: argparse.Namespace) -> int:
    schemas, failed = default_schema_set(), 0
    for path in _json_files(args.paths):
        doc = load_path(path)
        issues = schemas.issues(doc) or semantic_issues(doc)
        if issues:
            failed += 1
            print(f"FAIL {path}")
            for i in issues[:10]:
                print(f"     {i.path or '/'} [{i.keyword}] {i.message}")
    print(f"{failed} failing document(s)")
    return 1 if failed else 0


def cmd_conformance(args: argparse.Namespace) -> int:
    root, schemas = paths.repo_root(), default_schema_set()
    valid = check_valid(
        schemas, sorted((root / "examples" / "valid").rglob("*.json")) + sorted((root / "registry").rglob("*.json"))
    )
    invalid = check_invalid(schemas, root / "examples" / "invalid" / "cases.json", root)
    report = {
        "valid_examples": {"total": len(valid), "failed": [r.case_id for r in valid if not r.passed]},
        "invalid_cases": {
            "total": len(invalid),
            "failed": [{"id": r.case_id, "found": r.detail} for r in invalid if not r.passed],
        },
    }
    print(json.dumps(report, indent=2))
    if args.report:
        dump_path(report, Path(args.report))
    return 1 if report["valid_examples"]["failed"] or report["invalid_cases"]["failed"] else 0


def cmd_route(args: argparse.Namespace) -> int:
    decision = decide(
        load_path(Path(args.task)),
        documents=world_index(args.docs),
        bundle=load_path(Path(args.bundle)) if args.bundle else None,
        types=TypeRegistry.load(),
        reasons=ReasonCodeRegistry.load(),
        config=RouterConfig(max_decision_ttl=timedelta(hours=args.ttl_hours)),
        now=parse_ts(args.now),
    )
    print(json.dumps(decision, indent=2))
    return 0


def cmd_benchmark(args: argparse.Namespace) -> int:
    from aip.evaluation import load_suite, run_router, score

    suite = Path(args.suite)
    cases = load_suite(suite)
    index = world_index([str(suite / "world")])
    types, reasons = TypeRegistry.load(), ReasonCodeRegistry.load()
    config, now = RouterConfig(max_decision_ttl=timedelta(hours=args.ttl_hours)), parse_ts(args.now)

    def route(task: dict, bundle: dict) -> dict:
        return decide(task, documents=index, bundle=bundle, types=types, reasons=reasons, config=config, now=now)

    result = score(cases, run_router(cases, route))
    result["comparator"] = "deterministic_rules_router"
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2))
    if args.report:
        dump_path(result, Path(args.report))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aip")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("schemas", help="list contract kinds").set_defaults(
        func=lambda a: print("\n".join(default_schema_set().kinds)) or 0
    )
    v = sub.add_parser("validate", help="validate JSON documents or folders")
    v.add_argument("paths", nargs="+")
    v.set_defaults(func=cmd_validate)
    c = sub.add_parser("conformance", help="run valid examples and invalid cases")
    c.add_argument("--report")
    c.set_defaults(func=cmd_conformance)
    r = sub.add_parser("route", help="route one task")
    r.add_argument("--task", required=True)
    r.add_argument("--bundle")
    r.add_argument("--docs", nargs="*", default=[])
    r.add_argument("--now", required=True, help="decision time, e.g. 2026-10-14T12:00:00Z")
    r.add_argument("--ttl-hours", type=float, required=True, help="maximum decision validity (no default)")
    r.set_defaults(func=cmd_route)
    b = sub.add_parser("benchmark", help="score the rules router on a routing suite")
    b.add_argument("--suite", required=True)
    b.add_argument("--now", required=True)
    b.add_argument("--ttl-hours", type=float, required=True)
    b.add_argument("--report")
    b.set_defaults(func=cmd_benchmark)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
