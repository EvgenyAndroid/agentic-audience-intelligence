# Agentic Audience Intelligence Platform

A provider-agnostic platform that assesses permitted advertising data, selects defensible tasks, runs bounded modeling workflows, and prepares reviewable audience or contextual outputs. Agents interpret and propose. Deterministic services enforce contracts, compute results and control release.

This repository holds the specification and a working scaffold: normative JSON Schema contracts, a registry, a task router, policy composition, an agent tool gateway, modeling baselines, release controls, an AdCP boundary adapter and an evaluation harness. It is not a validated product. No real data, live integration or model-quality claim has been tested.

## Verification status

| Check | Status | Evidence |
| --- | --- | --- |
| Schema meta-validation (34 files, JSON Schema 2020-12) | Passed (Linux) | `reports/session2/` |
| Valid examples and registry documents (76) | Passed (Linux) | `reports/session2/conformance.json` |
| Invalid cases fail for the stated layer, keyword and path (54) | Passed (Linux) | `reports/session2/conformance.json` |
| Unit and contract tests (195) | Passed (Linux, Python 3.12) | `reports/session2/pytest-linux.xml` |
| Lint (ruff) and type check (mypy, 46 files) | Passed (Linux) | `reports/session2/README.md` |
| AdCP adapter output against pinned AdCP 3.1.20 schemas | Passed (Linux) | `tests/test_representation_and_exchange.py` |
| Rules router on the development routing suite (11 cases) | Passed by construction | `reports/session2/routing_benchmark_development.json` |
| Windows and PowerShell execution, CI | Not run | Run `.\scripts\check-all.ps1` or push to trigger CI |
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
docs/spec/          BRD, PRD (Revision 2), v3.1 prompt, DATA_CONTRACTS, AGENT_DESIGN, HANDOFF
docs/adr/           Architecture decision records
schemas/v1/         Normative JSON Schema 2020-12 contracts (34 files)
registry/           Type registry, reason-code registry, reference profiles, fixture policies
examples/valid/     One or more valid documents per contract kind, including router golden decisions
examples/invalid/   Patch-based invalid cases with expected failure layer, keyword and path
fixtures/routing/   Development routing suite: cases, world documents, separate oracles
src/aip/            Python package (see below)
tests/              pytest suite, including PRD traceability and router golden-output checks
third_party/adcp/   Pinned AdCP 3.1.20 schemas (Apache-2.0), hash-locked
scripts/            PowerShell automation
reports/session2/   Results of checks actually executed in Session 2
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
| `aip.evaluation` | Routing benchmark harness and metrics |

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
