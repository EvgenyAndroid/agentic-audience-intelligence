# Agentic Audience Intelligence Session Handoff

Session 2 | Revision 1 | 14 October 2026

## Completed scope

Session 2 applied the review corrections to the Session 1 documents and produced the data contracts, the agent design and a repository scaffold. The scaffold contains machine-readable schemas, a registry, examples, a router and supporting modules, with tests. No real-data training, agent benchmark with a reasoning model, clean-room integration, activation or downstream measurement was run.

| Path | Purpose | State |
| --- | --- | --- |
| `docs/spec/Claude_Audience_Platform_Mega_Prompt_v3.md` | v3.1: full Session 2 contract list; Session 3 extends this repository | Revised |
| `docs/spec/BRD.md` | Business requirements | Unchanged from Session 1 |
| `docs/spec/PRD.md` | Revision 3: complete traceability, FR30 retired into NFR08, FR37 to FR46 added | Revised |
| `docs/spec/DATA_CONTRACTS.md` | Dialect, conventions, catalog, units, policies, routing, AdCP mapping, VAC/GTS reuse, versioning | Session 2 |
| `docs/spec/AGENT_DESIGN.md` | Roles, authority, context limits, gateway, state machines, failure handling, benchmark design | Session 2 |
| `docs/adr/` | Four architecture decision records | Session 2 |
| `schemas/v1/` | 33 contract kinds plus shared definitions (JSON Schema 2020-12) | Validated |
| `registry/`, `examples/`, `fixtures/routing/` | Types, reason codes, reference profiles, fixture policies, valid and invalid examples, development routing suite | Validated |
| `src/aip/`, `tests/` | Scaffold implementation and 195 tests | Passing on Linux |
| `third_party/adcp/` | AdCP 3.1.20 schemas pinned at commit `d033baef`, hash-locked | Vendored unmodified |
| `scripts/`, `.github/workflows/ci.yml` | PowerShell automation and Windows CI | Written; not yet run on Windows |

## Binding decisions

All Session 1 binding decisions remain in force. Session 2 adds:

| Topic | Decision Session 3 must preserve |
| --- | --- |
| Normative contracts | JSON Schema 2020-12 files are the source of truth; code validates against them instead of re-declaring them (ADR 0001) |
| Verdict authority | Only the router issues `task_decision`. `agent_proposal` is advisory. Facts and prerequisites cannot name an agent as their authority (FR38, ADR 0002) |
| Decision validity | `valid_until` is the earliest of the configured maximum validity and the bound policies' effective ends. A policy version change lapses the decision (FR39) |
| Quarantine intake | Intake, profiling, semantic mapping and type registration may run on quarantined sources when an execution policy permits them. All other operations stay PROVISIONAL with `unregistered_source_profile` (FR40) |
| Reason codes | One registry. Each code has one dimension, task-decision codes declare their effect, and legacy names are aliases (FR41) |
| Usage and cost | `usage_cost_record` per job, task, run or release. Cost per comparable run attributes all costs in the class to completed runs, including abstentions and no-signal runs (FR37) |
| Monitoring | P1; reports propose reassessment or refresh and never act alone (FR42) |
| Policy composition | Every source must permit; prohibition wins; silence is missing; contradiction within a source blocks; aggregation composes most-restrictively (ADR 0003) |
| Exchange | AdCP 3.1.20 at `d033baef`. Use `signal_ref` with scope `signal_source`. Emit `modeling` only when seed source, jurisdictions and AI Act class are declared. `data_sources` are declared per profile. Aggregates, associations and experimental effects are not exchanged as audience signals |
| Representation | VAC field names reused. `pseudo-v1` vectors are nonsemantic and serve exchange conformance only. Direct comparison needs full descriptor equality; a projector needs held-out alignment evidence |
| Platform defaults | None for decision validity, thresholds, coverage, prototype counts, budgets, model identifiers or AdCP configuration |
| Unit mappings | A mapping definition never establishes links; a bound relationship snapshot does. An activation-only mapping cannot build features (FR43) |
| Model registration | Registration establishes identity and declared requirements, not validation. Endpoint models run only as `remote_inference`, with payload transfer checked as egress (FR44, FR45) |
| Recommendations | Deterministic; four sections; no claim-strength ladder; unknown cost is unknown; the requested task is never replaced (FR46) |
| Task-level policies | Tighten only. They can prohibit or restrict, never grant or add a requirement |
| Tooling | Python 3.11+, `pathlib`, PowerShell scripts, Windows CI, vendored files excluded from line-ending conversion (ADR 0004) |

## Verification boundary

Executed in the Linux authoring sandbox (details in `reports/session2/README.md`):

- 34 of 34 schemas meta-validate.
- 76 valid documents pass, and 54 invalid cases fail at the expected layer, keyword and path.
- 195 of 195 tests pass. They cover PRD traceability, router golden decisions, policy composition, the gateway, release rechecks, state machines, costs, baselines, and AdCP output against the pinned schemas.
- ruff, ruff format and mypy are clean.
- The rules router scores 11 of 11 on the development routing suite. This passes by construction and shows harness wiring only. Reject-all and approve-all baselines fail as intended.

Not run:

- Windows execution and CI.
- Agent evaluation with a reasoning model, hidden-oracle isolation, the locked suite and the analyst comparator.
- Real-data utility and calibration.
- Clean-room enforcement.
- Live AdCP destinations, governance context and pricing.
- Deletion propagation, numerical replay on real data and performance targets.

## Inputs for Session 3

Work inside this repository. Attach or read the v3.1 prompt, BRD, PRD Revision 3, DATA_CONTRACTS.md, AGENT_DESIGN.md and this handoff.

1. Run `.\scripts\check-all.ps1` on Windows. Record passed, failed and not-run results under `reports/`, and fix platform issues.
2. Produce MODELING_AND_EVALUATION.md, MVP_BACKLOG.md and PILOT_PROOF_PLAN.md with requirement traceability.
3. Build the locked routing suite with held-out defect combinations, an isolation harness that keeps `oracle/` inaccessible, and the analyst-notebook comparator. Run agents through `ReasoningModel` only when credentials are authorized.
4. Add statistical evaluation assets on synthetic fixtures, labeled as behavior tests: held-out seed retrieval, propensity ranking at reach, reliability and uncertainty.
5. Extend fixtures for revoked data, tenant isolation, injected content, budget exhaustion, and duplicate or uncertain delivery where they are not yet covered.
6. Keep exchange conformance, alignment GTS, routing correctness, statistical utility, destination readiness and downstream results in separate sections, each marked passed, failed or not run.

## Open items found in Session 2

- RESOLVED (FR43): unit mappings and relationship snapshots are defined; see DATA_CONTRACTS section 7. Original note: no unit-mapping contract existed, so `task.units.mapping_refs` could not be verified. A unit mismatch is BLOCKED `grain_incompatible` when the type registry declares no relationship between the types, and PROVISIONAL `missing_unit_mapping` otherwise, whether or not a mapping ref is cited. Session 2 must define the mapping definition and the bound relationship snapshot (effective and availability times, corrections, revocation, cardinality, ambiguity and unmatched handling, approvals) before mapped-grain tasks can be ELIGIBLE.
- Platform-wide policies: until an explicit platform scope exists, represent them as tenant-bound policy instances that reference the authoritative platform template and version. `tenant_id` stays required; mandatory platform exclusions cannot be relaxed by tenant policy.
- RESOLVED: task-level policies only tighten execution, output and aggregation checks (DATA_CONTRACTS section 6, rule 9).
- Relationship availability is checked against decision time; availability at each prediction cutoff stays a `P-FEATURE-TIMING` fact until the feature service computes it.
- The recommender orders by known cost only when `usage_cost_record` data is supplied per candidate; no cost data means ties, by design.
- `remote_inference` is defined and routed, but no endpoint client exists. Recipient terms are a reviewer fact, not an enforced contract.
- The evidence format for platform-enforced execution and output policies in real clean rooms.
- AdCP `data_sources`, signal type, training jurisdictions and AI Act class for each actual source profile.
- Whether cross-party exchange needs signed canonical hashes (RFC 8785 JCS) rather than the platform's sorted-key hashing.
- The tenant's maximum decision validity.
- The existing `adcp-signals-adaptor` publishes `pseudo-v1` taxonomy vectors. Semantic phases need Golden Test Set evidence before any similarity use.

## Decisions still needed for a real pilot

1. Business objective and requested artifact.
2. Actual source contract, profile versions, unit semantics and eligible universe.
3. Allowed execution location, operations, output rules and authoritative policies.
4. Seed, content brief or qualified outcome observations, with coverage and times.
5. Baseline, minimum worthwhile improvement, statistical uncertainty and budget limits.
6. Release reviewer and destination if any, and a compatible measurement design if chosen.

## Next session command

Run Session 3 only in Claude Code, inside this repository. Use the v3.1 brief, BRD, PRD Revision 3, DATA_CONTRACTS.md, AGENT_DESIGN.md and this handoff. First run `.\scripts\check-all.ps1` and record the results. Then produce MODELING_AND_EVALUATION.md, MVP_BACKLOG.md and PILOT_PROOF_PLAN.md, build the locked routing suite and analyst comparator, update HANDOFF.md, and stop before production deployment.
