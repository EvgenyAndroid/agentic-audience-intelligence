"""Build the workbench bundles: generate each dataset, route its tasks, model what is eligible, write JSON.

Like the scenario bundles (H4), everything is computed at build time with a supplied evaluation time. The page
only filters what was computed: picking a model, moving the reach slider and exporting rows never re-run the
engine. A future server API (ADR 0005) returns the same bundle shape on request instead of from a file.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from aip import __version__, paths
from aip.canonical import dump_path, sha256_of
from aip.demo.build import engine_sha256
from aip.recommendation import Candidate, recommend
from aip.registry import DocumentIndex, ReasonCodeRegistry, TypeRegistry
from aip.routing import RouterConfig, decide
from aip.routing.prerequisites import CATALOG
from aip.workbench import documents as docs
from aip.workbench import methods
from aip.workbench.generate import Synthetic, generate
from aip.workbench.specs import DATASETS, DatasetSpec

BUNDLE_FORMAT = "1.0.0"
DISCLOSURE = (
    "Synthetic datasets. Every verdict, model, score and metric here was computed by the engine when the site was "
    "built; the page only filters those results. The data describes no real people, households, companies or places, "
    "and the metrics test software behavior, not real-world performance. Nothing is activated."
)
METHOD_LABEL = {
    "lookalike": "Look-alike (seed affinity)",
    "actalike": "Act-alike (behavioral affinity)",
    "propensity": "Propensity (estimated chance)",
    "byom": "Your registered model",
    "semantic": "Contextual (semantic similarity)",
}


def _world() -> DocumentIndex:
    root = paths.repo_root()
    index = DocumentIndex()
    index.add_paths(sorted((root / "registry" / "policies").glob("*.json")))
    return index


def _assessment(spec: DatasetSpec, data: Synthetic) -> dict[str, Any]:
    """Rule-based profile of the data and the methods it supports. In the server version a reasoning agent drafts
    this from column names and summary statistics; it never sees rows, and the router still decides."""
    missing = np.isnan(data.x).mean(axis=0)
    features = [
        {
            "name": f.name,
            "label": f.label,
            "family": f.family,
            "kind": f.kind,
            "missing_rate": round(float(missing[i]), 3),
            "used": not f.sensitive,
            "excluded_reason": "sensitive attribute" if f.sensitive else None,
        }
        for i, f in enumerate(spec.features)
    ]
    behavioral = [f.name for f in spec.features if f.family == "behavioral"]
    proposals = []
    for method in spec.methods:
        if method == "lookalike":
            why = (
                f"A seed list of {len(data.seed):,} ({spec.seed_label}) is present, so similarity to it can be scored."
            )
        elif method == "actalike":
            why = (
                f"{len(behavioral)} behavioral signals and a behavior pattern of {len(data.behavior):,} "
                f"({spec.behavior_label}) are present."
            )
        elif method == "propensity":
            positives = int(np.nansum(data.outcome)) if data.outcome is not None else 0
            why = (
                f"An outcome label ({spec.outcome.label} within {spec.outcome.horizon_days} days) "
                f"has {positives:,} positives."
                if spec.outcome
                else ""
            )
        elif method == "byom":
            why = "A model is registered for this data and runs inside the boundary."
        else:
            why = f"A content brief ({spec.brief_label}) and contextual signals are present."
        proposals.append({"method": method, "label": METHOD_LABEL[method], "rationale": why})
    labels_ok, positives = methods.labels_qualified(data) if spec.outcome else (False, 0)
    known = int(np.isfinite(data.outcome.astype(float)).sum()) if data.outcome is not None else 0
    return {
        "assessor": "rule_based",
        "unit": {**docs.unit_ref(spec), "label": spec.unit.label},
        "rows": spec.n,
        "features": features,
        "sensitive_excluded": [f.name for f in spec.features if f.sensitive],
        "seed": {"label": spec.seed_label, "size": int(len(data.seed))} if spec.seed_size else None,
        "behavior": {"label": spec.behavior_label, "size": int(len(data.behavior))} if spec.behavior_features else None,
        "outcome": {
            "label": spec.outcome.label,
            "horizon_days": spec.outcome.horizon_days,
            "positives": positives,
            # Over records with a known outcome (every record, for generated data).
            "base_rate": round(positives / known, 4) if known else 0.0,
            "qualified": labels_ok,
            "min_positives_for_training": methods.MIN_POSITIVES,
        }
        if spec.outcome
        else None,
        "brief": spec.brief_label,
        "coverage": {
            m: round(docs.coverage_share(data, m), 4)
            for m in spec.methods
            if m in ("lookalike", "actalike", "semantic")
        },
        "min_coverage": methods.MIN_COVERAGE,
        "proposals": proposals,
    }


def _pick(method: str, result: dict[str, Any]) -> dict[str, Any]:
    """Recommend one candidate model on held-out quality; the simpler model wins ties."""
    models = result["models"]
    if len(models) == 1:
        return {"model_id": models[0]["model_id"], "basis": "Only one model applies to this method."}
    if method == "propensity":
        key, metric = (lambda m: m["evaluation"]["average_precision"]), "average precision on held-out records"
    else:
        key, metric = (lambda m: m["evaluation"]["recall_at"]["0.1"]), "held-out recall at 10% reach"
    best = models[0]
    for m in models[1:]:
        if key(m) > key(best):
            best = m
    return {
        "model_id": best["model_id"],
        "basis": f"Highest {metric} ({key(best):.3f}); the simpler model is kept unless another is better.",
    }


def _cells(spec: DatasetSpec) -> dict[str, Any] | None:
    if spec.location != "cleanroom":
        return None
    return {"dimension": "daypart", "min_distinct_count": 50, "small_cell_handling": "suppress_cell"}


def build_dataset(spec: DatasetSpec, world: DocumentIndex, now: datetime, ttl_hours: float) -> dict[str, Any]:
    data = generate(spec)
    types, reasons = TypeRegistry.load(), ReasonCodeRegistry.load()
    config = RouterConfig(max_decision_ttl=timedelta(hours=ttl_hours))
    index = DocumentIndex(world.all("execution_policy") + world.all("output_policy"))
    generated = [docs.profile(spec), docs.manifest(spec, data), docs.objective(spec)]
    if "byom" in spec.methods:
        generated.append(docs.model_registration(spec))
    for doc in generated:
        index.add(doc)

    routed: dict[str, dict[str, Any]] = {}
    candidates: list[tuple[str | None, Candidate]] = []
    for role, method, task in docs.tasks_for(spec):
        bundle = docs.evidence(spec, data, task, method)
        decision = decide(task, documents=index, bundle=bundle, types=types, reasons=reasons, config=config, now=now)
        key = method or role
        routed[key] = {"role": role, "method": method, "task": task, "evidence": bundle, "decision": decision}
        if role == "method":
            candidates.append((method, Candidate(task, decision)))

    objective = docs.objective(spec)
    recommendation = recommend(
        recommendation_id=f"rec_wb_{spec.dataset_id}",
        objective=objective,
        requested=candidates[0][1],
        alternatives=[c for _, c in candidates[1:]],
        now=now,
    )

    results: dict[str, Any] = {}
    for method in spec.methods:
        if routed[method]["decision"]["verdict"] != "ELIGIBLE":
            continue
        if method in ("lookalike", "actalike"):
            result = methods.affinity(data, method)
        elif method == "propensity":
            result = methods.propensity(data)
        elif method == "byom":
            result = methods.byom(data)
        else:
            result = methods.semantic(data)
        result = methods.strip_private(result)
        result["recommended"] = _pick(method, result)
        results[method] = result

    used_codes = sorted({r["code"] for v in routed.values() for r in v["decision"]["reasons"]})
    used_prereqs = sorted({p["prerequisite_id"] for v in routed.values() for p in v["decision"]["prerequisites"]})
    return {
        "bundle_format": BUNDLE_FORMAT,
        "dataset": {
            "dataset_id": spec.dataset_id,
            "title": spec.title,
            "type_label": spec.type_label,
            "summary": spec.summary,
            "rows": spec.n,
            "id_prefix": spec.unit.id_prefix,
            "id_width": 6 if spec.unit.id_prefix else 5,
            "location": spec.location,
            "breakdown": {
                "label": spec.breakdown_label,
                "values": list(spec.breakdown_values),
                "codes": [int(v) for v in data.breakdown],
            },
            "feature_labels": {f.name: f.label for f in spec.features},
        },
        "assessment": _assessment(spec, data),
        "documents": {d["kind"]: d for d in generated},
        "decisions": {
            k: {
                "role": v["role"],
                "method": v["method"],
                "label": METHOD_LABEL.get(v["method"] or "", None),
                "task": v["task"],
                "evidence": v["evidence"],
                "decision": v["decision"],
            }
            for k, v in routed.items()
        },
        "recommendation": recommendation,
        "results": results,
        "aggregate_rules": _cells(spec),
        "reason_codes": {c: reasons.resolve(c).description for c in used_codes},
        "prerequisites": {
            pid: {"description": CATALOG[pid].description, "remedy": CATALOG[pid].remedy} for pid in used_prereqs
        },
    }


UNIVERSE_SEED_OFFSET = 7919
# Postal areas are a closed set: there are no new ones to expand into.
CLOSED_UNITS = frozenset({"postal_code"})


def build_universe(spec: DatasetSpec, results: dict[str, Any]) -> dict[str, Any] | None:
    """A universe of new records generated like the dataset (another seed, the same size), scored by every
    method's models as fit on the dataset. Like an uploaded universe it has no labels on the page: the dataset's
    held-out evaluation is shown as the expected quality."""
    if spec.unit.type_id in CLOSED_UNITS or not results:
        return None
    data = generate(spec)
    universe = generate(replace(spec, rng_seed=spec.rng_seed + UNIVERSE_SEED_OFFSET))
    none = np.zeros(spec.n, dtype=bool)
    return {
        "bundle_format": BUNDLE_FORMAT,
        "dataset_id": spec.dataset_id,
        "rows": spec.n,
        "id_prefix": f"{spec.unit.id_prefix}u",
        "id_width": 6,
        "breakdown_codes": [int(v) for v in universe.breakdown],
        "expansions": {m: methods.expand(data, m, universe.x, none) for m in results},
    }


def build_workbench(out_dir: Path, *, now: datetime, ttl_hours: float) -> list[Path]:
    root = paths.repo_root()
    world = _world()
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    eng = engine_sha256(root)
    written, entries = [], []
    for spec in DATASETS:
        bundle = build_dataset(spec, world, now, ttl_hours)
        bundle["manifest"] = {
            "evaluated_at": stamp,
            "max_decision_ttl_hours": ttl_hours,
            "engine_version": __version__,
            "engine_sha256": eng,
            "snapshot_sha256": bundle["documents"]["dataset_manifest"]["snapshot"]["sha256"],
            "computed": "build_time",
            "synthetic": True,
            "disclosure": DISCLOSURE,
        }
        bundle["manifest"]["bundle_sha256"] = sha256_of({k: v for k, v in bundle.items() if k != "manifest"})
        path = out_dir / f"{spec.dataset_id}.json"
        # Compact: these files carry tens of thousands of scores and are fetched by the page.
        path.write_text(
            json.dumps(bundle, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n", encoding="utf-8"
        )
        written.append(path)
        universe = build_universe(spec, bundle["results"])
        if universe is not None:
            universe_path = out_dir / f"{spec.dataset_id}.universe.json"
            universe_path.write_text(
                json.dumps(universe, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            written.append(universe_path)
        verdicts = {k: v["decision"]["verdict"] for k, v in bundle["decisions"].items()}
        entries.append(
            {
                "dataset_id": spec.dataset_id,
                "title": spec.title,
                "type_label": spec.type_label,
                "summary": spec.summary,
                "rows": spec.n,
                "unit_label": spec.unit.label,
                "methods": list(spec.methods),
                "verdicts": verdicts,
                "file": f"{spec.dataset_id}.json",
                "universe": {"file": f"{spec.dataset_id}.universe.json", "rows": spec.n} if universe else None,
                "bundle_sha256": bundle["manifest"]["bundle_sha256"],
            }
        )
    index_path = out_dir / "index.json"
    dump_path(
        {
            "bundle_format": BUNDLE_FORMAT,
            "evaluated_at": stamp,
            "engine_version": __version__,
            "engine_sha256": eng,
            "disclosure": DISCLOSURE,
            "datasets": entries,
        },
        index_path,
    )
    return [index_path, *written]
