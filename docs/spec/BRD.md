# Business Requirements: Agentic Audience Intelligence Platform

Session 1 | Revision 1 | 14 October 2026

This document defines the business case and acceptance measures for the provider-agnostic platform. It is a product specification, not a report of tested product performance.

## 1. Business purpose

The platform turns permitted advertising data into reviewable audience or contextual products. Inputs may include viewing observations, web events, page content, transactions, surveys, CRM records, geographic aggregates, or future source families. The source contract determines what each record represents and which uses it supports. No provider, identifier, or modeling grain is the default.

Buyers need to understand whether a product resembles a seed, reflects similar behavior, forecasts a named outcome, or groups related content. Sellers need a repeatable way to test uncertain attributes, select a valid task, and disclose the evidence. Agents help assess and plan the work. Statistical services produce the scores and validation results.

The business promise is a defensible use decision, followed by an output when evidence and constraints permit it. A blocked or provisional task can be useful. Every dataset need not predict an outcome or support activation.

## 2. Customers and accountable roles

| Customer category | Business need | Typical buying role | Operating and review roles |
| --- | --- | --- | --- |
| Data owner or broker | Turn observations into tested, licensed products | Data/product leader; commercial owner | Data steward, analyst, scientist, rights owner |
| Marketplace operator | Compare and distribute products with clear evidence | Marketplace/product leader | Catalog operator, reviewer, exchange integration owner |
| Agency | Assess supplier data and build suitable audiences | Audience strategy or data lead | Planner, analyst, buyer, campaign measurement owner |
| Brand | Use permitted customer or partner signals against a named objective | Marketing/data leader | CRM or data steward, scientist, campaign operator |

Roles may overlap; the authorized actor remains explicit. A supplier describes data and rights; a buyer defines the use; a reviewer checks the prepared release. An agent cannot grant rights or commit a release on its own recommendation.

## 3. Problems and value

Today, a usable file may still contain weak signals, delayed features, mixed units, or incomplete outcome records. A familiar column name does not establish its meaning. A high similarity score does not establish purchase probability. Output rules may also allow an aggregate result while prohibiting a scored identifier file.

The platform addresses five needs: reduce repeated intake work, distinguish supported tasks from unsupported claims, test signal value against baselines, prepare controlled releases, and make evidence readable to buyers and their agents. Lower analyst effort, better routing, stronger models, destination acceptance, and downstream results are separate value claims. Each needs its own proof.

Default scope excludes sensitive trait inference, children, precise-location targeting and sensitive audiences. Cross-client reuse of models, derived features, embeddings, segments or retained learning requires explicit source and client rights. These boundaries apply regardless of source family or execution location.

## 4. Shared decision vocabulary

Every requested task receives one of three verdicts:

| Verdict | Business meaning |
| --- | --- |
| ELIGIBLE | All prerequisites for the specified operation, execution context, and requested outputs are established. This does not prove model utility or approve release. |
| PROVISIONAL | A required evidence, permission, or capability fact is missing. This exact task cannot proceed until resolved; separately permitted diagnostics need their own task verdict. |
| BLOCKED | A known violation or incompatibility prevents the requested operation. State its scope and required remedy. |

A dataset's fitness is its set of per-task decisions, with no global fitness label. Verdicts name the objective, operation, units and execution/output constraints. Building or validating propensity without qualified labels is PROVISIONAL with reason `unsupported_outcome_probability` and explicit label requirements. The reason code is diagnostic, never a status. No new-model training or probability release proceeds under that provisional task. Inference with an existing validated model does not require future labels on candidates; its feature, model-validity, population, and policy requirements still apply. Prohibited publication is BLOCKED; affinity or aggregate analysis may be ELIGIBLE on the same dataset.

“Exploratory” labels an output claim. It is not a verdict. Execution lifecycle, authorization, delivery, and verification are separately typed dimensions. They never substitute for a task verdict.

## 5. Business requirements

P0 means required for the MVP. P1 means a designed extension or optional pilot path. Product requirements trace to these IDs.

| ID and purpose | Priority; accountable actor | Inputs | Required output | Failure behavior | Business acceptance |
| --- | --- | --- | --- | --- | --- |
| BR01 — Define the requested value | P0; buyer/product owner | Objective, population, intended use, task and units | Agreed task brief and permitted claim | Defer ambiguous objectives | Every pilot fixes one objective, output grain, universe and reviewable output before testing. |
| BR02 — Accept extensible inputs | P0; data steward | Source contract, registered types, sample and snapshot | Confirmed source profile and lineage | Quarantine unknown semantics | ACR, web and URL references conform without provider branches; novel primitives or transforms receive explicit engineering scope. |
| BR03 — Route by task | P0; analyst/reviewer | Brief, profile, quality and coverage reports | Per-task verdict, evidence and next actions | Use PROVISIONAL for missing evidence; BLOCKED for known violations | Decisions use the shared vocabulary and do not reject valid alternate uses by default. |
| BR04 — Respect where computation and outputs are permitted | P0; execution/policy owner | Execution location, allowed operations, export rules, aggregation thresholds | Feasible run and output plan | Block forbidden computation or export | A restricted environment can block row-level export while allowing permitted internal computation and qualifying aggregates; each operation is routed separately and enforcement is service-side. |
| BR05 — Make claims match evidence | P0; scientist/reviewer | Source evidence, model results and holdouts | Typed evidence card with limits | Abstain or limit the claim | Affinity, probability and incremental effect remain distinct; unsupported outcome probability cannot be released. |
| BR06 — Use bounded agent assistance | P0; analyst | Sanitized reports, allowlisted tools and budgets | Recorded mapping, diagnosis and experiment proposals | Escalate unsupported inference or exhausted budget | Agents cannot invent observations, embed opaque keys, change permissions, or evade deterministic checks. |
| BR07 — Prepare a controlled release | P0; reviewer/export operator | Membership or contextual product, evidence, rights and destination | Immutable reviewed manifest; receipt when delivered | Recheck revocation and reconcile uncertain delivery | Authorization binds exact versions, destination and purpose; exchange mappings disclose verification status and unsupported fields. |
| BR08 — Add downstream evidence where feasible | P1; measurement owner | Exact release, compatible outcomes, assignment/exposure and coverage | Versioned measured claim | Record missing or immature evidence | Observed association and causal claims remain separate; measurement changes neither the original score type nor its backtest. |
| BR09 — Protect tenant and use rights | P0; rights owner | Tenant identity, permitted uses, retention and withdrawal rules | Enforced scope and affected-artifact trace | Keep unknown entitlement provisional and fail-closed | Joins, training, exports and retained learning stay within rights; deletion progress records actual receipts and limits. |
| BR10 — Make work replayable | P0; operations owner | Immutable inputs, plans, versions and job records | Auditable run and release history | Stop silent mutation or unverifiable replay | A reviewer can reconstruct inputs, cutoffs, transformations, decisions and costs from versioned references. |
| BR11 — Prove agent and product value independently | P0; evaluation owner | Locked routing cases, analyst/rules baselines and model comparisons | Separate correctness, utility and effort results | Report failed and not-run checks honestly | Reject-all routing cannot pass; synthetic behavior tests do not establish commercial predictive value. |
| BR12 — Expose commercial contribution | P0; commercial/finance owner | Measured usage and contracted cost parameters | Cost per run, release and customer contribution | Flag unknown costs | Software, data, review and destination economics are visible without invented prices or guarantees. |

## 6. Business measures

Set baseline-relative targets before opening the locked test. Targets remain decisions until real pilot volume, cost and evidence are known.

| Measure | Definition and practical limit |
| --- | --- |
| Routing quality | Verdict/next-action accuracy, macro F1, critical false-safe rate, false-block rate and unnecessary deferral; report counts and uncertainty by task and source. |
| Analyst effort | Active analyst minutes per completed comparable task, including review and remediation; compare against a competent reusable workflow. |
| Task utility | Improvement over the declared baseline at equal population, reach and evidence constraints; affinity retrieval and labeled prediction use task-specific metrics. |
| Preparation yield | Reviewed prepared outputs / completed eligible runs, at the named output grain; report policy and evidence rejection reasons separately. |
| Delivery readiness | Destination-accepted population / submitted population, when independently confirmed; acceptance or matching is not effectiveness. |
| Downstream evidence coverage | Outcome-observable population / agreed measurement population, with maturity and mapping coverage stated. |
| Cost efficiency | Fully attributed operating cost / completed comparable run and / reviewed release; report volume and exclusions. |

Population reports distinguish input, valid, rights-eligible, joinable, scoreable, selected, submitted, accepted, confirmed matched, delivered and outcome-observable counts. Every denominator names its grain. Combining counts across household, device, content or geographic units is invalid without an approved mapping.

## 7. Commercial model and unit economics

Potential software revenue may be subscription, usage, or enterprise service revenue. Data licensing is a separate commercial relationship and may be excluded, passed through, or contracted by the operator. Buyer-agent discovery is an interface; it does not settle pricing, ownership or royalty terms.

Use the following parameters rather than assumed prices:

- `R_software`: contracted software revenue for the period.
- `R_data`: data revenue recognized by the operator, if any.
- `C_compute`, `C_models`, `C_storage`: processing, model/API and storage costs.
- `C_review`, `C_support`: attributable human review and support costs.
- `C_source`, `C_destination`: source royalties and destination charges.

Contribution equals `R_software + R_data − C_compute − C_models − C_storage − C_review − C_support − C_source − C_destination`. Use consistent treatment of pass-through revenue and costs. Cost per run uses all comparable completed runs, including abstentions and unsuccessful statistical results. Cost per reviewed release uses reviewed releases and states its cost allocation method. For a contracted data CPM model, net data revenue equals billable impressions divided by 1,000, multiplied by the data CPM and contracted net share; source royalties and marketplace fees must not be deducted twice. Customer acquisition and fixed development costs remain separately visible.

No revenue uplift or margin claim is warranted until agreed real-data pilots establish usefulness, buyer acceptance and operating cost. Break-even run volume equals period fixed cost divided by positive contribution per comparable run; no break-even volume exists under that formula when contribution is zero or negative.

## 8. Finite MVP and pilot boundaries

The MVP provides source-profile conformance for ACR observations, web events and URL content; registered canonical primitives; batch intake; task routing; bounded analysis; evidence cards; and reviewed immutable output preparation. It supports a small baseline-based affinity/contextual path. Labeled propensity requires its full evidence gate and may be the chosen pilot only when qualified labels exist. Cohort membership need not carry a score.

The first real pilot uses one objective, one output grain, a fixed eligible universe, immutable snapshots and one reviewable batch output. Select the representation from the supplied contract. Examples are viewing-behavior affinity at a documented unit, web-action propensity with mature labels, or page similarity against a content brief. These illustrate different inputs and tasks, not three required live pilots.

Multiple sources are optional. No new identity graph, unrestricted cross-grain join, real-time bidding, autonomous spend, universal connector, production cloud deployment, or general causal-response service is required. Standards adapters are versioned boundaries; verified production activation is a later integration decision. Aggregate-only environments may make an aggregate cohort or report the pilot output.

## 9. Assumptions, decisions and business acceptance

Assume a tenant-controlled workspace, a named steward, permitted sample data, and a reviewer for the pilot. None establishes rights by itself. Windows and PowerShell are the Session 3 operating target; portable path handling must use `pathlib`, and no bash-only test runner is assumed.

Decisions still needed are the pilot objective, source contract, actual unit, execution location, allowed output, coverage and label availability, baseline, worthwhile improvement, rights owner and cost parameters. A missing provider specification does not justify guessing an identifier's semantics.

Business acceptance requires all P0 requirements to have traceable verification; no critical contract violation cleared in the must-pass routing suite; a feasible task under the supplied execution/output policy; a reviewable output with an honest evidence level; and measured cost and analyst effort against a baseline. Statistical utility and live delivery remain not-run until exercised on authorized data and integrations. Session 2 must preserve these decisions in the contracts and agent design rather than introduce a second verdict vocabulary.
