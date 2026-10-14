# ADR 0001: JSON Schema files are the normative contracts

Status: Accepted, 14 October 2026

## Context

The platform needs contracts that buyer agents, exchange adapters and services in any language can validate. Re-declaring the same contracts as Python classes would create a second source of truth that drifts.

## Decision

The JSON Schema 2020-12 files in `schemas/v1` are normative. Python code loads them through one `SchemaSet` and validates documents at every boundary. Internal logic works on validated dictionaries. Rules JSON Schema cannot express live in `aip.contracts.semantic` and run after schema validation.

## Consequences

Schemas stay language-neutral and are the single place to change a contract. Python gets less static typing for contract objects. Conformance tests (valid examples and patched invalid cases) and router golden outputs guard against drift between schemas and code.
