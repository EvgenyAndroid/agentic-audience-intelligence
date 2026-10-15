"""Uploaded datasets (ADR 0005, stage B): intake, profiling, confirmation and routing for a tenant's own CSV.

The stage A workbench routes generated data; this package routes uploaded data through the same contract
documents, router and ranker. The steps mirror the API:

1. ``parse_csv`` reads a CSV within fixed limits; ``profile_columns`` describes each column from summary
   statistics only (kind, missing share, distinct count) and ``suggest_roles`` proposes which column is the key,
   the seed flag, the behavior flag, the outcome label and the breakdown.
2. A person confirms the roles, the record type, sensitive columns and two attestations (``Confirmation``). The
   rule-based assessment is computed from the confirmed data; no row value ever reaches a language model.
3. ``route`` builds the source profile, manifest, objective, one task per method plus row export, and evidence
   bundles; the router decides each task and the ranker orders the methods.

Evidence is only as strong as what the uploader supplied: rights to use the data and feature timing are facts a
deterministic check cannot establish from a CSV, so they are true only when the uploader attests to them and
otherwise unknown, which leaves the dependent methods PROVISIONAL rather than ELIGIBLE.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Literal

import numpy as np

from aip.recommendation import Candidate, recommend
from aip.registry import DocumentIndex, ReasonCodeRegistry, TypeRegistry
from aip.routing import RouterConfig, decide
from aip.routing.prerequisites import CATALOG
from aip.timeutil import format_ts
from aip.workbench import documents as docs
from aip.workbench.build import METHOD_LABEL, _assessment, _world
from aip.workbench.generate import Synthetic
from aip.workbench.specs import DatasetSpec, Feature, Outcome, Unit

MAX_BYTES = 20 * 1024 * 1024
MAX_ROWS = 200_000
MAX_COLUMNS = 200
MIN_ROWS = 50
MAX_BREAKDOWN_VALUES = 12
NULLS = frozenset({"", "na", "n/a", "null", "none", "nan", "-"})
TRUE = frozenset({"1", "true", "t", "yes", "y"})
FALSE = frozenset({"0", "false", "f", "no", "n"})

ColumnKind = Literal["empty", "binary", "count", "share", "score", "category", "identifier", "text"]
COLLECTION_METHODS = (
    "tag_or_pixel",
    "sdk",
    "server_log",
    "crawl_extraction",
    "survey_response",
    "transaction_record",
    "vendor_model",
    "clean_room_output",
    "other",
)


DEFAULT_LIMITS = (
    "Covers only the records in the uploaded file; who is missing from it is unknown",
    "Column meanings are as confirmed by the uploader and were not checked against a source contract",
)


class UploadError(ValueError):
    """The upload or its confirmation cannot be processed; the message is safe to show the uploader."""


@dataclass(frozen=True)
class Table:
    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    byte_count: int
    sha256: str


@dataclass(frozen=True)
class ColumnProfile:
    name: str
    kind: ColumnKind
    missing_rate: float
    distinct: int
    unique: bool  # every present value differs (a key candidate)
    values: tuple[str, ...] = ()  # only for small categorical columns, so a breakdown can be labeled

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "missing_rate": round(self.missing_rate, 4),
            "distinct": self.distinct,
            "unique": self.unique,
            "values": list(self.values),
        }


def parse_csv(raw: bytes) -> Table:
    if len(raw) > MAX_BYTES:
        raise UploadError(f"The file is larger than {MAX_BYTES // (1024 * 1024)} MB.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise UploadError("The file is not UTF-8 text.") from exc
    reader = csv.reader(io.StringIO(text, newline=""))
    try:
        header = next(reader)
    except StopIteration as exc:
        raise UploadError("The file is empty.") from exc
    columns = tuple(h.strip() for h in header)
    if len(columns) > MAX_COLUMNS:
        raise UploadError(f"The file has more than {MAX_COLUMNS} columns.")
    if len(columns) < 2 or any(not c for c in columns) or len(set(columns)) != len(columns):
        raise UploadError("The header needs at least two columns, each with a distinct, non-empty name.")
    rows = []
    for line, row in enumerate(reader, start=2):
        if not any(cell.strip() for cell in row):
            continue
        if len(row) != len(columns):
            raise UploadError(f"Row {line} has {len(row)} fields; the header has {len(columns)}.")
        rows.append(tuple(cell.strip() for cell in row))
        if len(rows) > MAX_ROWS:
            raise UploadError(f"The file has more than {MAX_ROWS:,} rows.")
    if len(rows) < MIN_ROWS:
        raise UploadError(f"The file needs at least {MIN_ROWS} data rows.")
    return Table(columns, tuple(rows), len(raw), "sha256:" + hashlib.sha256(raw).hexdigest())


def _present(cells: list[str]) -> list[str]:
    return [c for c in cells if c.lower() not in NULLS]


def _number(cell: str) -> float | None:
    try:
        value = float(cell)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def profile_columns(table: Table) -> list[ColumnProfile]:
    out = []
    n = len(table.rows)
    for j, name in enumerate(table.columns):
        cells = [row[j] for row in table.rows]
        present = _present(cells)
        missing = 1 - len(present) / n
        distinct = len(set(present))
        unique = bool(present) and distinct == len(present)
        kind: ColumnKind
        values: tuple[str, ...] = ()
        lowered = {c.lower() for c in present}
        numbers = [_number(c) for c in present]
        if not present:
            kind = "empty"
        elif lowered <= TRUE | FALSE and len(lowered) <= 2:
            kind = "binary"
        elif all(v is not None for v in numbers):
            nums = [v for v in numbers if v is not None]
            if all(v >= 0 and v == int(v) for v in nums):
                kind = "identifier" if unique and distinct == n else "count"
            elif all(0 <= v <= 1 for v in nums):
                kind = "share"
            else:
                kind = "score"
        elif unique:
            kind = "identifier"
        elif distinct <= MAX_BREAKDOWN_VALUES:
            kind = "category"
            values = tuple(sorted(set(present)))
        else:
            kind = "text"
        out.append(ColumnProfile(name, kind, missing, distinct, unique, values))
    return out


ROLE_PATTERNS = {
    "seed": re.compile(r"seed|lookalike|look_alike|best_customer|is_customer"),
    "behavior": re.compile(r"behav|pattern|act_?alike|engaged|researching"),
    "outcome": re.compile(r"outcome|convert|purchase|purchased|won|label|target|churn"),
}


def suggest_roles(profiles: list[ColumnProfile]) -> dict[str, str | None]:
    """A starting point for the confirmation form, from column names and kinds only."""
    key = next((p.name for p in profiles if p.unique and p.missing_rate == 0 and p.kind == "identifier"), None)
    binaries = [p.name for p in profiles if p.kind == "binary"]
    roles: dict[str, str | None] = {"key_column": key}
    taken: set[str] = set()
    for role, pattern in ROLE_PATTERNS.items():
        hit = next((b for b in binaries if b not in taken and pattern.search(b.lower())), None)
        roles[f"{role}_column"] = hit
        if hit:
            taken.add(hit)
    roles["breakdown_column"] = next(
        (p.name for p in profiles if p.kind == "category" and 2 <= p.distinct <= MAX_BREAKDOWN_VALUES), None
    )
    return roles


FEATURE_KINDS: dict[str, Literal["count", "share", "binary", "score"]] = {
    "binary": "binary",
    "count": "count",
    "share": "share",
    "score": "score",
}


@dataclass(frozen=True)
class Confirmation:
    """What the uploader confirms about the file; the API validates and fills this from the request."""

    title: str
    unit_type: str
    unit_label: str
    key_column: str
    observation_start: str  # ISO date
    observation_end: str
    collection_method: str = "other"
    location: Literal["workspace", "cleanroom"] = "workspace"
    seed_column: str | None = None
    seed_label: str | None = None
    behavior_column: str | None = None
    behavior_label: str | None = None
    behavior_features: tuple[str, ...] = ()
    outcome_column: str | None = None
    outcome_label: str | None = None
    outcome_horizon_days: int = 30
    breakdown_column: str | None = None
    sensitive_columns: tuple[str, ...] = ()
    excluded_columns: tuple[str, ...] = ()
    rights_attested: bool = False
    timing_attested: bool = False
    known_limits: tuple[str, ...] = field(default=())


@dataclass(frozen=True)
class Prepared:
    spec: DatasetSpec
    data: Synthetic  # the workbench's data container; for an upload it holds the uploader's rows, not synthetic ones
    confirmation: Confirmation


def _flag(cells: list[str], column: str) -> np.ndarray:
    lowered = [c.lower() for c in cells]
    bad = [c for c in lowered if c not in TRUE | FALSE and c not in NULLS]
    if bad:
        raise UploadError(f"Column '{column}' must hold yes/no values (1/0, true/false).")
    return np.array([c in TRUE for c in lowered], dtype=bool)


def prepare(table: Table, conf: Confirmation, dataset_id: str) -> Prepared:
    """Validate the confirmation against the table and build the workbench spec and data container."""
    types = TypeRegistry.load()
    entry = types.get(conf.unit_type, docs.V)
    if entry is None:
        raise UploadError(f"Unknown record type '{conf.unit_type}'.")
    if conf.collection_method not in COLLECTION_METHODS:
        raise UploadError(f"Unknown collection method '{conf.collection_method}'.")
    profiles = {p.name: p for p in profile_columns(table)}
    named = [
        conf.key_column,
        conf.seed_column,
        conf.behavior_column,
        conf.outcome_column,
        conf.breakdown_column,
        *conf.sensitive_columns,
        *conf.excluded_columns,
        *conf.behavior_features,
    ]
    for name in named:
        if name is not None and name not in profiles:
            raise UploadError(f"Column '{name}' is not in the file.")
    key = profiles[conf.key_column]
    if not key.unique or key.missing_rate > 0:
        raise UploadError(f"The key column '{conf.key_column}' must be present and distinct on every row.")
    for role in (conf.seed_column, conf.behavior_column, conf.outcome_column):
        if role is not None and profiles[role].kind != "binary":
            raise UploadError(f"Column '{role}' must hold yes/no values (1/0, true/false).")
    if conf.breakdown_column is not None and profiles[conf.breakdown_column].kind != "category":
        raise UploadError(
            f"The breakdown column '{conf.breakdown_column}' needs 2 to {MAX_BREAKDOWN_VALUES} distinct labels."
        )

    roles = {conf.key_column, conf.seed_column, conf.behavior_column, conf.outcome_column, conf.breakdown_column}
    excluded = set(conf.excluded_columns)
    feature_names = [
        p.name for p in profiles.values() if p.name not in roles and p.name not in excluded and p.kind in FEATURE_KINDS
    ]
    sensitive = set(conf.sensitive_columns)
    usable = [f for f in feature_names if f not in sensitive]
    if not usable:
        raise UploadError("No numeric or yes/no columns are left to model on.")
    behavioral = set(conf.behavior_features)
    for name in behavioral:
        if name not in feature_names:
            raise UploadError(f"Behavior signal '{name}' is not a numeric or yes/no feature column.")

    index = {c: j for j, c in enumerate(table.columns)}

    def column(name: str) -> list[str]:
        j = index[name]
        return [row[j] for row in table.rows]

    def numeric(name: str) -> np.ndarray:
        cells = column(name)
        if profiles[name].kind == "binary":
            return np.array(
                [np.nan if c.lower() in NULLS else (1.0 if c.lower() in TRUE else 0.0) for c in cells], dtype=float
            )
        return np.array([np.nan if c.lower() in NULLS else float(c) for c in cells], dtype=float)

    features = tuple(
        Feature(
            name=name,
            label=name.replace("_", " ").capitalize(),
            kind=FEATURE_KINDS[profiles[name].kind],
            family="behavioral" if name in behavioral else "declared",
            means=(0.0,),
            missing=profiles[name].missing_rate,
            sensitive=name in sensitive,
        )
        for name in feature_names
    )
    x = np.column_stack([numeric(f.name) for f in features])
    n = len(table.rows)

    seed = np.flatnonzero(_flag(column(conf.seed_column), conf.seed_column)) if conf.seed_column else np.array([], int)
    behavior = (
        np.flatnonzero(_flag(column(conf.behavior_column), conf.behavior_column))
        if conf.behavior_column
        else np.array([], int)
    )
    outcome = _flag(column(conf.outcome_column), conf.outcome_column).astype(np.int8) if conf.outcome_column else None
    if conf.seed_column and len(seed) < 20:
        raise UploadError(f"The seed column '{conf.seed_column}' marks fewer than 20 records.")
    if conf.behavior_column and (len(behavior) < 20 or not behavioral):
        raise UploadError("Act-alike modeling needs a behavior column marking 20 or more records and behavior signals.")

    if conf.breakdown_column:
        labels = profiles[conf.breakdown_column].values
        cells = column(conf.breakdown_column)
        breakdown_values = (*labels, "Unknown") if any(c not in labels for c in cells) else labels
        breakdown = np.array([breakdown_values.index(c) if c in labels else len(labels) for c in cells])
        breakdown_label = conf.breakdown_column.replace("_", " ").capitalize()
    else:
        breakdown_values, breakdown, breakdown_label = ("All records",), np.zeros(n, dtype=int), "Records"

    methods: list[Literal["lookalike", "actalike", "propensity"]] = []
    if conf.seed_column:
        methods.append("lookalike")
    if conf.behavior_column:
        methods.append("actalike")
    if conf.outcome_column:
        methods.append("propensity")
    if not methods:
        raise UploadError("Choose at least one of a seed column, a behavior column or an outcome column.")

    spec = DatasetSpec(
        dataset_id=dataset_id,
        title=conf.title,
        type_label="Uploaded data",
        summary=f"{n:,} {conf.unit_label.lower()} records uploaded for audience modeling.",
        unit=Unit(conf.unit_type, f"upload_{dataset_id}", conf.key_column, "", conf.unit_label),
        n=n,
        segment_probs=(1.0,),
        segment_labels=("All records",),
        features=features,
        breakdown_label=breakdown_label,
        breakdown_values=tuple(breakdown_values),
        breakdown_by_segment=((1.0,),),
        collection_method=conf.collection_method,
        location=conf.location,
        methods=tuple(methods),
        seed_label=conf.seed_label or conf.seed_column,
        seed_size=len(seed),
        behavior_label=conf.behavior_label or conf.behavior_column,
        behavior_features=tuple(sorted(behavioral)),
        behavior_share=len(behavior) / n,
        outcome=Outcome(
            event=conf.outcome_column,
            label=conf.outcome_label or conf.outcome_column,
            horizon_days=conf.outcome_horizon_days,
            weights={},
            base_rate=float(outcome.mean()) if outcome is not None else 0.0,
        )
        if conf.outcome_column and outcome is not None
        else None,
        known_limits=conf.known_limits or DEFAULT_LIMITS,
    )
    data = Synthetic(spec, x, np.zeros(n, dtype=int), breakdown, seed, behavior, outcome)
    return Prepared(spec, data, conf)


def _steward(tenant_id: str) -> dict[str, str]:
    return {"actor_id": f"user_{tenant_id}_steward", "actor_type": "human", "role": "data_steward"}


def _documents(prep: Prepared, table: Table, tenant_id: str, now: datetime) -> list[dict[str, Any]]:
    spec, conf = prep.spec, prep.confirmation
    stamp = format_ts(now)
    profile = docs.profile(spec)
    profile.update(
        tenant_id=tenant_id,
        family_label=f"{conf.title} (upload)",
        collection_method_detail="Uploaded as a CSV file; roles, record type and sensitive columns confirmed by the "
        "uploader.",
        steward_confirmation={"actor": _steward(tenant_id), "confirmed_at": stamp},
    )
    profile["coverage"]["observable_population"] = f"{spec.n:,} uploaded {conf.unit_label.lower()} records"
    profile["time_semantics"].update(
        event_time_meaning="As stated by the uploader", availability_rule="Batch upload", expected_delivery_lag_hours=0
    )
    manifest = docs.manifest(spec, prep.data)
    manifest.update(tenant_id=tenant_id, received_at=stamp)
    manifest["snapshot"].update(
        storage_ref=f"upload://{tenant_id}/{spec.dataset_id}",
        sha256=table.sha256,
        byte_count=table.byte_count,
        created_at=stamp,
    )
    manifest["observation_period"] = {
        "start": f"{conf.observation_start}T00:00:00Z",
        "end": f"{conf.observation_end}T23:59:59Z",
    }
    objective = docs.objective(spec)
    objective.update(tenant_id=tenant_id, intended_use="Audience modeling on uploaded data")
    return [profile, manifest, objective]


def _evidence(prep: Prepared, task: dict[str, Any], method: str | None, now: datetime) -> dict[str, Any]:
    bundle = docs.evidence(prep.spec, prep.data, task, method)
    conf = prep.confirmation
    attested = {"P-RIGHTS-USE": conf.rights_attested, "P-FEATURE-TIMING": conf.timing_attested}
    unattested_reason = {"P-RIGHTS-USE": "unverified_permission", "P-FEATURE-TIMING": "missing_availability_evidence"}
    for fact in bundle["facts"]:
        fact["observed_at"] = format_ts(now)
        pid = fact["prerequisite_id"]
        if pid in attested:
            fact.update(
                value=True if attested[pid] else None,
                established_by="steward_confirmation",
                reason_code=None if attested[pid] else unattested_reason[pid],
            )
        elif pid == "P-SENSITIVE-EXCLUSION":
            fact["established_by"] = "steward_confirmation"
    bundle["assembled_at"] = format_ts(now)
    return bundle


def assessment(prep: Prepared) -> dict[str, Any]:
    """The workbench's rule-based assessment, computed from the confirmed upload."""
    return _assessment(prep.spec, prep.data)


UPLOAD_POLICIES = (
    "exec_workspace_demo",
    "output_workbench_demo",
    "exec_cleanroom_demo",
    "output_cleanroom_aggregate_only",
)
POLICY_DAYS = 30


def tenant_policies(tenant_id: str, now: datetime) -> list[dict[str, Any]]:
    """The workbench's location policies, issued to one upload tenant. Policies are tenant-scoped, so the router
    refuses another tenant's; each invite key's tenant gets its own copy, effective from now for POLICY_DAYS and
    retaining outputs no longer than uploads are kept."""
    world = _world()
    out = []
    for doc in world.all("execution_policy") + world.all("output_policy"):
        if doc["policy_id"] not in UPLOAD_POLICIES:
            continue
        copy = json.loads(json.dumps(doc))
        copy.update(
            tenant_id=tenant_id,
            authority_ref="upload_invite_terms_v1",
            effective_from=format_ts(now - timedelta(days=1)),
            effective_until=format_ts(now + timedelta(days=POLICY_DAYS)),
        )
        if "retention_days" in copy:
            copy["retention_days"] = 1
        out.append(copy)
    return out


def route(prep: Prepared, table: Table, *, tenant_id: str, now: datetime, ttl_hours: float = 24.0) -> dict[str, Any]:
    """Decide every task for an uploaded dataset and rank the methods; the same bundle shape as the workbench,
    without modeling results (a later slice trains and scores eligible methods)."""
    spec = prep.spec
    types, reasons = TypeRegistry.load(), ReasonCodeRegistry.load()
    config = RouterConfig(max_decision_ttl=timedelta(hours=ttl_hours))
    index = DocumentIndex(tenant_policies(tenant_id, now))
    generated = _documents(prep, table, tenant_id, now)
    for doc in generated:
        index.add(doc)

    routed: dict[str, dict[str, Any]] = {}
    candidates: list[Candidate] = []
    for role, method, task in docs.tasks_for(spec):
        task.update(tenant_id=tenant_id, created_at=format_ts(now), created_by=_steward(tenant_id))
        bundle = _evidence(prep, task, method, now)
        decision = decide(task, documents=index, bundle=bundle, types=types, reasons=reasons, config=config, now=now)
        routed[method or role] = {
            "role": role,
            "method": method,
            "label": METHOD_LABEL.get(method or "", None),
            "task": task,
            "evidence": bundle,
            "decision": decision,
        }
        if role == "method":
            candidates.append(Candidate(task, decision))

    recommendation = recommend(
        recommendation_id=f"rec_{spec.dataset_id}",
        objective=generated[2],
        requested=candidates[0],
        alternatives=candidates[1:],
        now=now,
    )
    used_codes = sorted({r["code"] for v in routed.values() for r in v["decision"]["reasons"]})
    used_prereqs = sorted({p["prerequisite_id"] for v in routed.values() for p in v["decision"]["prerequisites"]})
    return {
        "dataset": {
            "dataset_id": spec.dataset_id,
            "title": spec.title,
            "type_label": spec.type_label,
            "summary": spec.summary,
            "rows": spec.n,
            "location": spec.location,
            "breakdown": {"label": spec.breakdown_label, "values": list(spec.breakdown_values)},
            "feature_labels": {f.name: f.label for f in spec.features},
        },
        "assessment": _assessment(spec, prep.data),
        "documents": {d["kind"]: d for d in generated},
        "decisions": routed,
        "recommendation": recommendation,
        "results": {},
        "reason_codes": {c: reasons.resolve(c).description for c in used_codes},
        "prerequisites": {
            pid: {"description": CATALOG[pid].description, "remedy": CATALOG[pid].remedy} for pid in used_prereqs
        },
    }
