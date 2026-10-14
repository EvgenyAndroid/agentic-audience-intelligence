"""Bounded agent roles. Roles share one orchestrator; they are not separate services."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Role:
    name: str
    purpose: str
    tools: frozenset[str]
    escalates_to: str


def _role(name: str, purpose: str, tools: set[str], escalates_to: str) -> Role:
    return Role(name, purpose, frozenset(tools), escalates_to)


ROLES: dict[str, Role] = {
    r.name: r
    for r in [
        _role(
            "briefing",
            "Turn a request into a draft objective and task list",
            {"read_artifact", "list_profiles"},
            "analyst",
        ),
        _role(
            "fitness",
            "Read profile reports and propose per-task verdicts",
            {"read_artifact", "read_profile_report", "read_decision"},
            "data_steward",
        ),
        _role(
            "meaning",
            "Propose attribute-to-dictionary mappings with evidence kind",
            {"read_artifact", "read_dictionary", "propose_mapping"},
            "data_steward",
        ),
        _role(
            "joins_features",
            "Propose relationship and feature plans",
            {"read_artifact", "propose_feature_plan", "run_pit_check"},
            "scientist",
        ),
        _role(
            "experiments",
            "Propose bounded experiments within the model allowlist",
            {"read_artifact", "submit_job", "read_metrics"},
            "scientist",
        ),
        _role(
            "evaluation",
            "Interpret computed metrics; never compute them",
            {"read_artifact", "read_metrics"},
            "scientist",
        ),
        _role(
            "output_preparation",
            "Draft evidence cards and release notes",
            {"read_artifact", "draft_evidence_card"},
            "release_reviewer",
        ),
        _role(
            "monitoring",
            "Read monitoring reports and propose reassessment",
            {"read_artifact", "read_monitoring"},
            "operator",
        ),
    ]
}
