# Agent Design

Session 2 | Revision 1 | 14 October 2026

Agents interpret schemas and objectives, map meaning, propose features and experiments, and explain results. Deterministic services enforce contracts and permissions, join data, compute features and metrics, train and score, and prepare releases. The reasoning model is replaceable, and no agent output can establish a permission, a calculation or a verdict. This document specifies roles, authority, context limits, tools, state machines, failure handling and evaluation. The reference implementation is in `src/aip/agents/`, `src/aip/routing/`, `src/aip/release/` and `src/aip/lifecycle/`.

## 1 Orchestrator and roles

One durable orchestrator runs every role. Roles are bounded configurations of the same agent runtime, not separate services. A role sees only its allowlisted tools, and every tool call passes through the gateway described in Section 4.

| Role | Purpose | Allowed tools | Escalates to |
| --- | --- | --- | --- |
| `briefing` | Turn a request into a draft objective and task list | `list_profiles`, `read_artifact` | analyst |
| `fitness` | Read profile reports and propose per-task verdicts | `read_artifact`, `read_decision`, `read_profile_report` | data_steward |
| `meaning` | Propose attribute-to-dictionary mappings with evidence kind | `propose_mapping`, `read_artifact`, `read_dictionary` | data_steward |
| `joins_features` | Propose relationship and feature plans | `propose_feature_plan`, `read_artifact`, `run_pit_check` | scientist |
| `experiments` | Propose bounded experiments within the model allowlist | `read_artifact`, `read_metrics`, `submit_job` | scientist |
| `evaluation` | Interpret computed metrics; never compute them | `read_artifact`, `read_metrics` | scientist |
| `output_preparation` | Draft evidence cards and release notes | `draft_evidence_card`, `read_artifact` | release_reviewer |
| `monitoring` | Read monitoring reports and propose reassessment | `read_artifact`, `read_monitoring` | operator |

Every role produces at most two kinds of output:

- **Advisory proposals** (`agent_proposal`), such as a proposed verdict with registry reason codes and next actions.
- **Draft artifacts** (mappings, feature plans, evidence-card text) submitted to a deterministic service that validates them against their contracts.

No role can commit a decision, a policy, a release or a delivery.

## 2 Authority model

| Decision or fact | Authority | Agent role |
| --- | --- | --- |
| Task verdict | Task router service, from established prerequisites (FR38) | Proposes a verdict; the proposal is recorded and benchmarked |
| Schema, tenant, snapshot, unit, grain, policy composition, aggregation rules | Router's deterministic checks | None |
| Rights, sensitive screening | Policy service or rights owner | Can request evidence |
| Label qualification, feature timing, coverage, aggregate thresholds, model validation, representation compatibility | Deterministic jobs whose reports become facts | Interprets reports |
| Source profile and type confirmation | Human data steward | Proposes mappings |
| Release authorization | Human release reviewer (schema rejects non-human actors) | Drafts notes |
| Delivery state | Destination receipt with confirmation | None |
| Monitoring action | Operator, from reports against supplied thresholds | Proposes reassessment |

`evidence_bundle` facts and `task_decision` prerequisites exclude `agent` as an establishing authority. `task_decision.decided_by.authority` must be `router`, and `agent_proposal.authority` must be `advisory`.

The router may cite proposal identifiers for audit, but it never reads proposal content. `tests/test_routing.py` shows an ELIGIBLE proposal leaving a BLOCKED verdict unchanged.

## 3 Context and memory limits

Agents receive only content that may leave the execution boundary:

- approved schemas and dictionary descriptions
- sanitized profile and evaluation summaries
- task and decision documents
- artifact references

Raw identifiers, row-level data and restricted outputs never enter model context. Calls are scoped to schemas, plans and exception reports, never to individual identities (NFR07). A role's working memory is limited to one task version. Nothing persists across tasks or tenants except versioned artifacts written through services.

Caches are keyed by tenant, policy version, contract version and prompt-template version. They expire with the shortest applicable retention period. Prompt templates are versioned artifacts referenced by every proposal (`prompt_template_ref`).

Imported text is data. Page content, attribute names, file contents and comments cannot change tool permissions, tenant scope, budgets, policies or release rules (FR19).

## 4 Tool gateway contract

`aip.agents.gateway.ToolGateway` enforces the following on every call:

1. The tool must be on the caller's role allowlist; otherwise the call is denied and audited.
2. The tenant comes from the authenticated `ActorContext`. Handlers receive it as a separate argument, and tool arguments can never set or override it.
3. Arguments containing authority fields at any depth are rejected. These fields are `authority`, `authorization`, `budget`, `budget_refs`, `export_policy`, `permissions`, `policy`, `policy_refs`, `release`, `tenant_id`, `verdict`. This blocks injected text that tries to smuggle scope or permission changes.
4. Each call consumes declared budget units. A call that would exceed the budget is denied with `budget_exceeded`. Budget exhaustion pauses work without discarding artifacts (NFR03).
5. Every allowed or denied call is appended to the context's audit log.

No general SQL, shell, arbitrary URL fetch or write credentials are exposed to agents. Mutating operations (job submission, release preparation) are tools that call deterministic services and require idempotency keys.

## 5 State machines

Each dimension has its own machine (`aip.lifecycle.state_machines`). A transition outside the table raises `TransitionError`.

**Job execution state**

- `queued` → `cancelled`, `running`
- `running` → `cancelled`, `failed`, `paused`, `reconciling`, `succeeded`
- `paused` → `cancelled`, `running`
- `reconciling` → `failed`, `running`, `succeeded`
- `succeeded` → terminal
- `failed` → terminal
- `cancelled` → terminal

A job records its failure code only in the `failed` state, using execution-failure codes such as `budget_exceeded` or `cancelled`. Statistical outcome is a separate field: a job can succeed with `no_useful_signal`. Restart resumes only from a recorded checkpoint. Cancellation starts no new delivery.

**Audience lifecycle**

- `draft` → `prepared`
- `prepared` → `approved`, `revoked`
- `approved` → `expired`, `released`, `revoked`
- `released` → `expired`, `revoked`
- `expired` → terminal
- `revoked` → terminal

Preparing a release requires an ELIGIBLE release decision. Approval is a human authorization bound to the prepared checksum. Commit (`aip.release.commit`) rechecks all of the following, and any failure raises `CommitError`:

- authorization decision, checksum, destination and validity window
- release expiry
- that the decision is ELIGIBLE and still current, with unchanged policy versions
- suppression at commit time

A changed membership or policy requires a new prepared version and a new approval.

**Delivery state**

- `submitted` → `accepted`, `failed`, `unknown`
- `unknown` → `accepted`, `failed`, `submitted`
- `accepted` → `failed`, `live`, `matched`
- `matched` → `failed`, `live`
- `live` → terminal
- `failed` → terminal

`unknown` means the remote state could not be established. The only next step is reconciliation (`next_delivery_action` returns `reconcile`). A retry with the same idempotency key is allowed only for a failure the destination never acknowledged. Acceptance, matching and live states require destination confirmation.

**Task decision lifecycle**

A decision is issued with a `valid_until` bound. It lapses at that time or as soon as any bound policy version changes (`is_decision_current`). A changed task, input, objective, environment, evidence or policy produces a new decision that cites the old one through `supersedes`. Old decisions are retained for audit.

## 6 Failure handling and escalation

| Condition | Behavior | Escalation |
| --- | --- | --- |
| Model output fails schema validation or uses an unknown or wrong-dimension reason code | Proposal rejected (`make_proposal` raises); no retry with the same prompt | Role owner |
| No reasoning model configured or the provider is unavailable | `NullReasoningModel` returns a PROVISIONAL proposal with `insufficient_information`; deterministic routing continues | Operator |
| Budget exhausted | Gateway denies the call; the job pauses or fails with `budget_exceeded`; artifacts are kept | Analyst |
| Tool or argument outside role authority | Denied and audited | Security owner |
| Fact missing for a prerequisite | Task stays PROVISIONAL with the catalog's missing reason and remedy | Fact owner named in the remedy |
| Uncertain remote delivery | Reconciliation task; no automatic retry | Export operator |
| Policy change or decision expiry | Reassessment before execution or commit | Policy owner |

## 7 Routing benchmark design

The benchmark measures agent routing directly, separately from model utility. It has three components:

- **Cases** (`routing_case`): neutral IDs and paths to a task, an evidence bundle and visible world documents.
- **Oracles** (`routing_oracle`): stored in a separate `oracle/` directory, authored by a human (the schema rejects non-human authors).
- **Harness** (`aip.evaluation.routing_benchmark`): reads the oracles and scores predictions.

The harness reports:

- verdict accuracy, and accuracy of verdict plus mandatory reasons
- macro F1
- critical false-safe rate
- premature clearance of provisional cases
- false-block rate
- unnecessary deferral rate
- the expected distribution

Evaluated agents must run in a fresh, isolated workspace with allowlisted tools and only `cases/` and `world/` mounted. Oracles, generators and locked-suite metadata must be inaccessible. A local Windows run cannot enforce that isolation, so isolation remains not verified until a sandbox enforces it and records the boundary.

The development suite (`fixtures/routing/development`) has 12 cases: 5 BLOCKED, 3 ELIGIBLE and 4 PROVISIONAL. They cover forbidden row egress, a qualifying aggregate, a failed aggregate threshold, a missing policy, missing labels, availability leakage and its repaired counterpart, mixed grains with a permitted but unsupplied mapping (PROVISIONAL) and with no permitted relationship (BLOCKED), a provider-artifact promotion failure, quarantine profiling, and an unconfirmed source.

The deterministic rules router scores 12 of 12. That result is by construction, because the cases were authored alongside the router; it shows harness wiring, not routing competence. Reject-all and approve-all baselines fail on false blocks and critical false-safe cases (`tests/test_agents_and_benchmark.py`).

Session 3 builds a locked suite with held-out defect combinations. It then compares agents against the rules router and a competent analyst with a reusable notebook, using the same visible evidence, and measures correctness before time savings.

## 8 Model replaceability

Agents depend on the `ReasoningModel` protocol, `propose(role, sanitized_context) -> proposal fields`. Three implementations ship:

- `NullReasoningModel`, the safe default.
- `ScriptedReasoningModel`, for deterministic tests.
- `AnthropicReasoningModel`, an optional adapter installed with the `llm` extra. Its model identifier is required configuration; it is not exercised by tests.

Swapping providers changes `agent_proposal.model` and nothing in the decision path.

## 9 Not implemented in this scaffold

The following remain Session 3 or later work:

- the durable orchestrator runtime and persistence
- real tool handlers backed by services
- the agent prompt templates
- the locked benchmark suite and analyst comparator
- clean-room execution integrations
- live destination connectors
- deletion propagation
- telemetry

The scaffold provides the contracts, the router, policy composition, gateway, release rechecks, state machines, baselines and the harness they plug into.
