# Session 2 verification record

Executed 14 October 2026 in the Linux authoring sandbox. These results cover only the components and fixtures in this repository. They are not Windows results and not evidence of model quality, data quality or integration support.

Environment: Python 3.12.3, jsonschema 4.26.0, referencing 0.37.0, numpy 2.4.4, scikit-learn 1.8.0, pytest 9, ruff 0.17.0, mypy 2.4.0.

| Check | Command (PowerShell equivalent) | Result |
| --- | --- | --- |
| Schema meta-validation | loaded by every test session (`SchemaSet` calls `check_schema`) | Passed: 34 of 34 |
| Conformance | `aip conformance` | Passed: 76 valid documents, 54 invalid cases each failing at the expected layer, keyword and path (`conformance.json`) |
| Tests | `.\scripts\test.ps1` | Passed: 195 of 195 (`pytest-linux.xml`) |
| Lint | `.\scripts\lint.ps1 -StrictTypes` | Passed: ruff clean, ruff format clean, mypy no issues in 46 files |
| AdCP lock | hashes checked by `aip.exchange.adcp` on every validation | Passed: both vendored files match `adcp.lock.json` |
| Routing suite (rules router) | `.\scripts\benchmark.ps1` | 11 of 11, critical false-safe 0, false block 0 (`routing_benchmark_development.json`). Passed by construction: the cases were authored alongside the router, so this demonstrates harness wiring only |

Not run in Session 2:

- Windows and PowerShell execution of `scripts\*.ps1`, and the GitHub Actions workflow.
- Agent routing evaluation with a real reasoning model, hidden-oracle isolation, the locked suite and the analyst comparator.
- Statistical utility on real data, calibration on real outcomes, clean-room enforcement, live AdCP destinations, governance context, pricing, deletion propagation, numerical replay on real data, and performance targets (NFR05).

Local and CI runs write to `reports\local\`, which Git ignores. Commit a curated copy here only when a new session records verified results.
