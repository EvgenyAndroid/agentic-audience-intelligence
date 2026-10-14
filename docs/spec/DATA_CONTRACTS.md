# Data Contracts

Session 2 | Revision 1 | 14 October 2026

This document defines the machine-readable contracts for the provider-agnostic audience intelligence platform. The normative artifacts are the JSON Schema files in `schemas/v1/`; this document explains their rules and the decisions behind them. Validating a document against these schemas establishes its shape and declared semantics. It does not establish data quality, rights, predictive value, or integration support.

## 1 Dialect, validation and conventions

All schemas use JSON Schema draft 2020-12. Each schema has an `$id` under `https://schemas.aip.invalid/v1/`. The `.invalid` top-level domain is reserved and never resolves, so validators must load schemas locally. Shared definitions live in `common.schema.json` and are referenced with `$ref`, never copied.

The reference validator is the Python `jsonschema` package (version 4.21 or later) with the `referencing` registry, using `Draft202012Validator` and a `FormatChecker`. Format keywords are annotations unless optional format packages are installed. For that reason, every timestamp is also enforced by a pattern: RFC 3339 in UTC with a `Z` suffix. Any validator that supports draft 2020-12 `unevaluatedProperties`, `if`/`then`/`else` and `contains` can validate these schemas.

Every document carries `kind` (a constant naming its contract) and `schema_version` (constant `1.0.0`). Root objects use `unevaluatedProperties: false`; nested objects use `additionalProperties: false`. Unknown fields are therefore rejected everywhere except the declared `extensions` slot. That slot is an array of `{namespace, name, version, value}` entries with a dotted namespace such as `com.example`. The canonical primitives (`entity`, `observation`, `event`, `relationship`, `outcome_label`) and the benchmark contracts have no extension slot.

Every listed field is required. Absence of a value is written as an explicit `null`, so "unknown" can never be confused with "omitted". The only optional fields are the usage measurements in `usage_cost_record`, where an unmeasured quantity is omitted. Standard JSON cannot encode NaN or Infinity. The platform's strict loader (`aip.canonical.loads`) also rejects the non-standard literals that Python's `json` module accepts, and it rejects duplicate keys. Money is a decimal string with an ISO 4217 currency code. Checksums use the form `sha256:<64 hex>`. The platform's canonical hash input is sorted-key, compact, UTF-8 JSON. It is deterministic for these documents but is not RFC 8785 number canonicalization; cross-system signing would need JCS.

Some rules cannot be expressed in JSON Schema. A semantic layer (`aip.contracts.semantic`) runs after schema validation and checks:

- `available_at` is at or after the event or observation time.
- `horizon_end` follows `prediction_cutoff`.
- Validity windows are ordered.
- A decision's `valid_until` follows `decided_at`.
- Each operation appears only once per execution policy, and each artifact type once per output policy.

## 2 Contract catalog

| Kind | Purpose | PRD requirements |
| --- | --- | --- |
| `agent_proposal` | Advisory output of a bounded agent role. It is recorded and evaluated but never sets a task verdict. | FR38, FR32, NFR07 |
| `alignment_test_set` | Golden Test Set pairs with expected similarity bands, reusing the existing GTS pair fields. | FR24 |
| `authorization` | A human reviewer's decision bound to an exact prepared checksum, destination, purpose and policy versions. | FR16, FR38 |
| `cohort_membership` | Membership in a versioned cohort. No numeric score is required. | FR14, FR11, FR18 |
| `content_item` | A program, ad creative, page, app screen or other content. Content type is data, not a code branch. | FR08, FR24 |
| `dataset_manifest` | Binds one source profile version to one immutable input snapshot. | FR01, FR20, FR40, FR22 |
| `entity` | A tokenized unit. Raw identifiers stay in the tenant vault; only a vault reference appears here. | FR02, FR09 |
| `event` | A time-stamped action or exposure by an entity, optionally referencing a content item. | FR07, FR08 |
| `evidence_bundle` | Facts available to the router for one task, each with its establishing authority. Agents cannot establish facts. | FR38, FR25 |
| `evidence_card` | Buyer-readable evidence for one output version. Claim type and qualifier stay visible; later measurements are appended as separate claims. | FR21, FR13, FR15, FR27, FR34 |
| `execution_policy` | Where computation may run and which operations are permitted there. Operations not listed are unknown, not permitted. | FR27, FR05, FR40, NFR06 |
| `export_receipt` | Delivery record. Acceptance or matching requires destination confirmation; unknown state requires reconciliation before retry. | FR17, FR15 |
| `feature_plan` | Point-in-time feature definitions. Event time and availability time must both precede the cutoff. | FR07, FR12, FR06 |
| `job` | Execution record. Execution state, failure code and statistical outcome are separate fields. | NFR02, NFR03, FR21, FR20 |
| `measurement_feedback` | Downstream evidence bound to one exact release. Observational designs cannot carry causal claims. | FR34, FR35, FR36 |
| `model_registration` | Identity and declared requirements of an existing or bring-your-own model: features, units, score type, artifact and preprocessing checksums, bound validation evidence, validity, rights and execution mode. Registration is not validation. | FR44, FR45, FR13, FR14, FR09 |
| `monitoring_report` | Post-release drift, coverage or base-rate check against a supplied threshold. It can propose reassessment, never a release. | FR42 |
| `objective` | The buyer's requested value: task family, intended use, claim sought and task-specific inputs. | FR03, FR25, FR10 |
| `observation` | An attribute value about an entity. Missing, unobserved, zero and false remain distinct states. | FR08, FR07, FR23 |
| `outcome_label` | An outcome observation for a named event, cutoff and horizon. Negatives require a mature, complete window. | FR10, FR13, FR36 |
| `output_policy` | Which artifacts, grains and destinations may leave an execution boundary, with supplied disclosure controls. | FR28, FR29, FR05, NFR06 |
| `recommendation` | Deterministic ordering of the requested task and separately identified alternatives against one objective, from current decisions. Sections: requested task, recommended, unlock, blocked. | FR46, FR25, FR16 |
| `reason_code_registry` | Single registry of reason codes, each bound to one dimension. Legacy aliases resolve to canonical codes. | FR41 |
| `relationship` | A permitted, evidenced, time-bounded link between typed units. Permitted uses are explicit. | FR06, FR02, FR07 |
| `relationship_snapshot` | Immutable set of links produced under one unit mapping, with checksum, as-of and availability times, validity coverage, observed cardinality, unmatched and ambiguous counts, corrections and revocation. | FR43, FR06, FR07, FR15, FR22 |
| `release_manifest` | Immutable prepared release. Any membership or policy change requires a new prepared version. | FR15, FR16, FR18, FR22 |
| `representation_descriptor` | Vector space declaration reusing Vector Alignment Contract field names. Identifiers are never represented. | FR24, FR09 |
| `routing_case` | Neutral case visible to an evaluated agent. Expected decisions live only in the separate oracle. | FR32 |
| `routing_oracle` | Hidden expected decision for one case. Authored independently of the evaluated model. | FR32 |
| `run` | Groups tasks under one objective with immutable inputs and recorded experiment settings. | FR20, FR12 |
| `score` | Typed record-level score. Cosine, affinity, rank and probability are distinct; abstention is null with reasons. | FR14, FR10, FR13, FR11, FR18 |
| `source_profile` | Semantic contract that maps one source family onto canonical primitives. Transport adapters are referenced separately. | FR26, FR31, FR08, FR27, FR28, FR40 |
| `task` | One exact requested operation. Each task receives its own decision; parent runs may hold several tasks. | FR03, FR25, FR27, FR28, FR40 |
| `task_decision` | Authoritative per-task verdict assembled by the router from established prerequisites. Precedence: violated > missing > satisfied. | FR25, FR38, FR39, FR10, FR41, NFR06 |
| `type_registry_entry` | Declares what a unit or identifier type represents. Every source family uses the same registry rules. | FR31, FR02, FR09 |
| `unit_mapping` | Versioned definition of how one registered unit maps to another: direction, cardinality, method, confidence definition, permitted uses, aggregation rule, approval and effective period. It does not establish links. | FR43, FR03, FR06 |
| `usage_cost_record` | Attributed usage and cost for a job, task, run or release. Feeds cost per comparable run, per reviewed release and contribution. | FR37, NFR03, NFR05 |

## 3 Separate dimensions

No field is named `status`. Each dimension has its own field and vocabulary, and none substitutes for another.

| Dimension | Field | Values | Where |
| --- | --- | --- | --- |
| Task verdict | `verdict` | ELIGIBLE, PROVISIONAL, BLOCKED | `task_decision`, `agent_proposal.proposed_verdict`, `routing_oracle` |
| Prerequisite outcome | `outcome` | satisfied, missing, violated | `task_decision.prerequisites` |
| Claim qualifier | `claim.qualifier` | exploratory, validated | `evidence_card` |
| Execution state | `execution_state` | queued, running, paused, succeeded, failed, cancelled, reconciling | `job` |
| Statistical outcome | `statistical_outcome` | signal_found, no_useful_signal, inconclusive, not_applicable | `job` |
| Record inclusion | `inclusion_disposition` | included, excluded, abstained | `score`, `cohort_membership` |
| Audience lifecycle | `lifecycle_state` | draft, prepared, approved, released, expired, revoked | `release_manifest` |
| Authorization | `decision` | approved, rejected | `authorization` |
| Delivery | `delivery_state` | submitted, accepted, matched, live, failed, unknown | `export_receipt` |
| Registration | `registration_state`, `profile_state`, `dataset_state`, `entity_state` | per contract | registry and source contracts |
| Verification | report labels | passed, failed, not-run | `reports/` only, never in contracts |

A dataset's fitness is the set of task decisions about it. No global fitness field exists. `unsupported_outcome_probability` is a reason code, not a status.

## 4 Units and the type registry

A unit is `{type_id, type_version, namespace}`. Its grain and meaning come from the type registry entry, never from the source's family name or file name. A task declares five unit roles separately: observation units for each input, modeling unit, output unit, activation unit, and measurement unit. Analytical tasks have null activation and measurement units.

A source profile declares the units its key fields represent. Each declaration carries a `contract_evidence_ref` pointing at the clause of the provider contract that establishes the meaning. The reference ACR profile declares a household key because its fixture contract says so. Another ACR provider could register a screen, device or other key under the same rules. The router blocks a task whose claimed observation unit differs from the unit the source contract declares (`grain_incompatible`).

Seeded registry entries:

| Type | Category | Grain | Temporal validity | Semantic feature |
| --- | --- | --- | --- | --- |
| `browser_cookie` | identifier | browser | rotating | never |
| `content_item_key` | content | content_item | stable | never |
| `ip_observation` | network_observation | network_observation | time_bound | never |
| `mobile_ad_id` | identifier | device | rotating | never |
| `postal_code` | area | area | stable | never |
| `provider_household_key` | unit | household | stable | never |
| `tv_screen_key` | identifier | screen | stable | never |

Entries in the `identifier` and `network_observation` categories must set `semantic_feature_allowed: false`; the schema enforces this. Equal strings in different namespaces never join implicitly. Registering a type never establishes identity equivalence. Unconfirmed types keep tasks PROVISIONAL with `missing_unit_semantics`.

## 5 Source profiles and transport adapters

A source profile is the semantic contract for one source version. It contains:

- collection method and detail
- observation units with contract evidence
- signals mapped to canonical primitives (observation, event, content item, relationship, label), each with an evidence kind
- time semantics: event-time meaning, availability rule, source time zone, delivery lag and backfill policy
- observable coverage and known gaps
- missingness semantics
- content resolution
- quality checks
- rights, intake, execution and output policy references
- known limits

A transport adapter (file batch, warehouse snapshot, clean-room output) is a separate versioned reference. Changing transport does not change meaning.

| Reference profile | Maps | Documents as missing or limited |
| --- | --- | --- |
| `prof_acr_viewing_ref` | Viewing events, duration observations, matched content items; key declared as household by contract | Exposure is not attention or a person; unmatched content is unknown, not absent; coverage limited to opted-in supported TVs |
| `prof_web_events_ref` | Page-view events, page content items, conversion labels at browser grain | Tagged properties only; consent coverage varies; residual bot traffic unknown |
| `prof_url_content_ref` | Page content items with text references and provider topic labels | No reader linkage without an approved relationship; crawl staleness; topic labels are provider-inferred |

These are conformance fixtures, not mandatory integrations. A new source that uses supported transports, primitives, transforms and policy enforcement is onboarded by registering a profile (FR26). New modalities, execution integrations or transforms need versioned extensions and their own tests. A profile in `draft` or `quarantined` state supports only intake, profiling, semantic mapping and type registration tasks (FR40).

## 6 Execution and output policies

Execution policies list locations and operation permissions. Output policies list artifact rules, aggregation rules, query controls, cross-client reuse and retention. Both carry issuer, authority, effective period and enforcement method. Restrictions propagate through lineage: each input's profile contributes its policies, and run-bound policies on the task are an additional contributing source.

Composition rules (`aip.policy.compose`):

1. Every contributing source must permit the operation at the selected location. A prohibition from any source wins; a permissive source cannot override a restrictive one.
2. Silence is missing evidence, not permission. An operation a policy does not list yields `missing_execution_policy`.
3. If one source's own active policies both permit and prohibit the same operation, the task is BLOCKED (`contradictory_policies`).
4. Policies outside their effective period yield `policy_not_current`.
5. Internal computation and egress are separate decisions. `score` can be permitted at a clean room while `export_rows` and the `score_file` artifact are prohibited.
6. Prohibited row-level artifacts (`score_file`, `cohort_membership`, `feature_snapshot`) yield `forbidden_row_level_egress`. Output-unit and destination restrictions yield `output_grain_not_permitted` and `destination_not_permitted`.
7. Aggregation rules compose most-restrictively per counted unit: the highest threshold, `block_release` over `suppress_cell`, and the intersection of approved dimensions. Thresholds are supplied by the policy owner; the platform has no default cohort size.
8. A release whose cells cannot meet the composed rules is BLOCKED (`aggregation_threshold_not_met`). Unknown counts are PROVISIONAL (`aggregate_counts_unavailable`).

9. Task-level (run-bound) policies only tighten. A task-level prohibition or restriction applies; task-level silence or permission adds no requirement and grants nothing, so it cannot stand in for a contributing source that is silent. Unresolved policy refs from any source are missing evidence (`missing_document`) and never dropped.

A policy version change invalidates every decision that bound it (FR39, NFR06). Moving data to another location to bypass a rule is never a remedy; an alternative output requires a separate task.

## 7 Tasks, evidence bundles and decisions

A `task` names one exact operation with its task family, input snapshots, five unit roles, requested artifact, execution location, destination, run-bound policies, model reference (required for `infer`), budgets and creator. An `evidence_bundle` carries facts for that exact task version. Each fact is `true` (satisfied), `false` (violated, with a reason code) or `null` (missing), and names its establishing authority. The fact schema excludes `agent` as an authority.

The router selects prerequisites from the operation and task family (`aip.routing.prerequisites`):

| Prerequisite | Meaning | Established by | Reason when missing |
| --- | --- | --- | --- |
| `P-CONTRACT-VALID` | Task document passes schema and semantic validation | router check | `contract_invalid` |
| `P-TENANT-SCOPE` | Inputs and policies belong to the task's tenant | router check | `missing_document` |
| `P-SNAPSHOT-IMMUTABLE` | Every input resolves to an immutable, non-withdrawn snapshot | router check | `missing_document` |
| `P-PROFILE-CONFIRMED` | Every contributing source profile is steward-confirmed | router check | `unregistered_source_profile` |
| `P-UNITS-DECLARED` | Every task unit is registered, confirmed and declared by the source contract | router check | `missing_unit_semantics` |
| `P-GRAIN-COMPATIBLE` | Observation, modeling and output units match or have approved mappings | router check | `missing_unit_mapping` |
| `P-EXEC-OPERATION` | Every contributing source permits the operation at the execution location | router check | `missing_execution_policy` |
| `P-OUTPUT-ARTIFACT` | Every contributing source permits the artifact, output unit and destination | router check | `missing_output_policy` |
| `P-AGGREGATION-RULES` | Disclosure rules with counted units are supplied for the aggregate | router check | `aggregation_rules_unknown` |
| `P-AGGREGATION-THRESHOLD` | Releasable cells meet every supplied threshold | fact from policy service, steward, reviewer or deterministic job | `aggregate_counts_unavailable` |
| `P-RIGHTS-USE` | Rights permit this operation and purpose | fact from policy service, steward, reviewer or deterministic job | `unverified_permission` |
| `P-SENSITIVE-EXCLUSION` | Objective, labels and features avoid excluded sensitive categories | fact from policy service, steward, reviewer or deterministic job | `sensitive_screening_missing` |
| `P-SEED-PRESENT` | The seed reference resolves | router check | `missing_seed` |
| `P-UNIVERSE-DEFINED` | The eligible universe is defined | router check | `missing_universe` |
| `P-CONTENT-BRIEF` | The content brief or reference resolves | router check | `missing_content_brief` |
| `P-FEATURE-COVERAGE` | Feature coverage is adequate for the eligible population | fact from policy service, steward, reviewer or deterministic job | `insufficient_feature_coverage` |
| `P-FEATURE-TIMING` | Features and relationships are available by the prediction cutoff | fact from policy service, steward, reviewer or deterministic job | `missing_availability_evidence` |
| `P-LABELS-QUALIFIED` | Mature outcome labels exist for a named event, cutoff and horizon | fact from policy service, steward, reviewer or deterministic job | `unsupported_outcome_probability` |
| `P-MODEL-VALIDATED` | An applicable validated model and its evidence exist | fact from policy service, steward, reviewer or deterministic job | `missing_validation_evidence` |
| `P-POPULATION-COMPATIBLE` | The scored population is compatible with the validated model | fact from policy service, steward, reviewer or deterministic job | `missing_population_compatibility` |
| `P-REPRESENTATION-COMPATIBLE` | Vector representations are compatible or aligned with evidence | fact from policy service, steward, reviewer or deterministic job | `missing_representation_evidence` |
| `P-MODEL-REGISTERED` | The cited model is registered, current, and its family, score type, units and (for probabilities) target match the task and objective | router check | `missing_model_registration` |
| `P-MODEL-EXECUTION` | The model's registered execution mode and locations permit this operation here | router check | `missing_model_registration` |
| `P-MODEL-FEATURES-AVAILABLE` | The model's required features exist at its declared units for the scored population | fact from policy service, steward, reviewer or deterministic job | `insufficient_feature_coverage` |
| `P-REMOTE-PAYLOAD` | Every contributing source permits sending the inference payload to the endpoint | router check | `missing_output_policy` |
| `P-REMOTE-RECIPIENT-TERMS` | The rights owner accepts the endpoint's recipients, retention and reuse terms | fact from policy service, steward, reviewer or deterministic job | `recipient_terms_unverified` |
| `P-DESTINATION-COMPATIBLE` | Destination capability is verified for this artifact | fact from policy service, steward, reviewer or deterministic job | `capability_not_verified` |

Quarantine-safe operations (intake, profiling, semantic mapping, type registration) skip the profile, unit and grain prerequisites. A new propensity model (`train`, `validate`, `calibrate`) needs qualified labels. Inference with an existing model needs model validity, population compatibility and feature timing, but no future labels on candidates. Publishing probabilities additionally requires model validation, because eligibility to train does not establish eligibility to publish.

Unit mappings (FR43). Each unit that differs from the modeling unit, and an output unit that differs from it, needs a cited `unit_mapping` from that unit to the other, plus a cited `relationship_snapshot` produced under that mapping (`task.units.mapping_refs` and the optional `task.units.relationship_snapshot_refs`). The router checks, in order:

| Condition | Outcome | Reason |
| --- | --- | --- |
| The type registry declares no relationship between the types | violated | `grain_incompatible` |
| A cited mapping or snapshot does not resolve | missing | `missing_document` |
| No cited mapping covers the pair | missing | `missing_unit_mapping` |
| The mapping is revoked | violated | `mapping_revoked` |
| The mapping does not permit the use (observation to modeling needs `feature_join`, or `measurement_mapping` for `measure`; modeling to output needs `aggregation` when many-to-one, otherwise `activation_mapping`) | violated | `mapping_use_not_permitted` |
| The mapping is a draft or outside its effective period | missing | `missing_unit_mapping` |
| A cited snapshot is revoked | violated | `relationship_snapshot_revoked` |
| No cited snapshot was available at decision time | missing | `missing_relationship_evidence` |
| Observed cardinality contradicts the declared cardinality | violated | `mapping_cardinality_mismatch` |

Availability at the prediction cutoff, including late-discovered relationships, remains a `P-FEATURE-TIMING` fact.

Registered models (FR44, FR45). A scoring task that cites `model_ref`, and every `remote_inference` task, adds the model prerequisites. A revoked registration is BLOCKED; a suspended or expired one is PROVISIONAL. Registration never satisfies `P-MODEL-VALIDATED`, which probability tasks still require. An endpoint model must run as `remote_inference`, and an in-boundary model cannot, so the payload transfer is always checked. `P-REMOTE-PAYLOAD` applies output policies to the endpoint's payload artifact type, unit and destination with the same composition as egress: a prohibited row payload is BLOCKED (`forbidden_row_level_egress`), a missing permission is PROVISIONAL, and an expressly permitted aggregate payload passes even where row artifacts are prohibited.

Precedence is fixed: any violated prerequisite makes the task BLOCKED; otherwise any missing prerequisite makes it PROVISIONAL; otherwise it is ELIGIBLE. The `task_decision` schema enforces this structurally, so an ELIGIBLE decision with a non-satisfied prerequisite is invalid.

Each decision records:

- its prerequisites with their establishing authority
- reasons, with violated reasons listed first
- next actions
- `valid_until`, the earliest of the configured maximum validity and every bound policy's effective end
- policy and contract versions
- the decision it supersedes
- references to advisory agent proposals

The router never reads proposal content.

Required examples (generated by the router and stored as golden outputs; `tests/test_routing.py` regenerates them):

| Task | Verdict | Reasons | File |
| --- | --- | --- | --- |
| Row-level score export from an aggregate-only clean room | BLOCKED | forbidden_operation, forbidden_row_level_egress, capability_not_verified | `examples/valid/task_decision/decision_aggregate_only_rows_blocked.json` |
| Aggregate export from the same source with a qualifying threshold check | ELIGIBLE | none | `examples/valid/task_decision/decision_aggregate_only_aggregate_eligible.json` |
| Scoring at a location no policy addresses | PROVISIONAL | missing_execution_policy | `examples/valid/task_decision/decision_missing_policy_provisional.json` |
| New propensity model without qualified labels | PROVISIONAL | unsupported_outcome_probability | `examples/valid/task_decision/decision_propensity_no_labels_provisional.json` |
| Profiling a quarantined source | ELIGIBLE | none | `examples/valid/task_decision/decision_quarantine_profile_eligible.json` |
| Scoring the same quarantined source | PROVISIONAL | unregistered_source_profile | `examples/valid/task_decision/decision_quarantine_score_provisional.json` |

These are contract fixtures and future test cases. They are not evidence of integration support.

## 8 Records and outputs

**Observations** keep present, missing, unobserved and not-applicable as distinct states; a value appears only when present.

**Events** carry both event time and availability time.

**Relationships** list their permitted uses (`feature_join`, `activation_mapping`, `measurement_mapping`, `alias_exclusion`). An activation-only mapping cannot become a training feature, and a probabilistic relationship must state its confidence.

**Outcome labels** distinguish positive, negative, censored and unobserved outcomes. A negative requires a mature window.

**Scores** are typed by `score_type`:

- Only `outcome_probability` may carry a target and the probability scale.
- Semantic similarity uses the cosine scale and a representation reference.
- Affinity scores reference their seed.
- An abstained score is null and carries at least one inclusion reason.
- Scale ranges are enforced per scale.

**Cohort membership** carries no score. Excluded and abstained members need reasons.

**Evidence cards** bind:

- the decision, claim type and qualifier
- source profiles with collection method, coverage and limits
- seed, target, brief and universe
- windows, representations, baselines and metrics, with denominators and uncertainty
- population counts by stage and grain
- at least one limitation, permitted uses, and the execution boundary and output policies

Downstream measurements are appended as separate `measured_claims`; they never change the original claim type.

**Release manifests** are immutable prepared versions with artifact checksums and a content checksum.

**Authorizations** bind a human reviewer to that checksum, destination, purpose, policy versions and validity window.

**Export receipts** require destination confirmation before reporting accepted, matched or live states or counts. An unknown state requires reconciliation before any retry.

**Usage and cost records** (FR37) attribute metered, allocated or contracted costs to a job, task, run, release or tenant period. Allocated costs must name their allocation method. A run's outcome and comparable class make cost per comparable completed run computable, including abstentions and no-signal results. Review and analyst minutes support the BRD's analyst-effort measure.

**Recommendations (FR46).** `aip.recommendation.recommend` takes one objective, the requested task and separately identified alternatives, each with a current decision whose `task_checksum` matches the task. It refuses lapsed, changed or foreign inputs. The requested task keeps its own card with its verdict. ELIGIBLE tasks are ordered in three groups (the requested task, then tasks of the requested family, then alternatives that answer a different question), and within a group by known cost only. Unknown cost is never treated as zero: options without comparable cost share a position. There is no claim-strength ladder between families. `ranking_status` is `ranked`, `partial_order`, `insufficient_evidence_to_rank` (every eligible option shares the first position) or `no_eligible_options`. PROVISIONAL tasks appear under `unlock_options` with their reason codes and next actions; BLOCKED tasks under `blocked_options` with remedies. The recommendation lapses with its earliest decision. `admissibility_issues` checks any proposed recommendation, including a future agent-proposed order, against current decisions; passing it shows admissibility, not optimality.

## 9 Reason-code registry

`registry/reason_codes.json` is the single registry (FR41). Each code belongs to exactly one dimension, and task-decision codes declare whether they mark a violated or missing prerequisite. The router rejects any code used outside its dimension or with the wrong effect. Legacy names from the earlier PRD resolve as aliases.

- **Task decision, violated (drives BLOCKED):** `forbidden_operation`, `forbidden_row_level_egress`, `forbidden_artifact_egress`, `output_grain_not_permitted`, `destination_not_permitted`, `aggregation_threshold_not_met`, `dimension_not_approved`, `contradictory_policies`, `temporal_leakage` (alias leakage_detected), `invalid_join`, `grain_incompatible`, `prohibited_use` (alias unauthorized_use), `sensitive_category_excluded`, `source_withdrawn` (alias source_revoked), `promotion_criteria_failed`, `representation_incompatible` (alias incompatible_embedding), `representation_nonsemantic`, `representation_expired`, `tenant_scope_mismatch`, `snapshot_not_immutable`, `contract_invalid` (alias invalid_schema_task), `destination_incompatible`, `cross_client_reuse_not_permitted`
- **Task decision, missing (drives PROVISIONAL):** `unsupported_outcome_probability`, `missing_execution_policy`, `missing_output_policy`, `policy_not_current` (alias policy_expired), `unverified_permission`, `missing_availability_evidence`, `missing_unit_semantics` (alias unknown_grain), `missing_unit_mapping`, `missing_relationship_evidence`, `insufficient_information`, `insufficient_feature_coverage`, `missing_validation_evidence`, `missing_population_compatibility`, `unregistered_source_profile`, `missing_seed`, `missing_universe`, `missing_content_brief`, `missing_representation_evidence`, `aggregation_rules_unknown`, `aggregate_counts_unavailable`, `capability_not_verified`, `sensitive_screening_missing`, `missing_document`
- **Execution failure (job dimension only):** `invalid_schema`, `budget_exceeded`, `cancelled`, `timeout`, `dependency_unavailable`, `checkpoint_missing`, `internal_error`
- **Record inclusion (score and membership dimension):** `entity_feature_coverage_insufficient`, `zero_vector`, `embedding_version_mismatch`, `entity_suppressed`, `entity_is_seed_or_alias`, `entity_outside_universe`, `entity_expired`
- **Delivery:** `unknown_delivery_status`, `destination_rejected`

## 10 AdCP boundary mapping

The exchange adapter (`aip.exchange.adcp`) is pinned to AdCP schema version 3.1.20 from `adcontextprotocol/adcp` at commit `d033baef9adab46204db6c24a86f315580b40faf` (accessed 14 October 2026). The bundled `get-signals-response` and `activate-signal-request` schemas are vendored unmodified under `third_party/adcp/` with the Apache-2.0 license. Their SHA-256 hashes are recorded in `adcp.lock.json` and checked before every validation. AdCP schemas use draft-07 and are validated with a draft-07 validator.

| Canonical artifact | AdCP field | Classification |
| --- | --- | --- |
| Release id and version | `signal_agent_segment_id` (opaque handle) | Standard |
| Release id and agent URL | `signal_ref` with scope `signal_source` | Standard (the deprecated `signal_id` is not emitted) |
| Objective statement | `name` | Standard |
| Claim, qualifier and limitations | `description` | Standard (free text) |
| Membership versus score artifact | `value_type` (binary or numeric) with `range` for numeric | Standard |
| Commercial type | `signal_type` | Standard, supplied by configuration |
| Claim type | `methodology` (modeled or derived) and `audience_expansion` | Standard enrichment |
| Source profiles | `data_sources` | Standard enrichment, declared per profile in configuration; never inferred from a family name |
| Modeling method and seed source | `modeling` | Standard enrichment, emitted only when the seed source, jurisdictions and AI Act class are declared |
| Evidence card location | `methodology_url` | Standard enrichment, optional |
| Evidence card issue time | `last_updated` | Standard |
| Claim, output unit, populations, decision and checksum references | `ext.aip` | Namespaced extension |
| Deployments | `deployments` (empty until a destination receipt exists) | Standard |
| Approved activation | `activate_signal` request with `action`, handle, destinations and idempotency key | Standard |

Aggregate measurements, observed associations and experimental effects have no faithful AdCP audience-signal representation. The adapter refuses them (`UnsupportedMapping`); they remain referenced artifacts.

Building a request is not delivery. Destination acceptance is recorded only from a receipt with destination confirmation, and a mock or sandbox handle is never reported as accepted. Not verified in this session:

- live destinations
- `governance_context` flows
- pricing options
- account references
- asynchronous status surfaces

Every adapter output is validated against the pinned schema, wrapped in the minimal completed response envelope (`status`, `cache_scope`) that 3.1.x requires.

## 11 Representation compatibility and alignment tests

`representation_descriptor` reuses the Vector Alignment Contract field names from `adcp-signals-adaptor` at commit `cf5ef0edd3b5f11dc7cb80170824a838f4c9e7ae`: `model_id`, `model_family`, `space_id`, `dimensions`, `encoding`, `normalization`, `distance_metric` and `phase`. It adds:

- model revision and transformation version
- represented unit and role
- time validity and permitted uses
- provenance
- GTS version
- an alignment route

A `pseudo-v1` phase must declare `representation_semantics: nonsemantic`. Nonsemantic vectors never support semantic similarity, so the existing deterministic taxonomy bridge remains usable for exchange conformance only.

Direct comparison requires equality on model, family, revision, space, dimensions, encoding, normalization, metric and transformation version. Equal dimensions alone are rejected. A projector route needs both a projector reference and held-out alignment evidence; otherwise the result is incompatible, and the task falls back to structured criteria or abstains.

`alignment_test_set` reuses the GTS pair fields (`pair_id`, `concept_a`, `concept_b`, `rationale`, `expected_min` inclusive, `expected_max` exclusive). Exchange conformance, representation alignment and routing correctness remain separate test suites.

## 12 Measurement feedback

Measurement feedback binds:

- the exact release and its checksum
- model and feature versions
- output and measurement units with approved mapping versions
- campaign context and design (type, assignment, primary estimand, estimator and assumptions)
- exposure, outcome definition and observation window
- availability, maturity and coverage
- results with denominators and uncertainty
- claim type
- whether future training use is permitted

Observational designs can carry only `observed_association`. An `experimental_effect` claim requires intention-to-treat as the primary estimand. Permitted future training use requires a reuse-rights reference. Feedback can enter a later eligible training snapshot. It never enters the original model's backtest or turns an affinity score into a probability.

## 13 Versioning and change control

Schema files are versioned by path (`schemas/v1`) and by the `schema_version` constant. Adding an optional extension namespace is non-breaking. Adding a required field, removing a value from an enum, or tightening a rule is breaking: it requires `schemas/v2`, a new `schema_version`, updated examples and invalid cases, and a migration note.

Router-generated golden decisions change only through review. `tests/test_routing.py` fails when router output drifts from the stored examples. Reason codes are never repurposed; a renamed code keeps its old name as an alias.

## 14 Parameters without platform defaults

The following values must be supplied by the tenant, policy owner or pilot plan. The code requires them as explicit arguments rather than inventing defaults:

- maximum decision validity (`RouterConfig.max_decision_ttl`, CLI `--ttl-hours`)
- aggregation thresholds, counted units and approved dimensions
- affinity minimum feature coverage, prototype count and random seed
- reach fractions and reliability bin counts
- model allowlists, budgets and reasoning-model identifiers
- AdCP `data_sources` per profile, commercial signal type, training jurisdictions and AI Act risk class
- monitoring thresholds

Fixture values in `examples/` and `registry/` (for example a 50-household threshold) illustrate contract shape only. They are not recommendations.

## 15 Requirement to schema mapping

Requirements that describe behavior rather than data shape (for example FR12 bounded experiments or NFR01 tenant isolation) are verified by code and tests, as listed in the PRD traceability table.

| Requirement | Schemas |
| --- | --- |
| FR01 | `common`, `dataset_manifest` |
| FR02 | `entity`, `relationship`, `type_registry_entry` |
| FR03 | `objective`, `task` |
| FR05 | `execution_policy`, `output_policy` |
| FR06 | `feature_plan`, `relationship`, `relationship_snapshot`, `unit_mapping` |
| FR07 | `event`, `feature_plan`, `observation`, `relationship` |
| FR08 | `content_item`, `event`, `observation`, `source_profile` |
| FR09 | `entity`, `representation_descriptor`, `type_registry_entry` |
| FR10 | `objective`, `outcome_label`, `score`, `task_decision` |
| FR11 | `cohort_membership`, `score` |
| FR12 | `feature_plan`, `run` |
| FR13 | `evidence_card`, `outcome_label`, `score` |
| FR14 | `cohort_membership`, `score` |
| FR15 | `evidence_card`, `export_receipt`, `release_manifest` |
| FR16 | `authorization`, `release_manifest` |
| FR17 | `export_receipt` |
| FR18 | `cohort_membership`, `release_manifest`, `score` |
| FR20 | `common`, `dataset_manifest`, `job`, `run` |
| FR21 | `evidence_card`, `job` |
| FR22 | `dataset_manifest`, `release_manifest` |
| FR23 | `observation` |
| FR24 | `alignment_test_set`, `content_item`, `representation_descriptor` |
| FR25 | `evidence_bundle`, `objective`, `task`, `task_decision` |
| FR26 | `source_profile` |
| FR27 | `evidence_card`, `execution_policy`, `source_profile`, `task` |
| FR28 | `output_policy`, `source_profile`, `task` |
| FR29 | `output_policy` |
| FR31 | `source_profile`, `type_registry_entry` |
| FR32 | `agent_proposal`, `routing_case`, `routing_oracle` |
| FR34 | `evidence_card`, `measurement_feedback` |
| FR35 | `measurement_feedback` |
| FR36 | `measurement_feedback`, `outcome_label` |
| FR37 | `usage_cost_record` |
| FR38 | `agent_proposal`, `authorization`, `evidence_bundle`, `task_decision` |
| FR39 | `task_decision` |
| FR40 | `dataset_manifest`, `execution_policy`, `source_profile`, `task` |
| FR41 | `reason_code_registry`, `task_decision` |
| FR42 | `monitoring_report` |
| FR43 | `relationship_snapshot`, `task`, `unit_mapping` |
| FR44 | `model_registration`, `task` |
| FR45 | `common`, `model_registration` |
| FR46 | `recommendation` |
| NFR02 | `job` |
| NFR03 | `job`, `usage_cost_record` |
| NFR05 | `usage_cost_record` |
| NFR06 | `execution_policy`, `output_policy`, `task_decision` |
| NFR07 | `agent_proposal` |
