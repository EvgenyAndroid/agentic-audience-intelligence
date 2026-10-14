# Product Requirements for the Agentic Audience Intelligence Platform

Session 1 | Revision 2 | 14 October 2026 (Session 2 corrections; see Section 13)

## 1 Product decision and scope

Build a provider-agnostic workbench that assesses permitted data, selects defensible tasks, runs bounded modeling workflows, and prepares reviewable outputs. Agents interpret and propose. Deterministic services enforce contracts, perform calculations, and control release.

ACR viewing, web events, and URL content are reference input profiles. They do not set the modeling grain, identifier meaning, customer, or output format. New sources use a versioned profile and adapter registry. Each requested task states what it seeks to do, where computation may run, and what may leave that environment.

The first real pilot uses one objective, one output grain, a fixed eligible universe, immutable input snapshots, batch execution, and one reviewable output. Select its task from actual input evidence and restrictions. A permitted aggregate report is a valid pilot output when a score file is prohibited. No universal identity graph, real-time bidding, automatic media spend, or full marketplace is required.

This specification defines product behavior. Model performance, routing accuracy, production integrations, delivery, and commercial value have not been tested. Session 2 creates detailed contracts and schemas; Session 3 creates and checks evaluation assets.

## 2 Users and workflow

The buyer or analyst defines the objective and intended use. The data steward confirms source meaning, type registration, and lineage. The policy owner supplies execution and output rules. The scientist defines statistical evaluation. The release reviewer authorizes an exact prepared artifact. The operator monitors jobs and delivery. Roles may overlap, but authorities remain explicit.

1. Register source manifests, type and profile versions, immutable snapshots, and policy references.
2. Assess permitted metadata and profile data only under an eligible intake task.
3. Define the requested operation, modeling and output units, execution context, and artifact.
4. Return a per-task verdict and its reasons. Propose separately identified alternatives where useful.
5. Confirm meaning mappings, joins, feature logic, and evaluation plans within that task's authority.
6. Run permitted deterministic tools. Keep calculated evidence separate from the agent's interpretation.
7. Prepare an output with a typed claim, lineage, limitations, and policy checks.
8. Assess and authorize the exact release operation, rechecking current constraints before commit.
9. Record delivery or analytic release receipts. Add downstream evidence only under a compatible measurement task.

An unresolved task does not block unrelated eligible diagnostics. A permitted alternative cannot silently replace the buyer's requested task or retain its stronger claim.

## 3 One task verdict vocabulary

A task contract identifies task_id, operation, objective, input snapshot references, modeling unit, output unit, requested artifact, execution location, destination where applicable, policy versions, and required evidence. Activation and measurement tasks also bind their respective units and approved mapping references. Parent runs can contain several tasks; each has its own decision.

The run records five separate unit definitions: each input's observation grain, modeling unit, output grain, activation unit if requested, and measurement unit if requested. A difference requires supplied, permitted, validated relationships and aggregation rules. An activation-only mapping cannot silently become a training feature or identity model. Analytical-only runs have no implied activation or measurement unit.

| Verdict | Definition | Permitted action |
| --- | --- | --- |
| ELIGIBLE | All prerequisites for the exact operation, execution context, and outputs are established | Execute that operation within its controls |
| PROVISIONAL | Required evidence, permission, or capability verification is missing | Obtain specified evidence; do not execute the unresolved task |
| BLOCKED | A documented restriction or demonstrated violation forbids the exact task | Repair the violation or propose a new permitted task and reassess |

Dataset fitness is the set of its per-task decisions. There is no separate Ready, Ready with limitations, or Exploratory only vocabulary. exploratory labels an output claim; it is not a verdict. Codes such as unsupported_outcome_probability explain a decision and cannot introduce another status.

Known prohibitions take precedence over missing evidence for the same exact task. Unknown permissions are not treated as permission. Job execution states, release authorization, delivery states, and test results are separate typed dimensions; they never substitute for a fitness verdict.

Each decision records reasons, evidence references, required next actions, decision time, a validity limit (FR39), and contract and policy versions. The router service issues decisions from deterministic checks and facts confirmed by a policy service, steward or reviewer; agent proposals are advisory records and never set a verdict (FR38). A change in inputs, objective, environment, evidence, or policy produces a new decision. Retain the previous decision for audit.

### Required routing examples

| Exact requested task | Verdict | Required reason or limitation |
| --- | --- | --- |
| Build or validate a new propensity model without qualified outcome labels | PROVISIONAL | unsupported_outcome_probability and specific label requirements; no training or probability release |
| Run valid seed affinity with usable features and permitted outputs | ELIGIBLE | Output can carry an exploratory claim; affinity is not probability |
| Score with an existing validated model using suitable pre-cutoff features | ELIGIBLE when all task prerequisites pass | Future outcome labels on candidates are not required for inference |
| Export row-level scores from a context that explicitly forbids them | BLOCKED | forbidden_row_level_egress |
| Release qualifying aggregates under verified permissions and budgets | ELIGIBLE | Scope and evidence remain aggregate-level |
| Release aggregates whose required threshold is not met | BLOCKED | aggregation_threshold_not_met |
| Run with unverified execution or output permissions | PROVISIONAL | Missing policy evidence; no execution under that task |
| Train on features demonstrably delivered after the prediction cutoff | BLOCKED | temporal_leakage; rebuild the affected feature plan |

Eligibility for training does not establish eligibility for probability publication. A model awaiting quality tests makes the publication task provisional; a demonstrated failed promotion criterion blocks that candidate's promotion. This distinction also applies to alignment and destination conformance.

## 4 Supported tasks and claim boundaries

| Task family | Evidence prerequisites | Output claim |
| --- | --- | --- |
| Semantic similarity | Permitted content or descriptions, compatible representation, defined retrieval task | Nearness of meaning under the tested representation |
| Seed affinity | Seed, eligible candidate pool, usable shared features, grain compatibility | Resemblance to the defined seed |
| Behavioral affinity | Time-stamped observations, comparable coverage and behavior windows | Similar observed actions during the stated window |
| Outcome propensity | Training/validation needs defined event, cutoff, horizon, mature observations and valid evaluation; inference needs an existing applicable validated model and suitable pre-cutoff features | Estimated probability in the stated population and horizon when validated |
| Cohorts | Comparable permitted features and a repeatable grouping method | Shared observed patterns; no forced numeric score |
| Aggregate measurement | Permitted outcome and comparison data, compatible units, verified release controls | Results within the stated observable population |

Incremental response requires treatment information and a valid causal design; it is a later modeling capability. Permitted experimental measurement can still be planned as an optional pilot path. Neither propensity nor attributed conversions proves the effect of advertising.

An identifier is a lookup key, never a semantic feature. Similarity uses permitted attributes, content, or events. Cosine nearness cannot be relabeled as purchase probability. Missing facts remain unknown. The system may abstain with a reason.

## 5 Source profiles and the type registry

Core services use canonical entities, observations, events, content items, relationships, labels, policies, and artifact references. A source profile defines source/version, collection method, mapping to these primitives, observation grain, key namespace, value types and units, event and availability times, delivery lag, coverage, missingness, content resolution, quality rules, rights, execution and output policies, and limits.

The type registry defines what each unit or identifier represents, its namespace rules, validation, temporal validity, and allowed relationships. All extensions receive the same evidence and non-embedding rules. Registering a new type never establishes identity equivalence. Unknown or ambiguous semantics remain quarantined.

### Reference profiles

- ACR viewing profile: accepts documented viewing observations and content metadata. The source contract establishes whether its key refers to a screen, device, household, or another unit. Behavior windows and observation coverage are required for affinity; qualified labels are required for outcome modeling.
- Web-event profile: preserves event type, time, availability, supplied browser/account/session or other unit, collection context, and outcome coverage. A missing event is not an observed negative by default.
- URL-content profile: preserves content locator, canonicalization rules, permitted content, language, publication or observation time, and source. Page meaning supports context claims. Linking page observations to another unit requires an approved relationship.

These profiles are reference conformance cases, not three mandatory live integrations. New sources using supported transports, primitives, transforms, and policy enforcement can use configuration and approved mappings. New capabilities require versioned extensions. No source is promised universal configuration-only onboarding.

Shared semantic spaces across content families need task-specific validation. Equal vector dimensions or an equal encoder version alone cannot establish cross-media utility or shared audiences.

## 6 Execution location and output controls

Source profiles reference authoritative execution and output policy artifacts. The run selects an execution_location_ref and binds all applicable execution_policy_refs, output_policy_refs, requested_outputs, destinations, aggregation_rule_refs, and budget_refs. Session 2 will define their exact schemas.

| Policy dimension | Required meaning |
| --- | --- |
| Execution boundary | Allowed tenant environment, warehouse, clean room, or other registered location; residency and capabilities |
| Data operations | Permitted intake, raw-data access, feature construction, joins, training, inference and measurement |
| Output artifact | Allowed scores, cohort definitions, membership, aggregates, models, embeddings, reports and logs |
| Output grain and destination | Unit and granularity allowed to leave each boundary; recipient and use constraints |
| Disclosure controls | Required distinct-unit thresholds, approved dimensions, suppression and other supplied rules |
| Query and release controls | Repeated-query limits, cumulative budgets, privacy controls, and accounting where required |
| Authority and time | Issuer, policy version, effective period, enforcement method and evidence of current permission |

Apply every contributing source's restrictions through lineage. A permissive source cannot override a restrictive one. If policies are contradictory, the task is blocked under that contract. If required rules are unknown, it is provisional and cannot proceed.

Internal computation and output egress are different operations. A clean room may permit internal scoring and aggregate output while forbidding exported row-level scores. It may also prohibit the scoring operation itself. Verify both; do not assume unrestricted compute because raw data stays inside.

Enforce each threshold using its specified counted unit and all supplied predicates. Do not invent a universal cohort size. Apply repeated-query controls and budgets where applicable, including concurrent release accounting. Suppression must not expose identities through exceptions or logs.

An aggregate-only pilot may return a permitted cohort definition and aggregate evidence. It does not return membership IDs or imply outside activation. Moving data to another environment to bypass a rule is prohibited. Alternative outputs require a separate explicit task contract.

Public AWS and Snowflake documentation illustrates that aggregation controls are platform-specific [R1, R2]. The product requirement is policy-driven enforcement; no named clean-room implementation or threshold is assumed.

Default scope excludes sensitive trait inference, children, precise-location targeting and sensitive audiences. Apply these restrictions to labels, proxy features, semantic mappings, names and outputs. Cross-client reuse of models, features, embeddings, segments or retained learning requires explicit source and client rights. Ownership and derivative-use terms, redistribution, retention and withdrawal duties are part of the policy contract; a file, ID or consent string alone does not establish all permissions.

## 7 Modeling and evidence requirements

Profiling covers validity, duplicates, missingness, freshness, temporal coverage, observation coverage, source overlap, conflicts, grain, join fan-out, and permissions. Structural quality does not prove predictive utility. Reports preserve observed, declared, provider-inferred, model-inferred, and unknown evidence.

Feature plans keep numeric, categorical, behavioral, temporal, geographic and semantic representations distinct. Learn preprocessing on training data. Features and relationships must both be available by the prediction cutoff. A late backfill or later-discovered relationship cannot enter an earlier historical prediction.

Use simple baselines first. Affinity can use appropriate distances or multiple seed prototypes. Labeled propensity can compare logistic regression and a bounded boosted-tree candidate. Complex models require a justified gain and deployment fit. Hybrid weights need compatible scales and declared coverage rules; missing channels cannot silently become zero or equivalent evidence.

Splits match the deployment question: new entities, future periods, or both. Keep verified aliases and related observations from invalid leakage across relevant partitions. Separate model selection, calibration and the locked final test. Mature observation windows define valid negatives; unlabeled and censored records do not.

Affinity evidence includes held-out seed retrieval, source checks, stability and reach comparisons. It establishes resemblance to that seed. Propensity requires ranking at operational reach, sparse-outcome metrics, calibration evidence, population base rates, observation coverage and uncertainty. Report source and coverage slices. Brier score and log loss alone do not isolate calibration.

Assess provider-artifact signals, vendor proxy labels, duplicated source data, seed-definition leakage, observation-effort bias and out-of-distribution inputs. A weak candidate can fail while the baseline succeeds. An eligible run can complete with a report of no useful signal.

## 8 Agents and controlled tools

Use a durable orchestrator with bounded roles for briefing, fitness, meaning, joins/features, experiments, evaluation, output preparation and monitoring. Roles may share services. Agents receive only approved schemas, descriptions, summaries and artifact references that may leave the execution boundary.

Deterministic tools calculate profiles, enforce policy, build features, train and score, compute metrics, apply suppression, and prepare and commit releases. Agent-generated permissions or calculations cannot establish a pass. Strict schemas are followed by domain and policy validation.

Run stages preserve received inputs, profile, confirmed contract, prepared features, fitted representation/model, evaluation, scores or cohorts, and completion artifacts. Paused, failed and cancelled execution states remain separate from task verdicts. Unsupported statistical outcomes can complete with truthful reports. Restart only from recorded checkpoints with permitted idempotent operations or reconciliation.

Audience versions preserve draft, prepared, approved, released, expired and revoked lifecycle events. A changed membership or policy needs a new decision and the applicable approval. Agents cannot release their own recommendation.

## 9 Output and buyer-agent exchange

Score records identify entity token, namespace, output grain, score type and scale, model and feature versions, prediction cutoff, scoring time, expiry, inclusion_disposition, and reason codes. included, excluded and abstained describe record-level disposition, not task fitness. Probability outputs add target and horizon. Cohort membership has its own contract and need not carry a numeric score.

Evidence cards bind source and profile versions, task verdict, claim type, unit, seed/target/brief, universe, time windows, representation, evaluated baselines, metrics with denominators, uncertainty, coverage, limits, permitted uses, execution boundary and output controls. An exploratory claim stays visible even when the producing task is eligible.

Release manifests bind immutable artifacts, checksums, model evidence, task decision, counts, current policy, expiry, destination and authorizer. Delivery receipts distinguish submitted, accepted, matched, live and measured outcomes. An activation handle is not proof of efficacy.

AdCP discovery and activation are versioned boundary adapters over these contracts. Session 2 derives exact fields from a pinned schema and identifies extension or referenced-artifact fields. The canonical product must remain usable without AdCP. VAC/GTS compatibility contracts identify model, revision, transformation, space, dimensions, encoding, normalization, metric, represented unit, provenance, time and permitted uses.

Direct comparison requires compatible spaces; a projector requires held-out alignment evidence. Otherwise use documented criteria/segment fallback or abstain. Separate exchange conformance, representation alignment and agent routing tests. Neither simulations nor alignment success proves predictive value.

## 10 Functional requirements

P0 is required for enabled MVP tasks. P1 is an optional path or later capability. Each acceptance criterion is a future verification requirement, not a claim of a passed test.

**FR01 File intake — P0.** Purpose: preserve input meaning. Actor: ingestion service. Inputs: manifest and permitted CSV/Parquet snapshot. Outputs: parsed snapshot and errors. Failure: quarantine malformed rows or contract. Acceptance: no silent ID truncation or postal-code numeric conversion; counts reconcile.

**FR02 Namespaces — P0.** Purpose: prevent false matches. Actor: steward and join service. Inputs: typed keys and namespaces. Outputs: separate entities or approved relations. Failure: unresolved matches remain absent. Acceptance: equal strings from different namespaces do not join automatically.

**FR03 Grain compatibility — P0.** Purpose: preserve the scored unit. Actor: contract validator. Inputs: task and input units. Outputs: task verdict and grain plan. Failure: block demonstrated incompatible comparisons; provisional if required semantics are missing. Acceptance: household, browser and content records cannot enter an undeclared common entity representation.

**FR04 Profiling — P0.** Purpose: expose input limits. Actor: profiler. Inputs: an eligible profiling task. Outputs: calculated counts, quality, freshness and coverage. Failure: report unavailable dimensions. Acceptance: samples and estimates are labeled; no invented full-population statistics.

**FR05 Source rights — P0.** Purpose: enforce intended use. Actor: policy service. Inputs: authoritative permissions and task. Outputs: permission evidence and verdict. Failure: provisional for unverified permission; blocked for known prohibited use. Acceptance: the agent cannot create consent, waive rights or run the dependent task while unresolved.

**FR06 Valid joins — P0.** Purpose: prevent fan-out and false identity. Actor: join validator. Inputs: approved temporal relationship plan. Outputs: coverage, cardinality and lineage. Failure: block demonstrated invalid joins. Acceptance: shared IP, area or meaning alone does not merge entities; historical relations were available at cutoff.

**FR07 Feature time — P0.** Purpose: prevent leakage. Actor: feature service. Inputs: definitions and cutoffs. Outputs: point-in-time snapshot. Failure: block proven future/late features; provisional when timing evidence is missing. Acceptance: event and availability rules both hold, including backfills and relationship history.

**FR08 Semantic meaning — P0.** Purpose: preserve measurements. Actor: meaning agent and steward. Inputs: approved dictionary and descriptions. Outputs: versioned mapping with evidence kind. Failure: retain unresolved mappings. Acceptance: survey, visit, viewing and purchase remain distinct even when topic labels match.

**FR09 ID and context boundary — P0.** Purpose: keep keys out of semantics and uncontrolled disclosure. Actor: gateway. Inputs: policies and approved agent/embedding payloads. Outputs: permitted sanitized context. Failure: block prohibited payloads. Acceptance: opaque keys never enter embeddings; summaries and content cannot bypass source output rules.

**FR10 Missing propensity labels — P0.** Purpose: unify evidence and routing. Actor: task router. Inputs: a new-model build/validation request and label report. Outputs: PROVISIONAL with unsupported_outcome_probability and exact label requirements when labels are inadequate. Failure: no training or probability release until resolved. Acceptance: no exploratory-or-blocked fitness alias; eligible affinity is assessed separately. Existing validated-model inference has its own prerequisites.

**FR11 Seed exclusions — P0.** Purpose: evaluate and deliver the intended audience. Actor: scientist and scorer. Inputs: seed, universe and approved alias relationships. Outputs: documented exclusions. Failure: disclose missing alias coverage or return no new candidates. Acceptance: net-new tasks exclude seeds and verified aliases; held-out aliases do not leak into training.

**FR12 Bounded experiments — P0.** Purpose: make comparison sound. Actor: scientist/model service. Inputs: recorded baseline, candidates, budgets and split. Outputs: computed comparison. Failure: stop or retain failed candidates as evidence. Acceptance: model and threshold selection never use the locked final test.

**FR13 Probability evidence — P0 for probability tasks.** Purpose: support the claim. Actor: evaluation service. Inputs: mature labels and new validation results for training/promotion, or applicable prior validation evidence for existing-model inference/publication. Outputs: publication verdict and calibration evidence. Failure: provisional before required evidence; blocked if defined promotion criteria fail. Acceptance: outcome, horizon, population, validity and base-rate effects remain explicit; future labels on scored candidates are not an inference prerequisite.

**FR14 Typed outputs — P0.** Purpose: prevent claim substitution. Actor: output service. Inputs: approved results. Outputs: typed score or separate membership artifact. Failure: null/abstention with reasons. Acceptance: cosine, affinity, rank and probability remain distinct; cohort membership requires no score.

**FR15 Count reconciliation — P0.** Purpose: make reach legible. Actor: output service. Inputs: stage results. Outputs: count report with grain and denominator. Failure: withhold irreconcilable claims. Acceptance: input, excluded, scored, selected and released counts reconcile; aggregate-only reports respect disclosure rules.

**FR16 Release authority — P0.** Purpose: separate recommendation from publication. Actor: reviewer and release service. Inputs: prepared checksum, current verdict/policy and destination. Outputs: authorization or decision. Failure: block stale, revoked or conflicting release. Acceptance: changed membership cannot use the old pilot approval.

**FR17 Delivery retries — P0.** Purpose: avoid duplicate side effects. Actor: connector/operator. Inputs: idempotency key and delivery state. Outputs: receipt or reconciliation task. Failure: uncertain remote state is not automatically retried. Acceptance: internal keys alone never imply exactly-once remote delivery.

**FR18 Suppression and expiry — P0.** Purpose: keep release current. Actor: scorer/release service. Inputs: latest eligible suppression and time rules. Outputs: filtered immutable artifact. Failure: no commit with unresolved current policy. Acceptance: suppression is checked at scoring and again at commit; changes invoke the new-version rule.

**FR19 Untrusted content — P0.** Purpose: protect tool authority. Actor: agent gateway. Inputs: imported content and tool requests. Outputs: allowlisted actions. Failure: reject injected authority or tenant changes. Acceptance: a page or attribute cannot change budgets, permissions or export policy.

**FR20 Reproducibility — P0.** Purpose: support audit. Actor: operator. Inputs: snapshots, code, definitions, model and decision versions. Outputs: replay references and tolerance. Failure: flag missing provenance. Acceptance: stored agent decisions can be inspected; deterministic numerical replay uses pinned inputs and documented tolerance.

**FR21 Weak signal — P0.** Purpose: preserve honest results. Actor: evaluator. Inputs: computed tests. Outputs: candidate verdict and limitations. Failure: no utility claim where evidence fails or is absent. Acceptance: a successful job can report no useful model without relabeling affinity as prediction.

**FR22 Withdrawal — P0.** Purpose: honor source lifecycle. Actor: steward/operator. Inputs: revocation and lineage. Outputs: affected-artifact remediation and downstream request receipts. Failure: prohibit new affected processing; show failed or unsupported downstream removal. Acceptance: row deletion is not described as erasing influence from model weights.

**FR23 Insufficient information — P0.** Purpose: prevent invented audiences. Actor: router. Inputs: keys without usable evidence. Outputs: PROVISIONAL with specific requirements and insufficiency reasons. Failure: no fabricated traits or rankings. Acceptance: opaque IDs alone do not yield meaningful similarity; a proven prohibited task remains blocked independently.

**FR24 Representation compatibility — P0.** Purpose: make similarity valid. Actor: representation validator. Inputs: space/model/transform metadata and vectors. Outputs: compatible route, validated projector, fallback or abstention. Failure: reject wrong spaces, zero vectors or inadequate coverage. Acceptance: dimensions/version alone are insufficient; alignment tests and task utility remain separate.

**FR25 Task fitness — P0.** Purpose: use one vocabulary. Actor: router/report service. Inputs: exact task and verified evidence. Outputs: ELIGIBLE, PROVISIONAL or BLOCKED, reasons and next actions. Failure: reject unknown verdict values or silent task changes. Acceptance: dataset fitness is a set of decisions; exploratory is a claim label; provisional cannot authorize execution.

**FR26 Source onboarding — P0.** Purpose: extend without a false guarantee. Actor: steward/integration owner. Inputs: source contract and supported capabilities. Outputs: validated configuration/mapping or a required versioned extension. Failure: provisional until missing integration or validation evidence is resolved; blocked for a demonstrated prohibited task. Acceptance: configuration-only onboarding applies to supported transports, primitives, policy enforcement and transforms; new capabilities require scoped engineering and conformance tests.

**FR27 Execution binding — P0.** Purpose: enforce location. Actor: policy/orchestration service. Inputs: profile/run location and execution rules. Outputs: validated selected boundary. Failure: provisional for missing verification; blocked for an established incompatible location or operation. Acceptance: restricted data is not moved locally to make a task work.

**FR28 Artifact egress — P0.** Purpose: route outputs correctly. Actor: policy/release service. Inputs: lineage, artifact, output unit and destination. Outputs: separate task verdicts for internal computation and release. Failure: blocked for explicitly forbidden row egress. Acceptance: permitted internal scoring or aggregates never imply a permitted score-file export.

**FR29 Aggregation enforcement — P0 for aggregate tasks.** Purpose: apply supplied disclosure controls. Actor: execution/release service. Inputs: threshold units, dimensions, suppression and applicable budgets. Outputs: permitted aggregates and policy-check evidence. Failure: provisional for missing rules; blocked for proven failed constraints. Acceptance: all contributing policies and cumulative controls are enforced, not a guessed universal size.

**FR30 Windows target — Retired.** Merged into NFR08 in Revision 2 because it constrains verification assets rather than product behavior. The ID is kept so existing references stay stable.

**FR31 Type extensions — P0.** Purpose: generalize unit semantics. Actor: registry/steward. Inputs: type definition and evidence. Outputs: versioned registered type. Failure: quarantine unconfirmed semantics. Acceptance: new types follow the same key, grain, namespace, validity and evidence rules as existing types; source names cannot set grain.

**FR32 Direct agent evaluation — P0.** Purpose: prove routing competence. Actor: independent test owner. Inputs: task-specific oracles and locked fixtures. Outputs: correctness and cost results. Failure: no autonomous release claim when critical contracts fail. Acceptance: isolated agents cannot read answer keys; tests include missing labels, forbidden egress, valid aggregates, clean controls and repaired traps.

**FR33 Exchange mapping — P1 integration.** Purpose: let buyer agents use reviewed outputs. Actor: adapter owner. Inputs: canonical artifacts and pinned protocol schema. Outputs: verified discovery/activation mapping and conformance evidence. Failure: referenced artifacts, documented fallback or blocked incompatible exchange. Acceptance: extensions and simulations are labeled; no invented standard fields or confirmed deployment.

**FR34 Measurement binding — P1 optional pilot.** Purpose: add downstream evidence. Actor: measurement owner. Inputs: exact release, compatible outcomes, exposure/assignment, times and coverage. Outputs: permitted measurement artifact. Failure: provisional for missing evidence; blocked for known policy or design violation. Acceptance: original score type and backtest never change because later outcomes arrive.

**FR35 Experimental claims — P1 optional pilot.** Purpose: limit causal assertions. Actor: scientist/reviewer. Inputs: predeclared design and measured results. Outputs: assigned-group effect or explicitly limited association. Failure: reject unsupported causal promotion. Acceptance: intention-to-treat is primary for randomized studies; exposure contrasts and targeting-superiority claims need their own justified estimators/designs.

**FR36 Feedback reuse — P1 optional path.** Purpose: improve future versions lawfully. Actor: steward/scientist. Inputs: release-bound outcomes, coverage, maturity and reuse rights. Outputs: a later eligible label/feature snapshot. Failure: exclude unobserved negatives, immature outcomes or forbidden reuse. Acceptance: feedback cannot enter the earlier run's cutoff or retroactively establish probability validation.

**FR37 Usage and cost recording — P0.** Purpose: make BR12 and the analyst-effort measure computable. Actor: metering service and reviewers. Inputs: job, task, run and release usage, review and analyst time, contracted cost parameters. Outputs: usage_cost_record documents with category, basis and allocation method. Failure: flag unknown costs; never invent prices. Acceptance: cost per comparable completed run (abstentions and no-signal runs included), cost per reviewed release and contribution are reproducible from records; allocated costs name their allocation method.

**FR38 Verdict authority — P0.** Purpose: keep agents advisory. Actor: task router. Inputs: deterministic check results and facts established by a policy service, steward or reviewer. Outputs: a task decision recording each prerequisite's establishing authority; agent proposals stored as separate advisory records. Failure: reject facts or decisions attributed to an agent. Acceptance: an agent proposal cannot change a verdict; the routing benchmark scores proposals against hidden oracles independently of authoritative decisions.

**FR39 Decision validity — P0.** Purpose: prevent stale eligibility. Actor: task router and release service. Inputs: decision time, a configured maximum validity and policy effective periods. Outputs: valid_until and its basis on every decision. Failure: a lapsed or policy-changed decision requires reassessment before execution or commit. Acceptance: valid_until never exceeds the earliest bound; commit rejects lapsed decisions.

**FR40 Quarantine intake — P0.** Purpose: inspect new sources safely before registration. Actor: steward and ingestion service. Inputs: snapshot, draft or quarantined profile, and an execution policy that permits intake and profiling at the location. Outputs: profile reports under an ELIGIBLE intake or profiling task. Failure: modeling, scoring and egress tasks remain PROVISIONAL with unregistered_source_profile until steward confirmation. Acceptance: the same quarantined source yields an ELIGIBLE profiling task and a PROVISIONAL scoring task.

**FR41 Reason-code registry — P0.** Purpose: one diagnostic vocabulary. Actor: platform owner. Inputs: registry entries with dimension, decision effect and aliases. Outputs: validated codes for task decisions, execution failures, record inclusion and delivery. Failure: reject unknown codes and codes used outside their dimension. Acceptance: legacy names resolve to canonical codes (leakage_detected becomes temporal_leakage); budget and cancellation codes never appear as verdict reasons.

**FR42 Post-release monitoring — P1.** Purpose: detect drift after release. Actor: monitoring service and operator. Inputs: released model or audience, reference distributions and supplied thresholds. Outputs: monitoring reports with a proposed action. Failure: missing thresholds produce no automatic action. Acceptance: monitoring can propose reassessment or refresh but never releases, modifies or revokes an artifact by itself.

## 11 Nonfunctional requirements

**NFR01 Tenant isolation — P0.** Purpose: prevent cross-tenant access. Actor: platform security owner. Inputs: authenticated context and artifact scope. Outputs: enforced access across data, identity maps, prompts, embeddings, models and caches. Failure: deny mismatched access. Acceptance: service-derived tenant scope and negative access checks cover every enabled surface.

**NFR02 Durable execution — P0.** Purpose: recover without duplicated actions. Actor: operator. Inputs: job state, checkpoint and retry contract. Outputs: resumable jobs and cancellation receipts. Failure: bounded retry or reconciliation. Acceptance: mutations use idempotency/reconciliation; cancellation starts no new delivery; statistical verdicts remain separate from infrastructure failure.

**NFR03 Budget enforcement — P0.** Purpose: control resources and release allowance. Actor: orchestration/policy owner. Inputs: configured token, scan, trial, compute, query and release limits. Outputs: accounted usage and paused/ended work. Failure: stop before unauthorized spend or release. Acceptance: concurrent accounting cannot exceed enforced allowances; artifacts and controls survive a budget stop.

**NFR04 Restricted observability — P0.** Purpose: make operations reviewable within policy. Actor: operations owner. Inputs: permitted telemetry and disclosure rules. Outputs: time, cost, version, decision, count and failure records. Failure: suppress prohibited telemetry and retain an allowed error record. Acceptance: logs, summaries and support views cannot leak raw IDs or restricted outputs.

**NFR05 Measured performance — P0.** Purpose: set defensible service targets. Actor: performance owner. Inputs: named workload, execution profile and cost method. Outputs: measured duration, resources and cost. Failure: record failed/not-run benchmarks and unresolved targets. Acceptance: no unmeasured scale or latency guarantee; agreed targets follow actual benchmark evidence.

**NFR06 Policy freshness — P0.** Purpose: prevent stale authority. Actor: policy/release owner. Inputs: lineage and current policy versions. Outputs: recomposed constraints and fresh task/release decisions. Failure: stop unresolved or newly prohibited work. Acceptance: policy changes invalidate affected eligibility/authorizations and trigger reassessment before execution or commit.

**NFR07 Bounded model context — P0.** Purpose: control cost and disclosure. Actor: agent-platform owner. Inputs: approved schemas, plans, content and exception reports. Outputs: scoped calls and policy-bound caches. Failure: reject oversized or disallowed context. Acceptance: calls avoid per-identity LLM reasoning by default; caches respect tenant, policy, version and retention boundaries.

**NFR08 Windows verification — P0 for local assets.** Purpose: keep later checks runnable. Actor: evaluation engineer. Inputs: Windows workspace and separately verified remote contracts. Outputs: PowerShell/pathlib commands and compatible runners. Failure: flag unsupported dependencies or remote execution. Acceptance: the local path uses no Bash/Unix/WSL dependency and does not bypass remote data restrictions.

## 12 Verification and traceability

Session 3 creates checks for the contracts and failure modes implemented in scope. Real data is required for predictive evidence; actual integrations are required for delivery and clean-room enforcement evidence. A mock policy can test routing logic but cannot certify a remote platform.

| Business need | Product requirements | Verification focus |
| --- | --- | --- |
| BR01 Task clarity | FR03, FR10, FR25 | Exact operation, output, unit and verdict consistency |
| BR02 Extensible inputs | FR01, FR02, FR08, FR26, FR31, FR40 | Three reference profiles and supported versus new capability onboarding |
| BR03 Correct routing | FR04, FR10, FR21, FR23, FR25, FR32, FR38, FR41 | Task-specific locked cases and false-block/deferral metrics |
| BR04 Execution/output control | FR05, FR27, FR28, FR29 | Same source with blocked row export and eligible qualifying aggregates |
| BR05 Honest evidence | FR07, FR11, FR12, FR13, FR14, FR24 | Leakage, score types, calibration and abstention |
| BR06 Bounded agents | FR09, FR19, FR38, NFR03, NFR07 | Context restrictions, injected text and budget boundaries |
| BR07 Reviewed release | FR15 to FR18, FR33, FR39, NFR06 | Counts, checksums, policy freshness and receipts |
| BR08 Downstream evidence | FR34 to FR36 | Release binding, coverage, assignment-based claims and later feedback |
| BR09 Tenant and use rights | FR05, FR06, FR09, FR22, NFR01, NFR06 | Authorization, lineage, withdrawal and isolation |
| BR10 Auditability | FR20, FR39, FR42, NFR02, NFR04 | Versioned decisions, artifacts, recovery and replay |
| BR11 Independent proof | FR12, FR21, FR24, FR32, FR37, NFR08 | Separate routing, semantics, statistical utility and cost results |
| BR12 Commercial visibility | FR37, NFR03 to NFR05 | Attributed run/release costs and named denominators |

Agent evaluation uses neutral case IDs, hidden expected decisions, independent checks, clean controls and held-out defect combinations. Reports separate exchange conformance, alignment GTS, routing correctness, statistical utility, destination readiness and downstream evidence. Passed, failed and not-run check results are verification labels, not task verdicts.

## 13 Decisions and Session 2 boundary

The pilot still needs its objective, actual source contract and units, execution location, output permission, observable population, seed or content brief or qualified labels, baseline, minimum worthwhile improvement, reviewers and cost limits. These are inputs to a real pilot, not blockers to completing the specification.

Session 2 must implement the shared vocabulary and source/run execution fields in schemas. It resolves exact policy object structure, schema dialect, type extensions, job contracts, release authorization and pinned exchange mappings. Session 1 does not generate JSON schemas, implementation code, the detailed modeling report, or the engineering backlog.

Revision 2 records the Session 2 review corrections: the traceability table now covers every active requirement (FR04, FR11, NFR06 and NFR08 were untraced); FR30 is retired into NFR08; FR37 adds the usage and cost record that BR12 and the analyst-effort measure need; FR38 separates advisory agent proposals from authoritative task decisions; FR39 adds decision validity; FR40 defines quarantine profiling; FR41 creates one reason-code registry; and FR42 adds post-release monitoring as P1. The scientific rules, verdict vocabulary and scope are unchanged.

## 14 Reference guidance

Primary references inform specific design details. Their example policies and implementations do not set this product's thresholds or certify its behavior. Accessed 14 October 2026.

- R1 AWS Clean Rooms aggregation analysis rules: https://docs.aws.amazon.com/clean-rooms/latest/userguide/analysis-rules-aggregation.html
- R2 Snowflake aggregation policies: https://docs.snowflake.com/en/user-guide/aggregation-policies
- R3 Historical feature availability: https://docs.feast.dev/getting-started/concepts/point-in-time-joins
- R4 Leakage and preprocessing: https://scikit-learn.org/stable/common_pitfalls.html
- R5 Probability calibration: https://scikit-learn.org/stable/modules/calibration.html
- R6 AdCP discovery and activation: https://docs.adcontextprotocol.org/docs/signals/tasks/get_signals and https://docs.adcontextprotocol.org/docs/signals/tasks/activate_signal
- R7 Agentic Audiences and existing alignment bridge: https://github.com/IABTechLab/agentic-audiences and https://github.com/EvgenyAndroid/adcp-signals-adaptor
