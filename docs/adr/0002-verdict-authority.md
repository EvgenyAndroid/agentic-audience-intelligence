# ADR 0002: Agents propose; the router decides

Status: Accepted, 14 October 2026

## Context

The routing benchmark must measure agent judgment, while production verdicts must never depend on unverified model output. One shared "decision" object would let a model write ELIGIBLE directly.

## Decision

There are two contracts. `agent_proposal` is advisory (`authority: advisory`) and is what the benchmark scores. `task_decision` is issued only by the router (`decided_by.authority: router`) from deterministic checks and from facts established by a policy service, steward, reviewer or deterministic job. Neither facts nor prerequisites can name an agent as their authority. The router may cite proposal IDs but never reads their content.

## Consequences

Agent quality can improve or regress without changing production verdicts. Every prerequisite in a decision is traceable to a non-agent authority. Agents add value through diagnosis, mapping and explanation that people then confirm, not by granting permission.
