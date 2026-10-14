"""Prerequisite catalog and the operation/task-family matrix that selects prerequisites for a task."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class Prerequisite:
    pid: str
    description: str
    source: Literal["computed", "fact"]
    default_missing_reason: str
    remedy: str


CATALOG: dict[str, Prerequisite] = {
    p.pid: p
    for p in [
        Prerequisite(
            "P-CONTRACT-VALID",
            "Task document passes schema and semantic validation",
            "computed",
            "contract_invalid",
            "Correct the task contract and resubmit",
        ),
        Prerequisite(
            "P-TENANT-SCOPE",
            "Inputs and policies belong to the task's tenant",
            "computed",
            "missing_document",
            "Use only artifacts from the authenticated tenant",
        ),
        Prerequisite(
            "P-SNAPSHOT-IMMUTABLE",
            "Every input resolves to an immutable, non-withdrawn snapshot",
            "computed",
            "missing_document",
            "Register the immutable snapshot or replace the withdrawn input",
        ),
        Prerequisite(
            "P-PROFILE-CONFIRMED",
            "Every contributing source profile is steward-confirmed",
            "computed",
            "unregistered_source_profile",
            "Complete steward confirmation of the source profile",
        ),
        Prerequisite(
            "P-UNITS-DECLARED",
            "Every task unit is registered, confirmed and declared by the source contract",
            "computed",
            "missing_unit_semantics",
            "Register and confirm the unit type, or correct the declared unit",
        ),
        Prerequisite(
            "P-GRAIN-COMPATIBLE",
            "Observation, modeling and output units match or have approved mappings",
            "computed",
            "missing_unit_mapping",
            "Supply an approved mapping or choose a compatible modeling unit",
        ),
        Prerequisite(
            "P-EXEC-OPERATION",
            "Every contributing source permits the operation at the execution location",
            "computed",
            "missing_execution_policy",
            "Obtain an execution policy that addresses this operation and location",
        ),
        Prerequisite(
            "P-OUTPUT-ARTIFACT",
            "Every contributing source permits the artifact, output unit and destination",
            "computed",
            "missing_output_policy",
            "Request a permitted artifact (for example an aggregate) as a separate task",
        ),
        Prerequisite(
            "P-AGGREGATION-RULES",
            "Disclosure rules with counted units are supplied for the aggregate",
            "computed",
            "aggregation_rules_unknown",
            "Obtain aggregation rules from the policy owner",
        ),
        Prerequisite(
            "P-AGGREGATION-THRESHOLD",
            "Releasable cells meet every supplied threshold",
            "fact",
            "aggregate_counts_unavailable",
            "Run the aggregate check inside the boundary, coarsen dimensions, or widen the population",
        ),
        Prerequisite(
            "P-RIGHTS-USE",
            "Rights permit this operation and purpose",
            "fact",
            "unverified_permission",
            "Obtain rights evidence from the rights owner",
        ),
        Prerequisite(
            "P-SENSITIVE-EXCLUSION",
            "Objective, labels and features avoid excluded sensitive categories",
            "fact",
            "sensitive_screening_missing",
            "Complete sensitive-category screening",
        ),
        Prerequisite(
            "P-SEED-PRESENT", "The seed reference resolves", "computed", "missing_seed", "Supply the seed snapshot"
        ),
        Prerequisite(
            "P-UNIVERSE-DEFINED",
            "The eligible universe is defined",
            "computed",
            "missing_universe",
            "Define the eligible universe",
        ),
        Prerequisite(
            "P-CONTENT-BRIEF",
            "The content brief or reference resolves",
            "computed",
            "missing_content_brief",
            "Supply the content brief",
        ),
        Prerequisite(
            "P-FEATURE-COVERAGE",
            "Feature coverage is adequate for the eligible population",
            "fact",
            "insufficient_feature_coverage",
            "Profile feature coverage for the eligible population",
        ),
        Prerequisite(
            "P-FEATURE-TIMING",
            "Features and relationships are available by the prediction cutoff",
            "fact",
            "missing_availability_evidence",
            "Run the point-in-time check or rebuild the feature plan",
        ),
        Prerequisite(
            "P-LABELS-QUALIFIED",
            "Mature outcome labels exist for a named event, cutoff and horizon",
            "fact",
            "unsupported_outcome_probability",
            "Supply qualified labels: named event, cutoff, horizon, mature windows, coverage",
        ),
        Prerequisite(
            "P-MODEL-VALIDATED",
            "An applicable validated model and its evidence exist",
            "fact",
            "missing_validation_evidence",
            "Complete validation and calibration, or remediate the failed promotion criteria",
        ),
        Prerequisite(
            "P-POPULATION-COMPATIBLE",
            "The scored population is compatible with the validated model",
            "fact",
            "missing_population_compatibility",
            "Compare scored and validation populations",
        ),
        Prerequisite(
            "P-REPRESENTATION-COMPATIBLE",
            "Vector representations are compatible or aligned with evidence",
            "fact",
            "missing_representation_evidence",
            "Run the representation compatibility check",
        ),
        Prerequisite(
            "P-MODEL-REGISTERED",
            "The cited model is registered, current, and its family, score type and units match the task",
            "computed",
            "missing_model_registration",
            "Register the model, or cite a current registration whose contract matches the task",
        ),
        Prerequisite(
            "P-MODEL-EXECUTION",
            "The model's registered execution mode and locations permit this operation here",
            "computed",
            "missing_model_registration",
            "Run an in-boundary model at a registered location, or request remote_inference for an endpoint model",
        ),
        Prerequisite(
            "P-MODEL-FEATURES-AVAILABLE",
            "The model's required features exist at its declared units for the scored population",
            "fact",
            "insufficient_feature_coverage",
            "Confirm the model's required features are available at its declared units",
        ),
        Prerequisite(
            "P-REMOTE-PAYLOAD",
            "Every contributing source permits sending the inference payload to the endpoint",
            "computed",
            "missing_output_policy",
            "Obtain an output policy that permits this payload to this endpoint, or use an in-boundary model",
        ),
        Prerequisite(
            "P-REMOTE-RECIPIENT-TERMS",
            "The rights owner accepts the endpoint's recipients, retention and reuse terms",
            "fact",
            "recipient_terms_unverified",
            "Obtain the rights owner's confirmation of the endpoint's recipient terms",
        ),
        Prerequisite(
            "P-DESTINATION-COMPATIBLE",
            "Destination capability is verified for this artifact",
            "fact",
            "capability_not_verified",
            "Verify destination capability and conformance",
        ),
    ]
}

QUARANTINE_OPS = {"intake_receive", "profile", "map_semantics", "register_type", "inspect_raw"}
EGRESS_OPS = {"export_rows", "export_aggregate", "activate"}
MODEL_BUILD_OPS = {"train", "validate", "calibrate"}
SCORING_OPS = {"infer", "score", "remote_inference", "build_cohort"}


def required_prerequisites(task: dict[str, Any]) -> list[str]:
    op, family = task["operation"], task["task_family"]
    required = [
        "P-CONTRACT-VALID",
        "P-TENANT-SCOPE",
        "P-SNAPSHOT-IMMUTABLE",
        "P-EXEC-OPERATION",
        "P-RIGHTS-USE",
        "P-SENSITIVE-EXCLUSION",
    ]
    if op not in QUARANTINE_OPS:
        required += ["P-PROFILE-CONFIRMED", "P-UNITS-DECLARED", "P-GRAIN-COMPATIBLE"]
    if family in ("seed_affinity", "behavioral_affinity") and op in MODEL_BUILD_OPS | SCORING_OPS:
        required += ["P-SEED-PRESENT", "P-UNIVERSE-DEFINED", "P-FEATURE-COVERAGE", "P-FEATURE-TIMING"]
    if family == "semantic_similarity" and op in SCORING_OPS | {"embed_content"}:
        required += ["P-CONTENT-BRIEF", "P-REPRESENTATION-COMPATIBLE"]
    if family == "outcome_propensity":
        if op in MODEL_BUILD_OPS:
            required += ["P-UNIVERSE-DEFINED", "P-LABELS-QUALIFIED", "P-FEATURE-TIMING"]
        elif op in SCORING_OPS:
            required += ["P-MODEL-VALIDATED", "P-POPULATION-COMPATIBLE", "P-FEATURE-TIMING"]
        elif op in EGRESS_OPS | {"prepare_release"}:
            required += ["P-MODEL-VALIDATED"]
    if family == "cohort" and op in SCORING_OPS:
        required += ["P-FEATURE-COVERAGE"]
    if op in {"aggregate", "export_aggregate", "measure"}:
        required += ["P-AGGREGATION-RULES"]
    if op == "export_aggregate":
        required += ["P-AGGREGATION-THRESHOLD"]
    if op == "remote_inference" or (task.get("model_ref") and op in SCORING_OPS):
        required += ["P-MODEL-REGISTERED", "P-MODEL-EXECUTION", "P-MODEL-FEATURES-AVAILABLE"]
    if op == "remote_inference":
        required += ["P-REMOTE-PAYLOAD", "P-REMOTE-RECIPIENT-TERMS"]
    if op in EGRESS_OPS:
        required += ["P-OUTPUT-ARTIFACT", "P-DESTINATION-COMPATIBLE"]
    return list(dict.fromkeys(required))
