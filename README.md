# Agentic Audience Intelligence Platform

A provider-agnostic platform that assesses permitted advertising data, selects defensible tasks, runs bounded modeling workflows, and prepares reviewable audience or contextual outputs. Agents interpret and propose. Deterministic services enforce contracts, compute results and control release.

This repository holds the specification and a working scaffold: normative JSON Schema contracts, a registry, a task router, policy composition, an agent tool gateway, modeling baselines, release controls, an AdCP boundary adapter and an evaluation harness. It is not a validated product. No real data, live integration or model-quality claim has been tested.

## Verification status

| Check | Status | Evidence |
| --- | --- | --- |
| Schema meta-validation (38 files, JSON Schema 2020-12) | Passed (Linux; Windows in CI) | Session 2 record (34 files) in `reports/session2/` |
| Valid examples and registry documents (85) | Passed (Linux; Windows in CI) | Session 2 record (76) in `reports/session2/conformance.json` |
| Invalid cases fail for the stated layer, keyword and path (75) | Passed (Linux; Windows in CI) | Session 2 record (54) in `reports/session2/conformance.json` |
| Unit and contract tests (333) | Passed (Linux and Windows, Python 3.11 and 3.12, locked dependencies) | Session 2 record in `reports/session2/pytest-linux.xml` (195); tests added since in `tests/` |
| Lint (ruff) and type check (mypy, 57 files) | Passed (Linux) | `reports/session2/README.md` |
| AdCP adapter output against pinned AdCP 3.1.20 schemas | Passed (Linux) | `tests/test_representation_and_exchange.py` |
| Rules router on the development routing suite (12 cases) | Passed by construction | Session 2 record (11 cases) in `reports/session2/routing_benchmark_development.json` |
| Windows and PowerShell execution, CI | Passed (GitHub Actions `windows-latest`, Python 3.11 and 3.12) | `.github/workflows/ci.yml` runs `.\scripts\check-all.ps1` on every push |
| Agent routing benchmark with a real model, hidden-oracle isolation | Not run | Session 3 |
| Statistical utility on real data, clean-room enforcement, live delivery | Not run | Requires authorized data and integrations |

## Quickstart (PowerShell)

```powershell
Set-Location agentic-audience-intelligence
.\scripts\bootstrap.ps1 -WithModeling   # creates .venv and installs -e ".[dev,modeling]"
.\.venv\Scripts\Activate.ps1
.\scripts\check-all.ps1                 # lock check, lint, tests, conformance, benchmark
```

If script execution is blocked, allow it for the current session only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

The package locates the repository through `pyproject.toml` and `schemas\`. Use the editable install, or set `$env:AIP_HOME` to the repository root.

## Command line

```powershell
aip schemas
aip validate examples\valid\task
aip conformance --report reports\local\conformance.json
aip route --task examples\valid\task\task_cr_export_rows.json `
          --bundle examples\valid\evidence_bundle\bundle_task_cr_export_rows.json `
          --docs examples\valid --now 2026-10-14T12:00:00Z --ttl-hours 168
aip benchmark --suite fixtures\routing\development --now 2026-10-14T12:00:00Z --ttl-hours 168
```

`--now` and `--ttl-hours` are required because the platform supplies no default decision validity. The values above replay the fixtures, whose policies are effective from 2026-10-01 to 2027-01-01.

## Repository layout

```text
docs/spec/          BRD, PRD (Revision 3), v3.1 prompt, DATA_CONTRACTS, AGENT_DESIGN, HANDOFF
docs/adr/           Architecture decision records
schemas/v1/         Normative JSON Schema 2020-12 contracts (38 files)
registry/           Type registry, reason-code registry, reference profiles, fixture policies
examples/valid/     One or more valid documents per contract kind, including router golden decisions
examples/invalid/   Patch-based invalid cases with expected failure layer, keyword and path
fixtures/routing/   Development routing suite: cases, world documents, separate oracles
src/aip/            Python package (see below)
tests/              pytest suite, including PRD traceability and router golden-output checks
third_party/adcp/   Pinned AdCP 3.1.20 schemas (Apache-2.0), hash-locked
scripts/            PowerShell automation
reports/session2/   Results of checks actually executed in Session 2
demo/               Demonstrator scenarios and build settings (separate from the routing benchmark)
app/                Static demonstrator page and its precomputed bundles (app/data)
```

Package modules:

| Module | Responsibility |
| --- | --- |
| `aip.contracts` | Schema loading and validation, semantic cross-field rules, conformance runner |
| `aip.registry` | Type registry, reason-code registry, document index |
| `aip.policy` | Execution and output policy composition, aggregation release checks |
| `aip.routing` | Prerequisite catalog and matrix, deterministic checks, task router, decision validity |
| `aip.agents` | Roles, tool gateway, reasoning-model interface, advisory proposals |
| `aip.features` | Point-in-time availability checks |
| `aip.modeling` | Seed-affinity baselines with abstention, propensity baselines, evaluation metrics |
| `aip.representation` | Vector compatibility (VAC field names) and Golden Test Set evaluation |
| `aip.release` | Prepare, authorize and commit with rechecks; delivery retry policy |
| `aip.lifecycle` | Job, audience and delivery state machines |
| `aip.costs` | Cost per comparable run, contribution, CPM revenue and break-even |
| `aip.exchange` | AdCP 3.1.20 boundary adapter |
| `aip.monitoring` | Population stability index for post-release drift |
| `aip.recommendation` | Deterministic recommendations over current task decisions, and an admissibility check |
| `aip.demo` | Build-time demonstrator: routes `demo/scenarios` into static bundles for `app/` |
| `aip.workbench` | Audience workbench: eight synthetic datasets, routed, modeled and evaluated on held-out data at build time |
| `aip.evaluation` | Routing benchmark harness and metrics |

## Demonstrator

`app/` has two modes.

**Build an audience** (the workbench, ADR 0005) covers eight generated datasets: B2B accounts, geography, demographic and firmographic, interest and behavioral segments, TV viewing (ACR), web and app events, first-party CRM and page content. For each one you see an assessment of what the data is and what it supports, the router's verdict on every method (look-alike, act-alike, propensity, your registered model, contextual), a recommended method and a recommended model compared on held-out records, and a reach slider that trades audience size against held-out quality, with composition and feature drivers. Export is its own decision: row files download where the policy permits; the clean room only releases an aggregate report with small cells suppressed. Evidence facts (coverage, label counts, sensitive-attribute screening) are computed from the generated data, so the B2B propensity task stays PROVISIONAL with too few labels, and the inferred health attribute never reaches a model.

```powershell
aip workbench-build --out app\data\workbench          # rebuild after changing the engine or the dataset specs
aip workbench-build --out app\data\workbench --check  # floats compared within 2e-3 across platforms
```

**How the router decides** shows the engine's decisions on four synthetic scenarios: an ACR clean room, a web look-alike, URL content and a new source in quarantine. It answers what each dataset can be used for, task by task, with the reasons, what would unlock each task, a deterministic recommendation, synthetic look-alike results with their abstention denominators, and a stored trace.

Nothing runs while a visitor browses. `aip demo-build` routes the scenarios in `demo/scenarios/` through the real router, recommender and baselines, and writes versioned bundles to `app/data/`. Each bundle records its evaluation time (from `demo/build.json`), the engine version and source hash, and the hash of every input. `tests/test_demo.py` fails when the committed bundles differ from a fresh build, so any engine change must ship with rebuilt bundles.

```powershell
aip demo-build --out app\data          # rebuild after changing the engine, contracts or scenarios
aip demo-build --out app\data --check  # what CI checks
python -m http.server --directory app   # preview at http://localhost:8000
```

UI labels name the claim plainly and keep the task family visible: look-alike is seed affinity, act-alike is behavioral affinity, content similarity is semantic similarity, and propensity reads "Estimated chance of [event] within [horizon]".

Hosting on Cloudflare Pages: create a Pages project from this repository with no build command and `app` as the output directory, or deploy directly with `npx wrangler pages deploy app --project-name <name>`. `app/_headers` sets a strict same-origin content security policy and allows embedding only from nofluffadvisory.com.

## Suggested review order

1. `docs/spec/HANDOFF.md` for decisions, scope and what was and was not verified.
2. `docs/spec/DATA_CONTRACTS.md`, then `schemas/v1/common.schema.json`, `task.schema.json` and `task_decision.schema.json`.
3. `src/aip/routing/` and `src/aip/policy/compose.py`, with `tests/test_routing.py` and `tests/test_policy.py`.
4. `docs/spec/AGENT_DESIGN.md` with `src/aip/agents/gateway.py`.
5. `src/aip/release/manifest.py`, `src/aip/exchange/adcp.py`, then the modeling baselines.

## Rules the code enforces

- Three task verdicts only: ELIGIBLE, PROVISIONAL and BLOCKED. A known violation outranks missing evidence.
- Agents propose; only the router issues decisions, and only humans approve releases.
- Identifiers never become semantic features. Unit meaning comes from the type registry and the source contract.
- Every contributing source must permit an operation; silence is missing evidence.
- Affinity, probability and incremental effect are distinct claims. Abstention is a typed null, never a zero.
- No default thresholds, validity periods, prices or model identifiers. Fixture values illustrate shape only.

Values in `examples/`, `registry/` and `fixtures/` are synthetic fixtures. Synthetic results test software behavior, not market performance.

## License

MIT, see [LICENSE](LICENSE). The pinned AdCP schemas in `third_party/adcp/` keep their own Apache-2.0 license.
