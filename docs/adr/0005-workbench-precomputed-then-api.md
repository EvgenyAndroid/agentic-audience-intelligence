# ADR 0005: The audience workbench ships precomputed now and moves behind an API later

Status: Accepted, 15 October 2026

## Context

The demonstrator's first release explained decisions on four fixed scenarios. The product goal is wider: bring data, have it assessed, choose or accept a recommended method and model, and build a scaled audience. Doing that live needs the Python engine at request time, either in the visitor's browser (Pyodide, 20 to 30 MB per visitor and untestable in this repository's sandbox) or on a server, which takes custody of uploaded data.

## Decision

Two stages, one bundle shape.

**Stage A (now): precomputed workbench.** `aip.workbench` generates eight synthetic datasets (B2B, geography, demographic and firmographic, interest and behavioral segments, TV viewing, web and app events, first-party CRM, page content). For each, the build writes a confirmed source profile, an immutable manifest whose hash is the generated snapshot's, one objective, one task per method plus export tasks, and evidence bundles whose facts are computed from the data (coverage, label counts, sensitive-attribute screening). The real router decides every task, the ranker recommends among them, and only eligible methods are modeled and evaluated on held-out records. `aip workbench-build` writes one JSON bundle per dataset under `app/data/workbench/`. The page filters those results (method, model, reach, export) and never re-runs the engine. There is no upload.

**Stage B (later): a thin server API over the same functions.** Same engine, same contracts, same bundle shape returned per request instead of read from a file:

| Endpoint | Does | Engine call |
| --- | --- | --- |
| `POST /datasets` | Receive a file, write an immutable manifest and a draft source profile | intake and profiling |
| `POST /datasets/{id}/assess` | Draft the assessment and method proposals | reasoning agent over column names and summary statistics only; output is an `agent_proposal` |
| `POST /datasets/{id}/route` | Decide every proposed task | `decide`, `recommend` |
| `POST /datasets/{id}/build` | Train and score one eligible method | `aip.workbench.methods` |
| `GET /datasets/{id}/bundle` | Return the workbench bundle | as in stage A |

The page switches from reading `data/workbench/*.json` to calling these endpoints; its rendering code does not change.

## Consequences

Stage A is honest and cheap to host: everything is synthetic, disclosed and reproducible, and `aip workbench-build --check` compares committed bundles with a fresh build (floats within 2e-3, since model scores can differ in the last digits across platforms).

Stage B must add what stage A avoids by construction: authenticated tenants, a data-processing agreement and retention limits for uploads, row data that never reaches a language model, the steward and human-review steps that the synthetic documents currently fill with fixed fixtures, and the export and release controls that turn an eligible score file into an approved release. The routing contracts already carry all of these; stage B supplies real evidence for them.

## Stage B, slice 1 (15 October 2026)

Upload, assess and route are live in code (`aip.uploads`, `aip.api`). Slice 2 adds the build step: `POST /v1/datasets/{id}/build/{method}` trains and scores a method the router decided ELIGIBLE, with the same code the workbench uses, and the page shows the reach slider, charts and export on the uploader's own IDs. Slice 3 adds expansion: a universe file of new records with the same key and feature columns is scored by the same fitted models (`POST /v1/datasets/{id}/expand/{method}`), so a look-alike, act-alike or propensity audience can grow beyond the uploaded file. The universe has no labels; the held-out evaluation on the upload is shown as its expected quality, and its rights are attested separately. Decisions taken for this slice:

- **Hosting.** Cloudflare Containers behind a Worker (`deploy/api/`), in the same account as the demonstrator. One container instance holds uploads on its own disk, internet access off; idle containers stop after 30 minutes and take their disk with them.
- **Access.** Invite keys only. The server stores SHA-256 hashes mapped to tenant ids (`AIP_API_KEYS`); tenants are isolated by folder and by id, and each tenant gets its own copy of the location policies, because the router refuses another tenant's policies.
- **Retention.** 24 hours at most by default (`AIP_RETENTION_HOURS`; the live demo keeps uploads one hour, under data terms the uploader accepts), enforced on every authenticated request and by a sweep every minute; `DELETE` removes an upload at once. Row values are never logged.
- **Evidence from an upload.** The steward fills by confirmation what stage A filled with fixtures: record type, roles, sensitive and excluded columns, observation period. Rights and feature timing cannot be checked from a CSV, so they are facts only when the uploader attests to them and unknown otherwise, which keeps dependent methods PROVISIONAL rather than ELIGIBLE.
- **No language model.** The assessment stays rule-based; a reasoning agent over column names and summary statistics remains a later option and would only propose.
