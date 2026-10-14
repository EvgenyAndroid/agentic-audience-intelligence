# ADR 0003: Most-restrictive policy composition with silence as missing evidence

Status: Accepted, 14 October 2026

## Context

Tasks combine inputs from several sources, each with its own execution and output restrictions, and clean rooms often allow internal computation while forbidding row-level export.

## Decision

Every contributing source must permit an operation at the selected location. Any prohibition wins. An unlisted operation is missing evidence, never permission. Contradictory statements within one source block the task. Internal computation, row export and aggregate release are separate operations with separate decisions. Aggregation rules compose per counted unit using the highest threshold, blocking over suppression, and the intersection of approved dimensions. Thresholds always come from the policy owner.

## Consequences

The same dataset can be BLOCKED for score export and ELIGIBLE for a qualifying aggregate. Missing policies surface as PROVISIONAL with a named remedy instead of failing open. Adding a permissive source can never widen what a restrictive source allows.
