# ADR 0004: Python with Windows-first tooling

Status: Accepted, 14 October 2026

## Context

Session 3 verification targets Windows and PowerShell with no Bash, Unix-only commands or WSL dependency (NFR08). The modeling work needs the Python data stack.

## Decision

Implementation language is Python 3.11 or later. Paths use `pathlib` only. Repository automation is PowerShell (`scripts\*.ps1`), compatible with Windows PowerShell 5.1 and PowerShell 7. CI runs on `windows-latest`. Hash-locked vendored files are excluded from line-ending conversion.

## Consequences

Contributors on Windows run the same commands as CI. The checks executed in Session 2 ran on Linux in the authoring sandbox; Windows execution is recorded as not run until CI or a local Windows run produces reports.
