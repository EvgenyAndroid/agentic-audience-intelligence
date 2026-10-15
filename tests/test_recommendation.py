import copy

import pytest
from conftest import NOW, example

from aip.canonical import sha256_of
from aip.recommendation import Candidate, admissibility_issues, recommend

OBJECTIVE = example("objective/obj_seed_affinity_web")
REQUESTED = Candidate(
    example("task/task_seed_affinity_score"), example("task_decision/decision_seed_affinity_eligible")
)
PROVISIONAL = Candidate(
    example("task/task_score_unregistered_location"), example("task_decision/decision_missing_policy_provisional")
)


def derived(task_id, family, verdict, cost=None, reasons=None, valid_until=None):
    """A separately identified task for the same objective, with a decision shaped like the router's."""
    task = copy.deepcopy(REQUESTED.task)
    task.update(task_id=task_id, task_family=family)
    decision = copy.deepcopy(REQUESTED.decision)
    decision.update(
        decision_id=f"dec_{task_id}",
        task_ref={"id": task_id, "version": task["task_version"]},
        task_checksum=sha256_of(task),
        verdict=verdict,
        reasons=[{"code": c, "detail": c, "evidence_refs": []} for c in (reasons or [])],
        next_actions=[f"resolve {c}" for c in (reasons or [])],
    )
    if valid_until:
        decision["valid_until"] = valid_until
    return Candidate(task, decision, cost)


def usd(amount):
    return {"amount": amount, "currency": "USD", "usage_record_refs": ["usage_run_demo"]}


def run(requested, *alternatives):
    return recommend(
        recommendation_id="rec_test", objective=OBJECTIVE, requested=requested, alternatives=alternatives, now=NOW
    )


def test_sections_follow_verdicts_and_requested_comes_first():
    blocked = derived("task_alt_blocked", "seed_affinity", "BLOCKED", reasons=["forbidden_row_level_egress"])
    rec = run(REQUESTED, PROVISIONAL, blocked, derived("task_alt_behavior", "behavioral_affinity", "ELIGIBLE"))
    assert rec["requested_task"]["verdict"] == "ELIGIBLE"
    assert [o["fit"] for o in rec["recommended_options"]] == ["requested", "alternative"]
    assert rec["recommended_options"][0]["position"] == 1
    assert [o["decision_ref"] for o in rec["unlock_options"]] == [PROVISIONAL.decision["decision_id"]]
    assert rec["unlock_options"][0]["reason_codes"] == ["missing_execution_policy"]
    assert rec["blocked_options"][0]["reason_codes"] == ["forbidden_row_level_egress"]
    assert rec["ranking_status"] == "ranked"


def test_blocked_request_keeps_its_card_but_is_not_recommended():
    requested = derived("task_req_blocked", "seed_affinity", "BLOCKED", reasons=["forbidden_row_level_egress"])
    rec = run(requested, derived("task_alt_aggregate", "aggregate_measurement", "ELIGIBLE"))
    assert rec["requested_task"]["verdict"] == "BLOCKED"
    assert rec["requested_task"]["decision_ref"] not in [o["decision_ref"] for o in rec["recommended_options"]]
    assert rec["recommended_options"][0]["fit"] == "alternative"
    assert rec["recommended_options"][0]["fit_basis"] == ["different_question"]


def test_known_costs_order_a_group_and_unknown_cost_is_not_zero():
    blocked = derived("task_req_blocked", "seed_affinity", "BLOCKED", reasons=["forbidden_row_level_egress"])
    cheap = derived("task_alt_cheap", "seed_affinity", "ELIGIBLE", cost=usd("12.50"))
    dear = derived("task_alt_dear", "seed_affinity", "ELIGIBLE", cost=usd("40"))
    ranked = run(blocked, dear, cheap)
    assert [o["decision_ref"] for o in ranked["recommended_options"]] == ["dec_task_alt_cheap", "dec_task_alt_dear"]
    assert ranked["ranking_status"] == "ranked"
    unknown = run(blocked, dear, derived("task_alt_unknown", "seed_affinity", "ELIGIBLE"))
    assert {o["position"] for o in unknown["recommended_options"]} == {1}
    assert unknown["ranking_status"] == "insufficient_evidence_to_rank"
    assert {"status": "unknown"} in [o["cost"] for o in unknown["recommended_options"]]


def test_partial_order_when_some_ties_remain():
    a = derived("task_alt_a", "behavioral_affinity", "ELIGIBLE")
    b = derived("task_alt_b", "cohort", "ELIGIBLE")
    rec = run(REQUESTED, a, b)
    assert [o["position"] for o in rec["recommended_options"]] == [1, 2, 2]
    assert rec["ranking_status"] == "partial_order"


def test_no_eligible_options():
    rec = run(PROVISIONAL)
    assert rec["recommended_options"] == [] and rec["ranking_status"] == "no_eligible_options"


def test_recommendation_lapses_with_its_earliest_decision():
    soon = derived("task_alt_soon", "seed_affinity", "ELIGIBLE", valid_until="2026-10-15T00:00:00Z")
    assert run(REQUESTED, soon)["valid_until"] == "2026-10-15T00:00:00Z"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda c: Candidate({**c.task, "task_family": "cohort"}, c.decision),  # task changed after its decision
        lambda c: Candidate(c.task, {**c.decision, "valid_until": "2026-10-01T00:00:00Z"}),  # lapsed decision
        lambda c: Candidate({**c.task, "objective_ref": {"id": "obj_other", "version": "1.0.0"}}, c.decision),
    ],
)
def test_ranker_refuses_stale_or_foreign_inputs(mutate):
    with pytest.raises(ValueError):
        run(REQUESTED, mutate(derived("task_alt", "seed_affinity", "ELIGIBLE")))


def test_admissibility_accepts_the_rankers_output_and_rejects_a_tampered_one():
    rec = run(REQUESTED, PROVISIONAL)
    decisions = {c.decision["decision_id"]: c.decision for c in (REQUESTED, PROVISIONAL)}
    assert admissibility_issues(rec, decisions, NOW) == []
    tampered = copy.deepcopy(rec)
    tampered["recommended_options"].append({**tampered["unlock_options"][0], "position": 2})
    issues = admissibility_issues(tampered, decisions, NOW)
    assert any("PROVISIONAL decision listed under recommended_options" in i for i in issues)


def test_example_matches_the_rankers_output():
    rec = recommend(
        recommendation_id="rec_seed_affinity_web_0001",
        objective=OBJECTIVE,
        requested=REQUESTED,
        alternatives=[
            PROVISIONAL,
            Candidate(
                example("task/task_quarantine_score"), example("task_decision/decision_quarantine_score_provisional")
            ),
        ],
        now=NOW,
    )
    assert rec == example("recommendation/rec_seed_affinity_web_0001")
