"""Deterministic prerequisite checks. Facts come only from non-agent authorities (FR38)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from aip.contracts.semantic import semantic_issues
from aip.contracts.validator import SchemaSet
from aip.policy.compose import Outcome, artifact_permission, combine, compose_aggregation_rules, operation_permission
from aip.registry.documents import DocumentIndex
from aip.registry.types import TypeRegistry
from aip.routing.prerequisites import CATALOG

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

    def _grain_compatible(self) -> Outcome:
        units = self.task["units"]
        modeling, output = units["modeling_unit"], units["output_unit"]
        if modeling is None:
            return Outcome("P-GRAIN-COMPATIBLE", "satisfied", detail="no modeling unit")
        mismatched = [o["unit"] for o in units["observation_units"] if o["unit"] != modeling]
        if output is not None and output != modeling:
            mismatched.append(output)
        if not mismatched:
            return Outcome("P-GRAIN-COMPATIBLE", "satisfied")
        unrelatable = [u["type_id"] for u in mismatched if not self.types.relationship_allowed(u, modeling)]
        if unrelatable:
            # The registry declares no relationship between these types: no mapping can make them comparable (FR03).
            return Outcome("P-GRAIN-COMPATIBLE", "violated", "grain_incompatible", tuple(unrelatable))
        # A relationship is permitted, but no unit-mapping contract exists yet, so no supplied or absent mapping
        # can establish compatibility. Missing evidence, not a violation (FR03, FR06).
        return Outcome(
            "P-GRAIN-COMPATIBLE",
            "missing",
            "missing_unit_mapping",
            tuple(r["id"] for r in units["mapping_refs"]) or tuple(u["type_id"] for u in mismatched),
            detail="approved unit mapping not established",
        )

    def _exec_operation(self) -> Outcome:
        lookup = self._policies("execution_policy", "execution_policy_refs", "execution")
        outcome = operation_permission(
            lookup.by_source, self.task["execution_location_ref"], self.task["operation"], self.now
        )
        return combine("P-EXEC-OPERATION", [*self._unresolved("P-EXEC-OPERATION", lookup), outcome])

    def _output_artifact(self) -> Outcome:
        lookup = self._policies("output_policy", "output_policy_refs", "output")
        output = self.task["units"]["output_unit"]
        outcome = artifact_permission(
            lookup.by_source,
            self.task["execution_location_ref"],
            self.task["requested_artifact"],
            output["type_id"] if output else None,
            self.task["destination_ref"],
            self.now,
        )
        return combine("P-OUTPUT-ARTIFACT", [*self._unresolved("P-OUTPUT-ARTIFACT", lookup), outcome])

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
