from datetime import timedelta
from decimal import Decimal

import pytest
from conftest import NOW, example

from aip.costs import ContributionInputs, break_even_runs, contribution, cost_per_comparable_run, net_data_revenue_cpm
from aip.lifecycle import AUDIENCE, DELIVERY, JOB, TransitionError, transition
from aip.release import CommitError, authorize, commit, next_delivery_action, prepare_release

REVIEWER = {"actor_id": "user_reviewer_01", "actor_type": "human", "role": "release_reviewer"}
SERVICE = {"actor_id": "svc_release", "actor_type": "service", "role": "release_service"}
MEMBERS = ["ent_ck_77", "ent_ck_91"]


def prepared():
    decision = example("task_decision/decision_seed_affinity_eligible")
    manifest = prepare_release(
        release_id="rel_t",
        release_version="1.0.0",
        tenant_id="tenant_demo",
        artifacts=[({"id": "mem_file", "version": "1.0.0"}, "cohort_membership", MEMBERS)],
        evidence_card_ref={"id": "card_seed_web_0001", "version": "1.0.0"},
        decision=decision,
        populations=example("evidence_card/card_seed_affinity_exploratory")["populations"],
        destination_ref="dest_demo_dsp",
        expires_at=NOW + timedelta(days=5),
        prepared_by=SERVICE,
        now=NOW,
    )
    auth = authorize(
        manifest,
        authorization_id="auth_t",
        reviewer=REVIEWER,
        decision="approved",
        purpose="pilot",
        valid_from=NOW,
        valid_until=NOW + timedelta(days=2),
        now=NOW,
    )
    return decision, manifest, auth


def test_commit_happy_path_and_rechecks():
    decision, manifest, auth = prepared()
    current = decision["policy_versions"]
    commit(
        manifest,
        auth,
        decision,
        now=NOW + timedelta(hours=1),
        current_policy_versions=current,
        member_keys=MEMBERS,
        suppressed_keys=[],
    )
    with pytest.raises(CommitError, match="suppressed"):
        commit(
            manifest,
            auth,
            decision,
            now=NOW + timedelta(hours=1),
            current_policy_versions=current,
            member_keys=MEMBERS,
            suppressed_keys=["ent_ck_91"],
        )
    with pytest.raises(CommitError, match="policy"):
        commit(
            manifest,
            auth,
            decision,
            now=NOW + timedelta(hours=1),
            current_policy_versions=[],
            member_keys=MEMBERS,
            suppressed_keys=[],
        )
    with pytest.raises(CommitError, match="validity"):
        commit(
            manifest,
            auth,
            decision,
            now=NOW + timedelta(days=3),
            current_policy_versions=current,
            member_keys=MEMBERS,
            suppressed_keys=[],
        )


def test_changed_membership_cannot_reuse_approval():
    decision, manifest, auth = prepared()
    changed = dict(manifest, content_checksum="sha256:" + "0" * 64)
    with pytest.raises(CommitError, match="checksum"):
        commit(
            changed,
            auth,
            decision,
            now=NOW,
            current_policy_versions=decision["policy_versions"],
            member_keys=MEMBERS,
            suppressed_keys=[],
        )


def test_agents_cannot_authorize_and_non_eligible_cannot_be_prepared():
    decision, manifest, _ = prepared()
    with pytest.raises(ValueError):
        authorize(
            manifest,
            authorization_id="a",
            reviewer={"actor_id": "agent_1", "actor_type": "agent", "role": "x"},
            decision="approved",
            purpose="p",
            valid_from=NOW,
            valid_until=NOW + timedelta(days=1),
            now=NOW,
        )
    with pytest.raises(CommitError):
        prepare_release(
            release_id="r",
            release_version="1.0.0",
            tenant_id="tenant_demo",
            artifacts=[],
            evidence_card_ref={"id": "c", "version": "1"},
            decision=example("task_decision/decision_missing_policy_provisional"),
            populations=[],
            destination_ref=None,
            expires_at=NOW,
            prepared_by=SERVICE,
            now=NOW,
        )


def test_unknown_delivery_is_reconciled_not_retried():
    assert next_delivery_action(example("export_receipt/receipt_unknown_state")) == "reconcile"
    assert next_delivery_action(example("export_receipt/receipt_accepted_confirmed")) == "none"


def test_state_machines():
    assert transition(JOB, "queued", "running") == "running"
    assert transition(AUDIENCE, "prepared", "approved") == "approved"
    for machine, a, b in [
        (JOB, "succeeded", "running"),
        (AUDIENCE, "draft", "released"),
        (DELIVERY, "live", "submitted"),
    ]:
        with pytest.raises(TransitionError):
            transition(machine, a, b)


def _run(outcome, amount):
    return {
        "subject": {"subject_type": "run", "subject_ref": "r"},
        "comparable_run_class": "c",
        "run_outcome": outcome,
        "costs": [
            {
                "category": "compute",
                "amount": amount,
                "currency": "USD",
                "basis": "metered",
                "allocation_method_ref": None,
            }
        ],
    }


def test_cost_per_comparable_run_counts_abstentions_and_attributes_failures():
    records = [_run("completed_with_output", "10"), _run("completed_no_useful_signal", "6"), _run("failed", "4")]
    assert cost_per_comparable_run(records, "c", "USD") == Decimal("10")
    assert cost_per_comparable_run([_run("failed", "4")], "c", "USD") is None


def test_contribution_cpm_and_break_even():
    x = ContributionInputs(*(Decimal(v) for v in ["1000", "200", "100", "50", "10", "40", "20", "60", "15"]))
    assert contribution(x) == Decimal("905")
    assert net_data_revenue_cpm(2_000_000, Decimal("1.50"), Decimal("0.6")) == Decimal("1800")
    assert break_even_runs(Decimal("1000"), Decimal("0")) is None
    assert break_even_runs(Decimal("1000"), Decimal("250")) == Decimal("4")
