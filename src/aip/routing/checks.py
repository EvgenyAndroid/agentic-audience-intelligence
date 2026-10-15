"""Deterministic prerequisite checks. Facts come only from non-agent authorities (FR38)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from aip.contracts.semantic import semantic_issues
from aip.contracts.validator import SchemaSet
from aip.policy.compose import Outcome, artifact_permission, combine, compose_aggregation_rules, operation_permission
from aip.registry.documents import DocumentIndex
from aip.registry.types import TypeRegistry
from aip.routing.prerequisites import CATALOG
from aip.timeutil import parse_ts


def _cardinality_holds(declared: str, observed: dict[str, int]) -> bool:
    per_source, per_target = observed["max_targets_per_source"], observed["max_sources_per_target"]
    return {
        "one_to_one": per_source <= 1 and per_target <= 1,
        "many_to_one": per_source <= 1,
        "one_to_many": per_target <= 1,
        "many_to_many": True,
    }[declared]


MODEL_SCORE_TYPES = {
    "seed_affinity": {"seed_affinity", "rank"},
    "behavioral_affinity": {"behavioral_affinity", "rank"},
    "semantic_similarity": {"semantic_similarity", "rank"},
    "outcome_propensity": {"outcome_probability"},
}

TASK_SOURCE = "task"  # task-level policy refs; they can tighten constraints but never stand in for a source


@dataclass
class PolicyLookup:
    by_source: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    unresolved: dict[str, list[str]] = field(default_factory=dict)
    foreign: list[str] = field(default_factory=list)


@dataclass
class RoutingContext:
    task: dict[str, Any]
    documents: DocumentIndex
    facts: Mapping[str, dict[str, Any]]
    types: TypeRegistry
    schemas: SchemaSet
    now: datetime
    policies_used: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)

    # ---------- lineage ----------
    def datasets(self) -> list[dict[str, Any] | None]:
        return [self.documents.get("dataset_manifest", ref) for ref in self.task["input_snapshot_refs"]]

    def profiles(self) -> dict[str, dict[str, Any] | None]:
        out: dict[str, dict[str, Any] | None] = {}
        for ds in self.datasets():
            if ds is not None:
                ref = ds["source_profile_ref"]
                out[f"{ref['id']}@{ref['version']}"] = self.documents.get("source_profile", ref)
        return out

    def _policy_lookup(self, kind: str, profile_field: str, task_field: str) -> PolicyLookup:
        """Resolve policy refs per source. Unresolved and foreign-tenant refs are kept, never silently dropped."""
        lookup = PolicyLookup()
        sources = [(key, profile[profile_field] if profile else []) for key, profile in self.profiles().items()]
        task_refs = self.task["policy_refs"][task_field]
        if task_refs:
            sources.append((TASK_SOURCE, task_refs))
        for source, refs in sources:
            lookup.by_source[source] = []
            for ref in refs:
                label = f"{kind}:{ref['id']}@{ref['version']}"
                policy = self.documents.get(kind, ref)
                if policy is None:
                    lookup.unresolved.setdefault(source, []).append(label)
                elif policy["tenant_id"] != self.task["tenant_id"]:
                    lookup.foreign.append(label)  # reference only; the foreign policy's content is never used
                else:
                    lookup.by_source[source].append(policy)
        return lookup

    def _policies(self, kind: str, profile_field: str, task_field: str) -> PolicyLookup:
        lookup = self._policy_lookup(kind, profile_field, task_field)
        for policies in lookup.by_source.values():
            for p in policies:
                self.policies_used[(p["policy_id"], p["policy_version"])] = p
        return lookup

    @staticmethod
    def _unresolved(pid: str, lookup: PolicyLookup) -> list[Outcome]:
        return [
            Outcome(pid, "missing", "missing_document", tuple(labels), detail=f"unresolved policy refs in {source}")
            for source, labels in lookup.unresolved.items()
        ]

    def objective(self) -> dict[str, Any] | None:
        return self.documents.get("objective", self.task["objective_ref"])

    # ---------- evaluation ----------
    def evaluate(self, pid: str) -> Outcome:
        prerequisite = CATALOG[pid]
        if prerequisite.source == "fact":
            return self._fact(pid)
        return getattr(self, "_" + pid[2:].lower().replace("-", "_"))()

    def _fact(self, pid: str) -> Outcome:
        fact = self.facts.get(pid)
        if fact is None:
            return Outcome(pid, "missing", CATALOG[pid].default_missing_reason, detail="fact not supplied")
        refs, by = tuple(fact["evidence_refs"]), fact["established_by"]
        if fact["value"] is True:
            return Outcome(pid, "satisfied", None, refs, by)
        if fact["value"] is False:
            if not fact["reason_code"]:
                raise ValueError(f"fact {pid} is False but carries no reason code")
            return Outcome(pid, "violated", fact["reason_code"], refs, by)
        return Outcome(pid, "missing", fact["reason_code"] or CATALOG[pid].default_missing_reason, refs, by)

    def _contract_valid(self) -> Outcome:
        issues = self.schemas.issues(self.task, "task") or semantic_issues(self.task)
        if issues:
            return Outcome("P-CONTRACT-VALID", "violated", "contract_invalid", detail=issues[0].message)
        return Outcome("P-CONTRACT-VALID", "satisfied")

    def _tenant_scope(self) -> Outcome:
        tenant = self.task["tenant_id"]
        docs = [d for d in self.datasets() if d] + [p for p in self.profiles().values() if p] + [self.objective() or {}]
        docs += self._resolved("unit_mapping", self.task["units"]["mapping_refs"])[0]
        docs += self._resolved("relationship_snapshot", self.task["units"].get("relationship_snapshot_refs", []))[0]
        docs += [m for m in (self._model(),) if m]
        foreign = [d for d in docs if d and d.get("tenant_id") not in (None, tenant)]
        checked, foreign_refs = [], []
        for kind, profile_field, task_field in (
            ("execution_policy", "execution_policy_refs", "execution"),
            ("output_policy", "output_policy_refs", "output"),
        ):
            lookup = self._policy_lookup(kind, profile_field, task_field)
            checked += [
                f"{kind}:{p['policy_id']}@{p['policy_version']}" for ps in lookup.by_source.values() for p in ps
            ]
            foreign_refs += lookup.foreign
        if foreign or foreign_refs:
            return Outcome("P-TENANT-SCOPE", "violated", "tenant_scope_mismatch", tuple(sorted(set(foreign_refs))))
        return Outcome("P-TENANT-SCOPE", "satisfied", None, tuple(sorted(set(checked))))

    def _snapshot_immutable(self) -> Outcome:
        results = []
        for ref, ds in zip(self.task["input_snapshot_refs"], self.datasets(), strict=True):
            if ds is None:
                results.append(Outcome("P-SNAPSHOT-IMMUTABLE", "missing", "missing_document", detail=ref["id"]))
            elif ds["dataset_state"] == "withdrawn":
                results.append(Outcome("P-SNAPSHOT-IMMUTABLE", "violated", "source_withdrawn", (ds["dataset_id"],)))
            else:
                results.append(Outcome("P-SNAPSHOT-IMMUTABLE", "satisfied", None, (ds["snapshot"]["sha256"],)))
        return combine("P-SNAPSHOT-IMMUTABLE", results)

    def _profile_confirmed(self) -> Outcome:
        results = []
        for key, profile in self.profiles().items():
            if profile is None or profile["profile_state"] in ("draft", "quarantined"):
                results.append(Outcome("P-PROFILE-CONFIRMED", "missing", "unregistered_source_profile", (key,)))
            elif profile["profile_state"] == "retired":
                results.append(Outcome("P-PROFILE-CONFIRMED", "violated", "source_withdrawn", (key,)))
            else:
                results.append(Outcome("P-PROFILE-CONFIRMED", "satisfied", None, (key,)))
        return combine("P-PROFILE-CONFIRMED", results)

    def _units_declared(self) -> Outcome:
        units = self.task["units"]
        declared = [
            units[k] for k in ("modeling_unit", "output_unit", "activation_unit", "measurement_unit") if units[k]
        ]
        declared += [o["unit"] for o in units["observation_units"]]
        unconfirmed = [u["type_id"] for u in declared if not self.types.is_confirmed(u)]
        if unconfirmed:
            return Outcome("P-UNITS-DECLARED", "missing", "missing_unit_semantics", tuple(unconfirmed))
        for obs in units["observation_units"]:
            ds = self.documents.get("dataset_manifest", obs["dataset_ref"])
            profile = self.documents.get("source_profile", ds["source_profile_ref"]) if ds else None
            if profile and obs["unit"] not in [u["unit"] for u in profile["observation_units"]]:
                return Outcome(
                    "P-UNITS-DECLARED",
                    "violated",
                    "grain_incompatible",
                    (profile["profile_id"],),
                    detail="task observation unit differs from the unit declared by the source contract",
                )
        return Outcome("P-UNITS-DECLARED", "satisfied")

    def _resolved(self, kind: str, refs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
        found, unresolved = [], []
        for ref in refs:
            doc = self.documents.get(kind, ref)
            if doc is None:
                unresolved.append(f"{kind}:{ref['id']}@{ref['version']}")
            else:
                found.append(doc)
        return found, unresolved

    def _grain_compatible(self) -> Outcome:
        pid = "P-GRAIN-COMPATIBLE"
        units = self.task["units"]
        modeling, output = units["modeling_unit"], units["output_unit"]
        if modeling is None:
            return Outcome(pid, "satisfied", detail="no modeling unit")
        needed = [("observation", o["unit"], modeling) for o in units["observation_units"] if o["unit"] != modeling]
        if output is not None and output != modeling:
            needed.append(("output", modeling, output))
        if not needed:
            return Outcome(pid, "satisfied")
        unrelatable = [
            (src if role == "observation" else dst)["type_id"]
            for role, src, dst in needed
            if not self.types.relationship_allowed(src, dst)
        ]
        if unrelatable:
            # The registry declares no relationship between these types: no mapping can make them comparable (FR03).
            return Outcome(pid, "violated", "grain_incompatible", tuple(unrelatable))
        tenant = self.task["tenant_id"]
        mappings, unresolved_m = self._resolved("unit_mapping", units["mapping_refs"])
        snapshots, unresolved_s = self._resolved("relationship_snapshot", units.get("relationship_snapshot_refs", []))
        mappings = [m for m in mappings if m["tenant_id"] == tenant]  # foreign documents fail P-TENANT-SCOPE
        snapshots = [x for x in snapshots if x["tenant_id"] == tenant]
        outcomes = [
            Outcome(pid, "missing", "missing_document", tuple(labels), detail="unresolved mapping or snapshot refs")
            for labels in (unresolved_m, unresolved_s)
            if labels
        ]
        for role, src, dst in needed:
            candidates = [m for m in mappings if m["source_unit"] == src and m["target_unit"] == dst]
            if not candidates:
                outcomes.append(
                    Outcome(
                        pid,
                        "missing",
                        "missing_unit_mapping",
                        (f"{src['type_id']}/{dst['type_id']}",),
                        detail=f"no cited {role} mapping from {src['type_id']} to {dst['type_id']}",
                    )
                )
                continue
            results = [self._mapping_outcome(role, m, snapshots) for m in candidates]
            usable = [r for r in results if r.outcome == "satisfied"]
            outcomes.append(usable[0] if usable else combine(pid, results))
        return combine(pid, outcomes)

    def _required_use(self, role: str, mapping: dict[str, Any]) -> str:
        """Observation mappings build features (or measurement links); output mappings aggregate or re-key."""
        if role == "observation":
            return "measurement_mapping" if self.task["operation"] == "measure" else "feature_join"
        return "aggregation" if mapping["cardinality"] == "many_to_one" else "activation_mapping"

    def _mapping_outcome(self, role: str, mapping: dict[str, Any], snapshots: list[dict[str, Any]]) -> Outcome:
        pid = "P-GRAIN-COMPATIBLE"
        label = f"unit_mapping:{mapping['mapping_id']}@{mapping['mapping_version']}"
        if mapping["mapping_state"] == "revoked":
            return Outcome(pid, "violated", "mapping_revoked", (label,))
        use = self._required_use(role, mapping)
        if use not in mapping["permitted_uses"]:
            # A documented restriction: an activation-only mapping cannot build features (PRD section 3).
            return Outcome(pid, "violated", "mapping_use_not_permitted", (label,), detail=f"{use} not permitted")
        start, end = parse_ts(mapping["effective_from"]), mapping["effective_until"]
        if mapping["mapping_state"] != "approved" or start > self.now or (end and parse_ts(end) <= self.now):
            return Outcome(
                pid, "missing", "missing_unit_mapping", (label,), detail="mapping not approved or not effective"
            )
        bound = [
            x
            for x in snapshots
            if (x["mapping_ref"]["id"], x["mapping_ref"]["version"])
            == (mapping["mapping_id"], mapping["mapping_version"])
        ]
        snap_labels = tuple(f"relationship_snapshot:{x['snapshot_id']}@{x['snapshot_version']}" for x in bound)
        if any(x["snapshot_state"] == "revoked" for x in bound):
            return Outcome(pid, "violated", "relationship_snapshot_revoked", snap_labels)
        known = [x for x in bound if parse_ts(x["available_at"]) <= self.now]
        if not known:
            # Cutoff-level availability is checked separately under P-FEATURE-TIMING (FR07).
            return Outcome(
                pid,
                "missing",
                "missing_relationship_evidence",
                (label, *snap_labels),
                detail="no relationship snapshot available at decision time",
            )
        for x in known:
            if not _cardinality_holds(mapping["cardinality"], x["observed_cardinality"]):
                return Outcome(pid, "violated", "mapping_cardinality_mismatch", (label, *snap_labels))
        return Outcome(pid, "satisfied", None, (label, *snap_labels))

    def _sources_then_task(
        self, pid: str, lookup: PolicyLookup, check: Callable[[dict[str, list[dict[str, Any]]]], Outcome]
    ) -> Outcome:
        """Contributing sources must each permit; task-level policies can only tighten (ADR 0003).

        A task-level prohibition or restriction applies; task-level silence or permission adds nothing and grants
        nothing. Unresolved refs from either side stay missing (FR05).
        """
        sources = {k: ps for k, ps in lookup.by_source.items() if k != TASK_SOURCE}
        outcomes = [*self._unresolved(pid, lookup), check(sources)]
        if TASK_SOURCE in lookup.by_source:
            task_outcome = check({TASK_SOURCE: lookup.by_source[TASK_SOURCE]})
            if task_outcome.outcome == "violated":
                outcomes.append(task_outcome)
        return combine(pid, outcomes)

    def _exec_operation(self) -> Outcome:
        lookup = self._policies("execution_policy", "execution_policy_refs", "execution")
        return self._sources_then_task(
            "P-EXEC-OPERATION",
            lookup,
            lambda by_source: operation_permission(
                by_source, self.task["execution_location_ref"], self.task["operation"], self.now
            ),
        )

    def _output_artifact(self) -> Outcome:
        lookup = self._policies("output_policy", "output_policy_refs", "output")
        output = self.task["units"]["output_unit"]
        return self._sources_then_task(
            "P-OUTPUT-ARTIFACT",
            lookup,
            lambda by_source: artifact_permission(
                by_source,
                self.task["execution_location_ref"],
                self.task["requested_artifact"],
                output["type_id"] if output else None,
                self.task["destination_ref"],
                self.now,
            ),
        )

    def _aggregation_rules(self) -> Outcome:
        pid = "P-AGGREGATION-RULES"
        lookup = self._policies("output_policy", "output_policy_refs", "output")
        artifact = self.task["requested_artifact"] or "aggregate_report"
        location = self.task["execution_location_ref"]
        # Every contributing source must supply applicable rules; task-level policies can only tighten them (FR29).
        sources = {k: ps for k, ps in lookup.by_source.items() if k != TASK_SOURCE}
        silent = [
            k
            for k, ps in sources.items()
            if not compose_aggregation_rules(ps, artifact, self.now, location_id=location)
        ]
        unresolved = self._unresolved(pid, lookup)
        if not sources or silent:
            return combine(
                pid,
                [
                    *unresolved,
                    Outcome(pid, "missing", "aggregation_rules_unknown", tuple(silent), detail=", ".join(silent)),
                ],
            )
        policies = [p for ps in lookup.by_source.values() for p in ps]
        rules = compose_aggregation_rules(policies, artifact, self.now, location_id=location)
        refs = tuple(r for rule in rules for r in rule.rule_ids)
        return combine(pid, [*unresolved, Outcome(pid, "satisfied", None, refs)])

    # ---------- registered models (FR44, FR45) ----------
    def _model(self) -> dict[str, Any] | None:
        ref = self.task["model_ref"]
        return self.documents.get("model_registration", ref) if ref else None

    def _model_registered(self) -> Outcome:
        pid = "P-MODEL-REGISTERED"
        model = self._model()
        if model is None or model["tenant_id"] != self.task["tenant_id"]:  # a foreign model fails P-TENANT-SCOPE
            return Outcome(pid, "missing", "missing_model_registration")
        label = f"model_registration:{model['model_id']}@{model['model_version']}"
        if model["registration_state"] == "revoked":
            return Outcome(pid, "violated", "model_registration_revoked", (label,))
        end = model["valid_until"]
        current = parse_ts(model["valid_from"]) <= self.now and (end is None or self.now < parse_ts(end))
        if model["registration_state"] != "registered" or not current:
            return Outcome(pid, "missing", "model_registration_not_current", (label,))
        # The returned output must be the claim the task asks for, at the task's units.
        units, family = self.task["units"], self.task["task_family"]
        mismatches = []
        if model["task_family"] != family:
            mismatches.append("task_family")
        allowed = MODEL_SCORE_TYPES.get(family)
        if allowed is not None and model["score_type"] not in allowed:
            mismatches.append("score_type")
        if model["modeling_unit"] != units["modeling_unit"] or model["output_unit"] != units["output_unit"]:
            mismatches.append("units")
        objective = self.objective()
        if family == "outcome_propensity" and objective and objective.get("target") != model["target"]:
            mismatches.append("target")
        if mismatches:
            return Outcome(pid, "violated", "model_contract_mismatch", (label,), detail=", ".join(mismatches))
        return Outcome(pid, "satisfied", None, (label,))

    def _model_execution(self) -> Outcome:
        pid = "P-MODEL-EXECUTION"
        model = self._model()
        if model is None or model["tenant_id"] != self.task["tenant_id"]:
            return Outcome(pid, "missing", "missing_model_registration")
        label = f"model_registration:{model['model_id']}@{model['model_version']}"
        execution, remote = model["execution"], self.task["operation"] == "remote_inference"
        if execution["mode"] == "remote_endpoint" and not remote:
            return Outcome(
                pid,
                "violated",
                "model_execution_mismatch",
                (label,),
                detail="endpoint model must be run as remote_inference so the payload transfer is checked",
            )
        if execution["mode"] == "in_boundary" and remote:
            return Outcome(
                pid, "violated", "model_execution_mismatch", (label,), detail="in-boundary model has no endpoint"
            )
        if self.task["execution_location_ref"] not in execution["permitted_location_ids"]:
            return Outcome(pid, "violated", "model_execution_mismatch", (label,), detail="location not registered")
        return Outcome(pid, "satisfied", None, (label,))

    def _remote_payload(self) -> Outcome:
        """Calling an endpoint transfers its payload across the boundary even when no file is saved (FR45, FR28)."""
        pid = "P-REMOTE-PAYLOAD"
        model = self._model()
        endpoint = model["execution"]["endpoint"] if model and model["tenant_id"] == self.task["tenant_id"] else None
        if endpoint is None:
            return Outcome(pid, "missing", "missing_model_registration")
        lookup = self._policies("output_policy", "output_policy_refs", "output")
        modeling = self.task["units"]["modeling_unit"]
        return self._sources_then_task(
            pid,
            lookup,
            lambda by_source: artifact_permission(
                by_source,
                self.task["execution_location_ref"],
                endpoint["payload_artifact_type"],
                modeling["type_id"] if modeling else None,
                endpoint["endpoint_id"],
                self.now,
            ),
        )

    def _objective_field(self, pid: str, field_name: str) -> Outcome:
        objective = self.objective()
        if objective is None:
            return Outcome(pid, "missing", "missing_document", detail="objective not resolved")
        if objective.get(field_name) is None:
            return Outcome(pid, "missing", CATALOG[pid].default_missing_reason)
        return Outcome(pid, "satisfied", None, (objective[field_name]["id"],))

    def _seed_present(self) -> Outcome:
        return self._objective_field("P-SEED-PRESENT", "seed_ref")

    def _universe_defined(self) -> Outcome:
        return self._objective_field("P-UNIVERSE-DEFINED", "eligible_universe_ref")

    def _content_brief(self) -> Outcome:
        return self._objective_field("P-CONTENT-BRIEF", "content_brief_ref")
