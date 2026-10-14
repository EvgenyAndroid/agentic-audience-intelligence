import copy
from datetime import timedelta

import pytest
from conftest import NOW, example, registry_doc

from aip.registry import DocumentIndex
from aip.routing import decide, is_decision_current, required_prerequisites

GOLDEN = {
    "task_cr_export_rows": "decision_aggregate_only_rows_blocked",
    "task_cr_export_aggregate": "decision_aggregate_only_aggregate_eligible",
    "task_score_unregistered_location": "decision_missing_policy_provisional",
    "task_propensity_train_no_labels": "decision_propensity_no_labels_provisional",
    "task_seed_affinity_score": "decision_seed_affinity_eligible",
    "task_quarantine_profile": "decision_quarantine_profile_eligible",
    "task_quarantine_score": "decision_quarantine_score_provisional",
}


def route(task, world, types, reasons, config, facts=None, **kw):
    bundle = example(f"evidence_bundle/bundle_{task['task_id']}")
    if facts is not None:
        bundle = {**bundle, "facts": facts}
    return decide(task, documents=world, bundle=bundle, types=types, reasons=reasons, config=config, now=NOW, **kw)


def codes(decision):
    return [r["code"] for r in decision["reasons"]]


@pytest.mark.parametrize("task_id,golden", GOLDEN.items())
def test_router_reproduces_golden_decisions(world, types, reasons, config, task_id, golden):
    assert route(example(f"task/{task_id}"), world, types, reasons, config) == example(f"task_decision/{golden}")


def test_aggregate_only_source_blocks_rows_but_allows_aggregates(world, types, reasons, config):
    rows = route(example("task/task_cr_export_rows"), world, types, reasons, config)
    agg = route(example("task/task_cr_export_aggregate"), world, types, reasons, config)
    assert rows["verdict"] == "BLOCKED" and "forbidden_row_level_egress" in codes(rows)
    assert agg["verdict"] == "ELIGIBLE"
    assert (
        example("task/task_cr_export_rows")["input_snapshot_refs"]
        == example("task/task_cr_export_aggregate")["input_snapshot_refs"]
    )


def test_missing_policy_is_provisional(world, types, reasons, config):
    d = route(example("task/task_score_unregistered_location"), world, types, reasons, config)
    assert d["verdict"] == "PROVISIONAL" and codes(d) == ["missing_execution_policy"]


def test_new_propensity_without_labels_is_provisional_with_reason(world, types, reasons, config):
    d = route(example("task/task_propensity_train_no_labels"), world, types, reasons, config)
    assert d["verdict"] == "PROVISIONAL" and codes(d) == ["unsupported_outcome_probability"]


def test_existing_model_inference_does_not_require_labels():
    task = copy.deepcopy(example("task/task_propensity_train_no_labels"))
    task.update(
        operation="infer", model_ref={"id": "propensity_logreg_v1", "version": "1.0.0"}, requested_artifact="score_file"
    )
    required = required_prerequisites(task)
    assert "P-LABELS-QUALIFIED" not in required
    assert {"P-MODEL-VALIDATED", "P-POPULATION-COMPATIBLE", "P-FEATURE-TIMING"} <= set(required)


def test_known_prohibition_outranks_missing_evidence(world, types, reasons, config):
    d = route(example("task/task_cr_export_rows"), world, types, reasons, config, facts=[])
    assert d["verdict"] == "BLOCKED"
    assert codes(d)[0] in {"forbidden_operation", "forbidden_row_level_egress"}
    assert "unverified_permission" in codes(d)


def test_quarantined_source_can_be_profiled_but_not_scored(world, types, reasons, config):
    assert route(example("task/task_quarantine_profile"), world, types, reasons, config)["verdict"] == "ELIGIBLE"
    scored = route(example("task/task_quarantine_score"), world, types, reasons, config)
    assert scored["verdict"] == "PROVISIONAL" and codes(scored) == ["unregistered_source_profile"]


def test_agent_proposals_are_recorded_but_never_change_the_verdict(world, types, reasons, config):
    proposal = example("agent_proposal/proposal_fitness_rows")
    assert proposal["proposed_verdict"] == "ELIGIBLE"
    d = route(
        example("task/task_cr_export_rows"),
        world,
        types,
        reasons,
        config,
        agent_proposal_refs=[proposal["proposal_id"]],
    )
    assert d["verdict"] == "BLOCKED" and d["agent_proposal_refs"] == ["prop_0001"]


def test_validity_is_bounded_by_ttl_and_lapses_on_policy_change(world, types, reasons, config):
    d = route(example("task/task_seed_affinity_score"), world, types, reasons, config)
    assert d["valid_until"] == "2026-10-21T12:00:00Z"
    current = d["policy_versions"]
    assert is_decision_current(d, NOW + timedelta(days=1), current)
    assert not is_decision_current(d, NOW + timedelta(days=8), current)
    changed = [{"id": p["id"], "version": "1.0.1"} for p in current]
    assert not is_decision_current(d, NOW + timedelta(days=1), changed)


def test_bundle_for_another_task_is_rejected(world, types, reasons, config):
    with pytest.raises(ValueError):
        decide(
            example("task/task_seed_affinity_score"),
            documents=world,
            bundle=example("evidence_bundle/bundle_task_cr_export_rows"),
            types=types,
            reasons=reasons,
            config=config,
            now=NOW,
        )


def test_fact_with_wrong_effect_reason_is_rejected(world, types, reasons, config):
    bad = [
        {
            "prerequisite_id": "P-RIGHTS-USE",
            "value": False,
            "established_by": "policy_service",
            "evidence_refs": ["x"],
            "reason_code": "unverified_permission",
            "observed_at": "2026-10-10T00:00:00Z",
        }
    ]
    with pytest.raises(ValueError):
        route(example("task/task_seed_affinity_score"), world, types, reasons, config, facts=bad)


def test_task_observation_unit_must_match_source_contract(world, types, reasons, config):
    task = copy.deepcopy(example("task/task_seed_affinity_score"))
    hh = {"type_id": "provider_household_key", "type_version": "1.0.0", "namespace": "acr_demo_hh"}
    task["units"]["observation_units"][0]["unit"] = hh
    task["units"]["modeling_unit"] = task["units"]["output_unit"] = hh
    d = decide(task, documents=world, bundle=None, types=types, reasons=reasons, config=config, now=NOW)
    assert d["verdict"] == "BLOCKED" and "grain_incompatible" in codes(d)


def _prerequisite(decision, pid):
    return next(p for p in decision["prerequisites"] if p["prerequisite_id"] == pid)


def _index_with(world, *extra):
    kinds = ("execution_policy", "output_policy", "source_profile", "dataset_manifest", "objective")
    return DocumentIndex([d for k in kinds for d in world.all(k)] + list(extra))


def _rebound_bundle(task, bundle_id):
    bundle = copy.deepcopy(example(f"evidence_bundle/bundle_{bundle_id}"))
    bundle["task_ref"] = {"id": task["task_id"], "version": task["task_version"]}
    return bundle


def test_policy_from_another_tenant_violates_tenant_scope(world, types, reasons, config):
    foreign = copy.deepcopy(registry_doc("policies/exec_cleanroom_demo"))
    foreign.update(policy_id="exec_other_tenant", tenant_id="tenant_other")
    task = copy.deepcopy(example("task/task_cr_export_aggregate"))
    task["policy_refs"]["execution"] = [{"id": "exec_other_tenant", "version": foreign["policy_version"]}]
    d = decide(
        task,
        documents=_index_with(world, foreign),
        bundle=_rebound_bundle(task, "task_cr_export_aggregate"),
        types=types,
        reasons=reasons,
        config=config,
        now=NOW,
    )
    assert d["verdict"] == "BLOCKED" and "tenant_scope_mismatch" in codes(d)


def test_unverifiable_unit_mapping_does_not_satisfy_grain(world, types, reasons, config):
    task = copy.deepcopy(example("task/task_seed_affinity_score"))
    task["units"]["output_unit"] = {"type_id": "postal_code", "type_version": "1.0.0", "namespace": "zip_us"}
    task["units"]["mapping_refs"] = [{"id": "no_such_mapping", "version": "9.9.9"}]
    d = decide(
        task,
        documents=world,
        bundle=_rebound_bundle(task, "task_seed_affinity_score"),
        types=types,
        reasons=reasons,
        config=config,
        now=NOW,
    )
    assert _prerequisite(d, "P-GRAIN-COMPATIBLE")["outcome"] == "missing"
    assert d["verdict"] == "PROVISIONAL" and "missing_unit_mapping" in codes(d)


def test_aggregation_rules_apply_only_at_their_location(world, types, reasons, config):
    task = copy.deepcopy(example("task/task_cr_export_aggregate"))
    task["operation"] = "aggregate"
    task["execution_location_ref"] = "loc_somewhere_else"
    d = decide(
        task,
        documents=world,
        bundle=_rebound_bundle(task, "task_cr_export_aggregate"),
        types=types,
        reasons=reasons,
        config=config,
        now=NOW,
    )
    assert _prerequisite(d, "P-AGGREGATION-RULES")["outcome"] == "missing"


def test_every_source_must_supply_aggregation_rules(world, types, reasons, config):
    silent = copy.deepcopy(registry_doc("policies/output_cleanroom_aggregate_only"))
    silent.update(policy_id="output_task_silent", aggregation_rules=[])
    task = copy.deepcopy(example("task/task_cr_export_aggregate"))
    task["operation"] = "aggregate"
    task["policy_refs"]["output"] = [{"id": "output_task_silent", "version": silent["policy_version"]}]
    d = decide(
        task,
        documents=_index_with(world, silent),
        bundle=_rebound_bundle(task, "task_cr_export_aggregate"),
        types=types,
        reasons=reasons,
        config=config,
        now=NOW,
    )
    assert _prerequisite(d, "P-AGGREGATION-RULES")["outcome"] == "missing"
    assert d["verdict"] == "PROVISIONAL" and "aggregation_rules_unknown" in codes(d)
