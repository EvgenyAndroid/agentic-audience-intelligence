# Claude prompt for the Agentic Audience Intelligence Platform v3

Version 3.1 | Revised 14 October 2026 after Session 2 review

## How to use this prompt

Attach this file to each session and paste the relevant session instruction below. Attach the files produced by earlier sessions. Run only the selected session. If no session is selected, run Session 1 and stop after its handoff.

The platform is provider agnostic. ACR, web events, and URL content are reference inputs. They are not a closed list, a fixed modeling grain, or a required customer profile.

| Session | Environment | Main outputs |
| --- | --- | --- |
| 1 Business and product | Claude | BRD.md and PRD.md |
| 2 Contracts and agents | Claude or Claude Code | DATA_CONTRACTS.md, AGENT_DESIGN.md, and complete JSON schemas |
| 3 Evaluation and pilot | Claude Code | MODELING_AND_EVALUATION.md, MVP_BACKLOG.md, PILOT_PROOF_PLAN.md, validated schemas, fixtures, and test reports |

Each session updates a short HANDOFF.md with completed files, decisions, unresolved dependencies, and inputs for the next session. Keep decisions and assumptions in the relevant documents; do not create five separate registers. Do not generate all seven reports in one pass.

## Shared brief for every session

You are designing a general audience intelligence platform for advertising data owners, brokers, marketplace teams, agencies, and brands. It accepts permitted data with attributes of unknown quality, identifies supported modeling tasks, and returns scores, cohorts, contextual outputs, and evidence that a buyer can review.

Inputs may include ACR viewing observations, web events, URL or page content, transactions, survey responses, CRM attributes, geographic aggregates, or other supplied signals. Records may carry household, device, browser, account, person, session, network, content, geographic, or custom keys. Source family, identifier type, and modeling grain are separate concepts.

Agents interpret schemas and objectives, map meaning, propose valid features and experiments, assess evidence, and explain results. Deterministic services enforce contracts and permissions, join data, build features, train models, compute metrics, score populations, and prepare releases. The reasoning model is replaceable.

The product supports semantic similarity, seed affinity, behavioral affinity, labeled outcome propensity, and exploratory cohorts. Causal response modeling is a separate later capability. Downstream measurement is an optional evidence path when compatible activation, exposure, and outcome data exist.

Use the supplied PRD as a starting point, not as authority for a conflicting scope choice. This v3 brief supersedes fixed device, household, provider, and source-family defaults. Preserve the scientific and rights rules. Do not invent customer commitments, data quality, source permissions, performance, prices, dates, or connector capabilities.

## Shared task verdict vocabulary

Every exact requested task receives one verdict: ELIGIBLE, PROVISIONAL, or BLOCKED. A task identifies its operation, objective, score or artifact type, modeling and output units, execution location, requested destination, and applicable input and policy versions.

- ELIGIBLE means all prerequisites for that operation, execution context, and requested outputs are established. It permits the operation under those controls; it does not promise model quality or authorize a later release.
- PROVISIONAL means required evidence, permission, or capability verification is missing. The exact task cannot proceed until those prerequisites are resolved. Return specific reasons and evidence requests. Separately permitted diagnostics can have their own ELIGIBLE task decision.
- BLOCKED means a documented restriction or demonstrated violation forbids the exact task. Return reasons and a repair or alternative task proposal; changing the task requires a fresh decision.

A dataset's fitness is its set of per-task verdicts. Do not introduce Ready, Ready with limitations, Exploratory only, or a second fitness status field. exploratory is a label on the output claim, never a routing verdict. Reason codes explain verdicts; they do not replace them. Execution lifecycle states remain separately typed and cannot be used as fitness verdicts.

Building or validating a new outcome-probability model without qualified labels is PROVISIONAL with reason unsupported_outcome_probability. No statistical training or probability release proceeds under that task until the missing evidence is resolved. Valid affinity or contextual work is a separate task that can be ELIGIBLE and carry an exploratory claim. Scoring with an existing validated model does not require future outcome labels on the candidate population; its own feature, population, policy, and model-validity requirements still apply.

Apply this vocabulary in Session 1's PRD, Session 2's schemas, all fixture labels, user-facing reports, and every tool contract. Rewrite the inherited FR10 explicitly to these semantics rather than retaining exploratory-or-blocked wording.

## Evidence rules

1. Separate semantic similarity, seed affinity, behavioral affinity, probability, and incremental effect. Each score has a distinct type, scale, grain, purpose, and validation status.
2. Cosine similarity is a normalized dot product in a particular vector space. Meaning comes from the representation. A score of 0.85 does not imply an 85 percent chance of buying.
3. An identifier is a key. Never embed opaque cookies, IDFAs, IP strings, or arbitrary IDs to establish similarity or identity equivalence.
4. A seed plus an unlabeled universe supports affinity. It does not establish calibrated purchase probabilities. Unobserved entities are not automatically negatives.
5. Training or validating propensity requires a named event, prediction cutoff, outcome horizon, eligible population, mature labels, observation coverage, and an evaluation plan. Valid negatives require complete observation windows. Inference uses an existing validated model and suitable pre-cutoff features under its population and policy requirements; it does not require future labels on scored candidates.
6. Incremental response requires treatment data and a credible causal design. Attributed conversions and propensity lift cannot establish causal ad impact.
7. Use the versioned type registry to declare what each identifier or unit represents. All current and future types retain their declared grain, namespace, and limits. For example, a postal code is an area, a URL is a content locator, an IP is a time-bound network observation, and browser, device, household, and person units remain distinct. Unknown types are quarantined until their meaning is established. Registry extension cannot turn a key into a semantic feature or waive evidence rule 3.
8. Shared IP, shared ZIP, or semantic closeness cannot establish that two IDs represent the same entity. Cross-source joins require permitted relationships with evidence and validity windows.
9. Missing features remain unknown unless a documented statistical transform applies. An LLM cannot invent observed facts or sensitive traits.
10. A clean schema does not prove predictive utility. Measure utility against a relevant holdout and baseline. A failed or exploratory result is a valid product outcome.
11. Separate source accuracy, identity-link evidence, missing-feature coverage, semantic mapping support, and model uncertainty. Do not compress them into one confidence score.
12. Synthetic fixtures test software behavior. Synthetic performance is not market evidence.

An ACR dataset is a source of observations. Its key may represent a screen, device, household, or another documented unit. Confirm that meaning from its contract. Do not infer it from the letters ACR, the file name, or a vendor convention. Apply the same rule to web and other sources.

## Source profiles and canonical data

Use a versioned adapter and source-profile registry. Core services operate on entities, observations, events, content items, relationships, labels, and eligibility references. Source profiles describe how source records map to these primitives.

Each profile declares source and schema versions, observation grain, key namespace, signal definitions, value types and units, collection method, event time, availability time, delivery lag, observation coverage, missingness semantics, content resolution, rights, quality checks, optional supplied relationships, known limits, execution_policy_ref, and output_policy_ref. A dataset manifest binds a profile version to an immutable input snapshot.

| Reference input | Example observations | Supported outputs when evidence permits |
| --- | --- | --- |
| ACR viewing | Time-stamped viewing events and content metadata at the supplied key's declared grain | Behavioral affinity, cohorts, labeled tune-in forecasts, or content similarity |
| Web events | Visits, actions, sessions, exposures, and conversions at declared grains | Seed or behavior affinity, labeled propensity, or exploratory cohorts |
| URL content | Permitted page text, topics, content metadata, and optional observation links | Contextual retrieval, content cohorts, or permitted features for linked observations |

These are conformance examples. Add future sources through adapters, approved mappings, and registered transforms. A new profile that uses already supported primitives should not require source-specific branches in the core workflow. New modalities or transforms may require additional adapter or service work and their own tests. Do not promise that every new dataset can be supported through configuration alone.

Rewrite the inherited FR26 explicitly: configuration and approved mappings can onboard sources using already supported transport, primitive, policy-enforcement, and transformation capabilities. New protocols, execution integrations, policy controls, or transforms require versioned extensions and conformance tests. Do not carry over a universal configuration-only guarantee.

Unregistered inputs may be staged and profiled in quarantine under separately eligible intake tasks. Agents can propose mappings. They cannot invent missing units, timestamps, source rights, or entity relationships. Steward confirmation validates the profile's semantics and mappings; each processing task still requires an ELIGIBLE decision under its evidence, execution, and output contract.

A run may reference one or several profiles. It explicitly declares the observation grain of each input, modeling unit, output grain, activation unit if any, and measurement unit if any. Combining inputs requires approved relationships or documented aggregation rules. Source type never determines the output unit implicitly.

Content from TV, pages, apps, or ads can be represented in a shared semantic space only when the encoder and task support those inputs and cross-source tests pass. A matching embedding version is necessary for direct comparison but is not sufficient evidence of useful cross-media similarity. Content resemblance alone cannot establish shared audiences or behavioral equivalence.

## Execution location and output restrictions

The source profile references authoritative execution and output policies. They declare allowed environments and residency, required capabilities, allowed raw-data access and joins, permitted operations, artifact types and output grains, destinations, row-level egress rules, aggregation thresholds with their counted units, approved dimensions, suppression, and query or privacy budgets where applicable. Include policy authority, version, effective period, and enforcement method. Missing rules are unknown, not permissive defaults.

Every run binds its selected execution_location_ref, execution_policy_refs, output_policy_refs, requested_outputs, destinations, aggregation_rule_refs, and applicable budget_refs. Validate all contributing sources' restrictions and retain them through derived features, models, embeddings, logs, reports, and exports. One permissive source cannot override a restrictive source.

Internal computation, row-level export, cohort-definition release, and aggregate measurement are distinct tasks. If a clean room permits internal scoring but forbids row-level egress, route the row-level export BLOCKED with reason forbidden_row_level_egress. An aggregate release can be ELIGIBLE when its actual permissions, thresholds, and budgets are established. Missing policy details make the dependent task PROVISIONAL and prevent execution. Do not silently replace requested row-level output with aggregates.

Enforce thresholds on the required distinct units and apply the full supplied policy, including repeated-query controls and cumulative budgets. Do not invent a minimum cohort size or assume a single threshold establishes permission. Aggregate-only outputs need their own evidence card and restrictions; they do not imply that audience membership IDs can be activated outside the boundary.

## Shared architecture and release requirements

Keep namespaces, source lineage, grain, units, and observed versus reported versus inferred status throughout processing. Preserve missing, zero, false, and unobserved as separate states. Postal codes remain strings with country qualifiers.

Features and relationship evidence must be available by the prediction cutoff, in addition to having valid event times and relationship intervals. Version backfills and corrections. A later-discovered identity relationship cannot enter an earlier backtest.

Raw identifiers remain in tenant-controlled storage. Agents use sanitized schemas, approved descriptions, aggregate reports, and artifact references. External embeddings use only permitted sanitized content. The export service resolves activation identifiers. Hashing alone does not establish anonymity, rights, or destination compatibility.

Use one durable orchestrator with bounded roles for intake, fitness, meaning mapping, join and feature planning, experiments, evaluation, audience preparation, and monitoring. These are roles, not a requirement to deploy eight separate LLM services.

Keep run execution separate from audience lifecycle. Persist plans, tool responses, metrics, and artifact versions. A statistically unsupported result can be a successfully completed run. Review and release are separate from a model's recommendation.

Tools use authenticated actor context, server-verified tenant scope, versioned artifact references, policy context, budgets, and idempotency keys. Long jobs return job references. Strict schemas require service-side semantic and policy checks. Imported text cannot change permissions, invoke unrestricted SQL or shell access, or authorize publication.

Define separate score and cohort-membership contracts. A score carries its type, scale, grain, namespace, model version, feature snapshot, prediction_cutoff, scored_at, expiry, inclusion_disposition, and reasons. included, excluded and abstained describe record disposition, not task fitness. Propensity also requires outcome and horizon. Cohorts need no forced numeric score. Abstention is a typed result rather than a disguised zero.

Prepare immutable membership and a release manifest. Approval binds their checksum, destination, purpose, and policy versions. Commit rechecks suppression, expiry, and revocation. A changed membership requires a new prepared version and the applicable review. Unknown remote delivery status requires reconciliation before retry.

Track input, valid, rights-eligible, joinable, scoreable, selected, submitted, accepted, matched when confirmed, delivered, and outcome-observable populations separately. Every count names its grain and denominator.

Source contracts cover collection, joining, derivative modeling, licensing, redistribution, retention, and activation as applicable. Default scope excludes sensitive trait inference, children, precise-location targeting, and sensitive audiences. Cross-client reuse of models, features, embeddings, segments, or retained learning requires explicit rights. Trace deletion and source withdrawal into affected artifacts and model remediation. Downstream deletion has requested, acknowledged, completed, failed, or unsupported status with receipts; a local flag cannot retrieve a delivered file.

## Buyer agent exchange and vector alignment

Keep the canonical platform independent of an exchange protocol. Add versioned boundary adapters for AdCP and the relevant Agentic Audiences profile so buyer agents can discover reviewed outputs and request authorized activation.

| Platform artifact | Exchange surface | Constraint |
| --- | --- | --- |
| Audience or contextual product | AdCP get_signals discovery | Preserve stable reference, output meaning, grain, eligibility, and evidence links |
| Evidence card and manifest | Signal definition and supported disclosure fields or extension references | Keep score type, outcome horizon, denominators, limitations, expiry, and source versions visible |
| Reviewed activation request | AdCP activate_signal | Bind the exact released version, destination, entitlement, price selection, authorization, and retry key |
| Activation receipt | Deployment and asynchronous status surfaces | Delivery status does not establish audience effectiveness |
| Permitted vector representation | Agentic Audiences or a documented bridge profile | Validate representation compatibility and permitted use before comparison or exchange |
| Downstream outcome evidence | Versioned measurement artifact and supported reporting or feedback surface | Bind the exact release and retain observational versus causal claim type |

Derive exact wire fields from a pinned official schema. Keep protocol version, adapter version, and namespaced extension version separate. Do not copy legacy examples into a newer schema or invent mandatory fields. Unsupported evidence fields remain referenced artifacts or declared extensions. A mock activation handle cannot be reported as a destination's confirmed acceptance.

Reuse the existing Vector Alignment Contract and Golden Test Set design where verified. Each exchanged vector declares model and revision, transformation version, embedding space, dimensions, encoding, normalization, metric, represented grain, role, time validity, permitted uses, and provenance. Matching dimensions alone does not establish compatibility.

Direct comparison requires compatible spaces. A projector requires its own versioned held-out alignment evidence. If neither route is valid, use documented structured criteria or segment references, or abstain. Simulated projectors and nonsemantic pseudo-vectors cannot qualify as production alignment.

Maintain three separate test suites: exchange/schema conformance, representation alignment, and agent decision quality. Passing one does not imply passing the others or proving predictive value. Treat the existing adapter's VAC, GTS, and namespaced extensions as an implementation profile to inspect and reuse, not as automatically mandated AdCP core fields.

## Session 1 instruction

Run Session 1 only. Act as product lead and data scientist. Read the shared brief, evidence rules, and any attached PRD. Produce BRD.md and PRD.md, followed by HANDOFF.md. Do not generate schemas, implementation code, the backlog, or the other reports in this session.

The BRD defines the customer categories, buying and operating roles, concrete problems, value, commercial model, business measures, and decisions needed. Use no named provider default. Separate software revenue from data licensing; include source royalties, destination fees, review cost, and contribution formulas with parameters rather than invented prices.

The PRD defines the source-profile architecture, supported-task matrix, workflows, role boundaries, functional and nonfunctional requirements, release rules, buyer-agent exchange, direct agent evaluation, and optional downstream measurement. Define observation, modeling, output, activation, and measurement units separately. Use the shared task verdicts from this brief. Rewrite FR10 and FR26 explicitly. Include execution and output restrictions in the profile and run requirements, including a clean-room example with different verdicts for row export and aggregate release.

Keep the first real pilot small: one named objective, one output grain, a fixed eligible universe, immutable snapshots, batch execution, and one reviewable output. Choose the grain and representation from the supplied source contract. A seed task needs a seed and compatible candidate pool; a contextual task needs a content brief or reference; a new propensity training/validation task needs qualified labels. Existing-model inference follows the shared stage-specific requirements. Do not force all inputs into numeric/categorical seed affinity.

The MVP needs reference profile conformance for ACR, web events, and URL content. It does not need every modeling method, every possible source combination, a new identity graph, real-time bidding, or autonomous media spend.

For each requirement include ID, purpose, priority, actor, inputs, outputs, failure behavior, and acceptance criteria. Use one compact traceability table from business need to product requirement and verification. Put a concise assumptions and decisions section inside these two reports.

Use one short example per reference source to show how the objective and unit change. Put detailed fixture and modeling design into the later sessions. Treat stronger model quality, better agent routing, lower analyst effort, activation readiness, and downstream results as distinct proof obligations.

Ask only questions that materially affect the pilot. Continue with explicit assumptions for nonblocking choices. End with the decisions and files Session 2 needs, then stop. Do not describe this specification as a validated product.

## Session 2 instruction

Run Session 2 only. Read the v3 brief and Session 1 files. Act as data architect and agent engineer. Produce DATA_CONTRACTS.md, AGENT_DESIGN.md, complete machine-readable JSON schema files, and an updated HANDOFF.md. Do not run model experiments or implement the product in this session.

Define the minimum coherent contract set: source profile, type registry, execution policy, output policy, reason-code registry, dataset manifest, entity, content item, observation/event, relationship, outcome label, objective, task, run, feature plan, evidence bundle, advisory agent proposal, authoritative task decision, asynchronous job, usage and cost record, representation descriptor, alignment test set, routing case and oracle, monitoring report (P1), score, cohort membership, evidence card, release manifest, authorization, export receipt, and measurement feedback. Share definitions through schema references instead of duplicating them. State the JSON Schema dialect and validator compatibility.

Separate transport adapters from semantic source profiles. Each reference profile maps source observations into the canonical contracts and documents what is missing. Extension types must have declared semantics, namespace, validation, and steward confirmation; a new source must not silently introduce a new grain.

Use required and nullable fields explicitly, finite numeric values, timestamp formats, enums, and discriminated task and score types. Reject unknown fields unless the schema defines an extension slot. A seed-affinity object cannot carry an outcome probability. A propensity object requires outcome and horizon. Abstained records require reasons. Include positive and negative examples.

Define role inputs, tools, outputs, rights, memory limits, budgets, failure handling, and escalation. Specify allowed state transitions, guards, actors, required artifacts, retries, cancellation, and reconciliation. Separate statistical verdict from execution status.

Agent routing implements the shared task verdict vocabulary verbatim. Return the exact operation, output contract, grain, execution context, ELIGIBLE, PROVISIONAL, or BLOCKED, plus reasons, evidence references, and required next actions. Dataset fitness is the set of these decisions; exploratory is a claim label. PROVISIONAL does not authorize the unresolved task. Keep unsupported_outcome_probability as a reason on the no-label new-model decision, not a fourth verdict. Define execution and output-policy references on source profiles and runs.

Produce an exact AdCP mapping against a pinned schema and a representation compatibility contract that can reuse VAC/GTS concepts. Identify standard fields, implementation extensions, fallback behavior, and unsupported mappings. Add interface conformance requirements; do not infer production readiness from a demo README.

Measurement feedback binds release ID and checksum, model/feature versions, output and measurement units, approved mapping versions, campaign/experiment context, assignment and exposure, outcome definition, observation windows, availability, maturity, population coverage, estimator, uncertainty, and permitted future training use.

If file creation is available, save complete schemas and examples as files. Otherwise provide complete labeled file contents for Session 3 to materialize. Do not use ellipses or unfinished schema placeholders. Verify reference resolution and consistency with Session 1. Record necessary changes rather than silently redefining the product.

End with the complete file manifest and dependencies for Session 3, then stop.

## Session 3 instruction

Run Session 3 only in Claude Code. Work in the repository scaffold produced by Session 2 (README.md describes its layout) and extend it rather than regenerating it. Read the v3 brief and all earlier outputs. Act as data scientist and evaluation engineer. Work in the designated project workspace. Produce MODELING_AND_EVALUATION.md, MVP_BACKLOG.md, PILOT_PROOF_PLAN.md, executable contract validation and fixture tests, their reports, and an updated HANDOFF.md.

The target development environment is Windows. Use PowerShell syntax for commands and scripts, Python pathlib for paths, and test runners that work on Windows. Do not depend on Bash, Unix-only commands, WSL, or shell-specific path expansion. Describe remote execution separately; the local Windows runner must respect the selected execution boundary and cannot move restricted data onto the laptop.

Materialize the exact Session 2 schemas and examples as actual files if they are not already present. Validate schemas and references with a suitable library. Valid examples must pass; intentionally invalid examples must fail for the expected reason. Record validator and schema versions. Fix inconsistencies explicitly and update the affected source document.

This session builds evaluation assets, not the full production platform. Do not add a frontend, cloud deployment, live destination connector, or general agent framework unless I separately request implementation. Do not use real data, credentials, or activation endpoints without a supplied and authorized contract.

### Modeling plan

Define eligibility, representation, and evaluation per task. Use approved text embeddings for content and meaning. Keep numerical, categorical, behavior, temporal, and geographic features distinct. A hybrid rank needs compatible scales and a declared weighting and missing-channel method.

Start with simple rules and appropriate affinity baselines. Compare a single seed prototype with multiple prototypes where useful. For labeled propensity, compare logistic regression with a bounded gradient-boosted candidate. Richer models require an observed need and justified data, compute, licensing, and deployment fit.

Match validation to deployment: new entities, future periods, or both. Keep verified aliases and related observations from leaking across relevant partitions. Fit transformations on training data. Separate model selection, calibration, and a locked final test. Respect label maturity, class sampling, and observation coverage.

Use held-out seed retrieval as affinity evidence. For propensity report ranking at operational reach, PR-AUC or average precision, source and coverage slices, reliability curves, Brier score, log loss, and group-aware uncertainty. Brier and log loss do not isolate calibration. Compare candidates at the same reach, population, horizon, and evidence constraints. Model attributions describe association rather than causation.

### Agent routing benchmark

Create versioned labeled fixtures across ACR, web, URL, and source-neutral canonical cases. Give agents neutral case IDs and only the data, reports, and tools they would legitimately receive. Keep answer keys, diagnostic filenames, and generator metadata out of their context.

| Fixture | Condition | Expected decision |
| --- | --- | --- |
| Availability leakage | Event predates cutoff; availability follows it | Block the affected feature plan and rebuild it |
| Mixed grains | Incompatible seed/candidate units without a valid transform | Block the affected comparison and request a valid representation or mapping |
| Provider artifact | Independent source holdout and ablation expose spurious apparent lift | Block model promotion and require remediation |
| Good labeled data | Mature outcomes, correct times and units, valid splits | Allow evaluation and remaining release checks |
| Good unlabeled affinity or context | Usable seed/content evidence without outcome labels | Allow evaluation for the supported task; a propensity request is PROVISIONAL with specific label requirements |
| Missing evidence | Availability, coverage, or relationship evidence cannot be established | Return provisional with precise evidence requests |
| Aggregate-only policy | The same source permits validated aggregates but explicitly forbids row-level egress | Row-level export is BLOCKED; a qualifying aggregate release is ELIGIBLE |
| Unverified policy | Execution or output permissions cannot be established | The dependent task is PROVISIONAL and cannot proceed |

Include repaired counterparts and clean controls so rejecting every dataset cannot pass. Statistical traps need independently computed, reproducible evidence. Do not expect the agent to know facts hidden from its permitted inputs. Evaluate the same dataset under different requested tasks where appropriate.

Use independent deterministic checks for schema, time, grain, joins, splits, and permissions; source-held-out tests and ablations support statistical verdicts. Fixture oracles must not be the evaluated LLM's own answers. A versioned case manifest fixes requested task, grain, expected state, acceptable next actions, mandatory reasons, permitted evidence, and oracle version before testing.

Separate development fixtures from a locked test suite with held-out corruption patterns, sources, and defect combinations. Run evaluated agents and comparators in isolated workspaces with allowlisted tools. Mount only neutral inputs and permitted reports. Make oracle files, generators, expected verdicts, and locked-test metadata inaccessible. Use fresh agent context and record the enforced access boundary. Store case-level results and evidence references.

Report routing exact-match accuracy for verdict and next action, macro F1, critical false-safe rate, premature clearance of provisional cases, false-block rate, unnecessary deferral, diagnosis completeness, cost, and analyst intervention. Break results down by task, source profile, and grain. Pre-register counts, uncertainty, and baseline-relative targets. Critical contract violations in the must-pass suite cannot be cleared. Zero observed errors is not proof of zero production risk.

Compare against a deterministic rules router and a competent analyst with a reusable notebook, using the same visible evidence and tools. Measure correctness before time savings. A faster agent with worse correctness is not an improvement.

### Separate proof of semantics and automation

Retain the four-way comparison: manual rules, conventional ML, ML with semantic features, and the agent-guided workflow with the same permitted model choices. This tests representation and workflow value under controlled conditions. The direct routing benchmark separately tests diagnosis and supported-task selection.

Keep exchange conformance, vector alignment GTS, routing correctness, statistical utility, destination acceptance, and downstream results in separate labeled sections of MODELING_AND_EVALUATION.md. Give each a passed, failed, or not-run status. Generate machine-readable reports only for checks actually executed. Synthetic fixtures establish behavior only. Without real permitted data or model credentials, record the relevant evaluation as not run rather than fabricating results.

### Downstream measurement option

Bind measurement to an immutable audience or contextual release. Before activation, define outcome, unit, comparison design, exposure/assignment rules, observation window, availability, maturity, and coverage gates.

Reference examples are tune-in from compatible viewing observations, conversions from compatible web or transaction observations, and placement-level outcomes for contextual cohorts. They are examples, not mandatory provider capabilities. Page-level outcomes cannot become proof of individual propensity.

Evidence cards may carry held-out resemblance, offline outcome prediction, observed downstream association, or experimental incrementality. These are separate claims with their own population, dates, denominators, uncertainty, and limits. New observed results supplement the exact release's evidence card; they do not retroactively turn an affinity score into a probability.

An exposed-versus-unexposed comparison is observational unless assignment supports a causal claim. A randomized campaign holdout inside an audience can test campaign impact in that audience. It does not by itself prove better audience selection than a baseline strategy. A targeting-superiority claim needs an appropriate comparison of strategies under comparable delivery conditions.

For randomized studies, use assigned groups as the primary intention-to-treat comparison. Random assignment does not make an actually exposed-versus-unexposed contrast causal. Exposure-based effect estimates require a separately justified causal estimator and stated assumptions.

Missing exposure and outcome observations remain unknown unless the contract establishes complete coverage. Feedback can enter a later eligible training snapshot; it cannot leak into the original model's backtest.

### Finish the pilot and backlog

Write the ordered MVP backlog with requirement traceability, dependencies, verification, and later work. Put build-versus-buy decisions into the relevant epics only where they affect implementation. Parameterize unsupported budgets, timelines, model thresholds, and scale limits.

The pilot plan fixes objective, input profiles, grain, eligible universe, seed or content brief or labels, baselines, measurement options, release rules, and minimum worthwhile improvement before opening the final test. Track model quality, routing correctness, analyst effort, delivery readiness, downstream evidence, and cost separately.

Keep tests proportionate to contracts and high-impact failure modes. Include revoked data, suppression, wrong embedding spaces, zero vectors, invalid labels, injection, tenant isolation, budget exhaustion, and duplicate or uncertain delivery where covered by the specification. Do not claim to have tested production components that were not implemented.

End with passed, failed, and not-run checks; generated artifact paths; unresolved inputs; and the concrete next implementation step. Stop after Session 3's scope.

## Reference sources and verification

Use primary sources and record the exact schema, repository revision, and access date used in the generated specifications. Documentation retrieval is permitted; live activation and media buying are separate authorized operations. If sources are unavailable, mark that mapping as unverified and keep the canonical contracts usable.

- AdCP official protocol and task documentation: https://github.com/adcontextprotocol/adcp and https://docs.adcontextprotocol.org/docs/signals/tasks/get_signals and https://docs.adcontextprotocol.org/docs/signals/tasks/activate_signal
- Agentic Audiences official repository and systems documentation: https://github.com/IABTechLab/agentic-audiences and https://github.com/IABTechLab/agentic-audiences/blob/main/docs/systems-and-models.md
- Existing AdCP/VAC/GTS bridge implementation to inspect for reuse: https://github.com/EvgenyAndroid/adcp-signals-adaptor
- Buyer disclosure reference: https://iabtechlab.com/standards/data-transparency-standard/
- Historical feature availability reference: https://docs.feast.dev/getting-started/concepts/point-in-time-joins
- Leakage and probability calibration references: https://scikit-learn.org/stable/common_pitfalls.html and https://scikit-learn.org/stable/modules/calibration.html

Verify current status and actual interfaces. A proposed specification, namespaced extension, simulation, and production-tested capability are different things. Preserve those labels.

## Start command

Attach this v3 file and paste: Run Session 1 only. Use the shared brief and evidence rules. Revise the BRD and PRD for a provider-agnostic platform with extensible inputs, then produce the handoff and stop.
