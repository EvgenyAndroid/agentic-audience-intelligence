"""Compile demo scenarios into static bundles (H4: computed at build time, served without a live API).

Every bundle states its inputs by hash, the engine version and source hash, and a fixed evaluation time, so a
reader can tell exactly what was computed and when. Bundles are rebuilt deterministically; a test compares the
committed copies with a fresh build.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from aip import __version__, paths
from aip.canonical import canonical_bytes, dump_path, load_path, sha256_of
from aip.contracts.validator import default_schema_set
from aip.demo import lookalike
from aip.recommendation import Candidate, recommend
from aip.registry import DocumentIndex, ReasonCodeRegistry, TypeRegistry
from aip.routing import RouterConfig, decide
from aip.routing.prerequisites import CATALOG
from aip.timeutil import parse_ts

BUNDLE_FORMAT = "1.0.0"
DISCLOSURE = (
    "Synthetic scenarios. Every decision, ranking and score on this page was computed by the engine when the site "
    "was built, at the evaluation time shown; nothing runs while you browse. Synthetic results test software "
    "behavior and are not evidence of data quality, model quality or market performance. The release preview is "
    "not an approval and nothing is activated."
)
WORLD_KINDS = (
    "dataset_manifest",
    "objective",
    "source_profile",
    "unit_mapping",
    "relationship_snapshot",
    "model_registration",
)


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(load_path(path))).hexdigest()


def engine_sha256(root: Path) -> str:
    """Hash of the engine source and contracts, so a bundle names the exact code that produced it."""
    digest = hashlib.sha256()
    files = sorted((root / "src" / "aip").rglob("*.py")) + sorted((root / "schemas" / "v1").glob("*.json"))
    for path in files:
        digest.update(_rel(root, path).encode())
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
    return "sha256:" + digest.hexdigest()


def _world(root: Path) -> tuple[DocumentIndex, list[Path]]:
    files = sorted((root / "registry" / "policies").glob("*.json")) + sorted(
        (root / "registry" / "profiles").glob("*.json")
    )
    for kind in WORLD_KINDS:
        files += sorted((root / "examples" / "valid" / kind).glob("*.json"))
    index = DocumentIndex()
    index.add_paths(files)
    return index, files


def _fingerprint(world: DocumentIndex, types: TypeRegistry, dataset_ref: dict[str, str]) -> dict[str, Any]:
    dataset = world.get("dataset_manifest", dataset_ref)
    if dataset is None:
        raise ValueError(f"dataset {dataset_ref['id']} not found")
    profile = world.get("source_profile", dataset["source_profile_ref"])
    if profile is None:
        raise ValueError(f"profile for {dataset_ref['id']} not found")
    units = []
    for obs in profile["observation_units"]:
        entry = types.get(obs["unit"]["type_id"], obs["unit"]["type_version"]) or {}
        units.append(
            {
                "unit": obs["unit"],
                "key_field": obs["key_field"],
                "label": entry.get("label"),
                "represents": entry.get("represents"),
                "grain": entry.get("grain"),
                "registration_state": entry.get("registration_state"),
            }
        )
    return {
        "dataset_id": dataset["dataset_id"],
        "dataset_state": dataset["dataset_state"],
        "profile_id": profile["profile_id"],
        "profile_version": profile["profile_version"],
        "family_label": profile["family_label"],
        "profile_state": profile["profile_state"],
        "observation_units": units,
        "signals": [
            {k: s[k] for k in ("signal_id", "primitive", "value_type", "evidence_kind", "description")}
            for s in profile["signals"]
        ],
        "known_limits": profile["known_limits"],
        "execution_policy_refs": profile["execution_policy_refs"],
        "output_policy_refs": profile["output_policy_refs"],
    }


def _build_scenario(
    root: Path,
    scenario_path: Path,
    world: DocumentIndex,
    types: TypeRegistry,
    reasons: ReasonCodeRegistry,
    config: RouterConfig,
    now: datetime,
) -> tuple[dict[str, Any], list[Path]]:
    schemas = default_schema_set()
    scenario = load_path(scenario_path)
    inputs = [scenario_path]
    trace: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    candidates: dict[str, Candidate] = {}
    for entry in scenario["tasks"]:
        task_path, bundle_path = root / entry["task"], root / entry["bundle"]
        inputs += [task_path, bundle_path]
        task, bundle = load_path(task_path), load_path(bundle_path)
        schemas.validate(task, "task")
        decision = decide(task, documents=world, bundle=bundle, types=types, reasons=reasons, config=config, now=now)
        objective = world.get("objective", task["objective_ref"])
        trace.append(
            {
                "step": "route",
                "task_id": task["task_id"],
                "detail": f"{len(decision['prerequisites'])} prerequisites checked",
                "outcome": decision["verdict"],
            }
        )
        rows.append(
            {
                "task": {
                    k: task[k]
                    for k in (
                        "task_id",
                        "task_family",
                        "operation",
                        "requested_artifact",
                        "execution_location_ref",
                        "destination_ref",
                        "objective_ref",
                        "model_ref",
                        "units",
                    )
                },
                "objective": objective,
                "decision": decision,
            }
        )
        candidates[task["task_id"]] = Candidate(task, decision)

    requested = candidates[scenario["requested_task"]]
    objective = world.get("objective", requested.task["objective_ref"])
    if objective is None:
        raise ValueError("requested task objective not found")
    alternatives = [
        c
        for tid, c in candidates.items()
        if tid != scenario["requested_task"] and c.task["objective_ref"] == requested.task["objective_ref"]
    ]
    rec = recommend(
        recommendation_id=f"rec_demo_{scenario['scenario_id']}",
        objective=objective,
        requested=requested,
        alternatives=alternatives,
        now=now,
    )
    trace.append(
        {
            "step": "recommend",
            "task_id": scenario["requested_task"],
            "detail": f"{len(alternatives)} alternative{'' if len(alternatives) == 1 else 's'} for the same objective",
            "outcome": rec["ranking_status"],
        }
    )

    look = None
    if scenario["lookalike"]:
        params = scenario["lookalike"]
        verdict = candidates[params["task_id"]].decision["verdict"]
        if verdict != "ELIGIBLE":
            raise ValueError("synthetic scores are only computed for an ELIGIBLE look-alike task")
        look = lookalike.run({k: v for k, v in params.items() if k != "task_id"})
        look["task_id"] = params["task_id"]
        trace.append(
            {
                "step": "score",
                "task_id": params["task_id"],
                "detail": "synthetic seed and pool; centroid and multi-prototype baselines",
                "outcome": "completed",
            }
        )

    used = sorted({r["code"] for row in rows for r in row["decision"]["reasons"]})
    bundle = {
        "bundle_format": BUNDLE_FORMAT,
        "scenario": {k: scenario[k] for k in ("scenario_id", "title", "source_label", "summary", "requested_task")},
        "fingerprint": _fingerprint(world, types, requested.task["input_snapshot_refs"][0]),
        "tasks": rows,
        "recommendation": rec,
        "lookalike": look,
        "reason_codes": {c: reasons.resolve(c).description for c in used},
        "prerequisites": {
            pid: {"description": CATALOG[pid].description, "remedy": CATALOG[pid].remedy}
            for pid in sorted({p["prerequisite_id"] for row in rows for p in row["decision"]["prerequisites"]})
        },
        "trace": trace,
    }
    return bundle, inputs


def load_settings() -> tuple[datetime, float]:
    """Evaluation time and maximum decision validity from demo/build.json (supplied, never defaulted)."""
    settings = load_path(paths.repo_root() / "demo" / "build.json")
    return parse_ts(settings["evaluated_at"]), float(settings["max_decision_ttl_hours"])


def build_bundles(out_dir: Path, *, now: datetime, ttl_hours: float) -> list[Path]:
    """Build every scenario under demo/scenarios into out_dir. Evaluation time and validity are always supplied."""
    root = paths.repo_root()
    world, world_files = _world(root)
    types, reasons = TypeRegistry.load(), ReasonCodeRegistry.load()
    config = RouterConfig(max_decision_ttl=timedelta(hours=ttl_hours))
    out_dir.mkdir(parents=True, exist_ok=True)
    written, index = [], []
    scenario_paths = sorted((root / "demo" / "scenarios").glob("*/scenario.json"), key=lambda p: load_path(p)["order"])
    for scenario_path in scenario_paths:
        bundle, inputs = _build_scenario(root, scenario_path, world, types, reasons, config, now)
        files = sorted(set(world_files + inputs + sorted((root / "registry" / "types").glob("*.json"))))
        files.append(root / "registry" / "reason_codes.json")
        bundle["manifest"] = {
            "evaluated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "max_decision_ttl_hours": ttl_hours,
            "engine_version": __version__,
            "engine_sha256": engine_sha256(root),
            "inputs": [{"path": _rel(root, f), "sha256": _file_hash(f)} for f in files],
            "computed": "build_time",
            "synthetic": True,
            "disclosure": DISCLOSURE,
        }
        bundle["manifest"]["bundle_sha256"] = sha256_of({k: v for k, v in bundle.items() if k != "manifest"})
        sid = bundle["scenario"]["scenario_id"]
        path = out_dir / f"{sid}.json"
        dump_path(bundle, path)
        written.append(path)
        index.append(
            {**bundle["scenario"], "file": f"{sid}.json", "bundle_sha256": bundle["manifest"]["bundle_sha256"]}
        )
    index_path = out_dir / "index.json"
    dump_path(
        {
            "bundle_format": BUNDLE_FORMAT,
            "evaluated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "engine_version": __version__,
            "engine_sha256": engine_sha256(root),
            "disclosure": DISCLOSURE,
            "scenarios": index,
        },
        index_path,
    )
    return [index_path, *written]
