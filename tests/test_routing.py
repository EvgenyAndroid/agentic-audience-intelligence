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


def _index_with(world, *extra, drop=()):
    kinds = ("execution_policy", "output_policy", "source_profile", "dataset_manifest", "objective")
    docs = [d for k in kinds for d in world.all(k) if d.get("policy_id") not in drop]
    return DocumentIndex(docs + list(extra))


def _decide(task, documents, bundle_id, types, reasons, config):
    bundle = copy.deepcopy(example(f"evidence_bundle/bundle_{bundle_id}"))
    bundle["task_ref"] = {"id": task["task_id"], "version": task["task_version"]}
    return decide(task, documents=documents, bundle=bundle, types=types, reasons=reasons, config=config, now=NOW)


HOUSEHOLD = {"type_id": "provider_household_key", "type_version": "1.0.0", "namespace": "acr_demo_hh"}
POSTAL = {"type_id": "postal_code", "type_version": "1.0.0", "namespace": "zip_us"}
BOGUS_MAPPING = [{"id": "no_such_mapping", "version": "9.9.9"}]


def test_policy_from_another_tenant_violates_tenant_scope_and_is_not_bound(world, types, reasons, config):
    foreign = copy.deepcopy(registry_doc("policies/exec_cleanroom_demo"))
    foreign.update(policy_id="exec_other_tenant", tenant_id="tenant_other")
    task = copy.deepcopy(example("task/task_cr_export_aggregate"))
    task["policy_refs"]["execution"] = [{"id": "exec_other_tenant", "version": foreign["policy_version"]}]
    d = _decide(task, _index_with(world, foreign), "task_cr_export_aggregate", types, reasons, config)
    assert d["verdict"] == "BLOCKED" and "tenant_scope_mismatch" in codes(d)
    label = f"execution_policy:exec_other_tenant@{foreign['policy_version']}"
    assert _prerequisite(d, "P-TENANT-SCOPE")["evidence_refs"] == [label]
    assert "exec_other_tenant" not in [p["id"] for p in d["policy_versions"]]


@pytest.mark.parametrize(
    "unit,mapping_refs,verdict,code",
    [
        (HOUSEHOLD, [], "PROVISIONAL", "missing_unit_mapping"),  # relationship permitted, mapping not supplied
        (HOUSEHOLD, BOGUS_MAPPING, "PROVISIONAL", "missing_document"),  # cited mapping does not resolve
        (POSTAL, [], "BLOCKED", "grain_incompatible"),  # registry permits no relationship
        (POSTAL, BOGUS_MAPPING, "BLOCKED", "grain_incompatible"),  # a meaningless ref does not change that
    ],
)
def test_unit_mismatch_classification(world, types, reasons, config, unit, mapping_refs, verdict, code):
    task = copy.deepcopy(example("task/task_seed_affinity_score"))
    task["units"]["modeling_unit"] = task["units"]["output_unit"] = unit
    task["units"]["mapping_refs"] = mapping_refs
    d = _decide(task, world, "task_seed_affinity_score", types, reasons, config)
    assert d["verdict"] == verdict and code in codes(d)


def test_unresolved_policy_ref_is_missing_even_beside_a_permissive_policy(world, types, reasons, config):
    task = copy.deepcopy(example("task/task_cr_export_aggregate"))
    task["policy_refs"]["execution"] = [{"id": "exec_not_registered", "version": "1.0.0"}]
    d = _decide(task, world, "task_cr_export_aggregate", types, reasons, config)
    exec_check = _prerequisite(d, "P-EXEC-OPERATION")
    assert exec_check["outcome"] == "missing" and exec_check["reason_code"] == "missing_document"
    assert "execution_policy:exec_not_registered@1.0.0" in exec_check["evidence_refs"]
    assert d["verdict"] == "PROVISIONAL"


def test_unresolved_policy_ref_does_not_hide_an_established_prohibition(world, types, reasons, config):
    task = copy.deepcopy(example("task/task_cr_export_rows"))
    task["policy_refs"]["output"] = [{"id": "output_not_registered", "version": "1.0.0"}]
    d = _decide(task, world, "task_cr_export_rows", types, reasons, config)
    # The established prohibition outranks the missing reference within the same prerequisite.
    assert d["verdict"] == "BLOCKED" and "forbidden_row_level_egress" in codes(d)


def test_aggregation_rules_apply_only_at_their_location(world, types, reasons, config):
    task = copy.deepcopy(example("task/task_cr_export_aggregate"))
    task["operation"] = "aggregate"
    task["execution_location_ref"] = "loc_somewhere_else"
    d = _decide(task, world, "task_cr_export_aggregate", types, reasons, config)
    assert _prerequisite(d, "P-AGGREGATION-RULES")["outcome"] == "missing"


def test_task_policy_without_aggregation_rules_does_not_create_a_requirement(world, types, reasons, config):
    retention_only = copy.deepcopy(registry_doc("policies/output_cleanroom_aggregate_only"))
    retention_only.update(policy_id="output_task_retention", aggregation_rules=[])
    task = copy.deepcopy(example("task/task_cr_export_aggregate"))
    task["operation"] = "aggregate"
    task["policy_refs"]["output"] = [{"id": "output_task_retention", "version": retention_only["policy_version"]}]
    d = _decide(task, _index_with(world, retention_only), "task_cr_export_aggregate", types, reasons, config)
    assert _prerequisite(d, "P-AGGREGATION-RULES")["outcome"] == "satisfied"


def test_task_policy_cannot_fill_a_silent_source(world, types, reasons, config):
    source_policy = registry_doc("policies/output_cleanroom_aggregate_only")
    silent_source = copy.deepcopy(source_policy)
    silent_source["aggregation_rules"] = []
    task_rules = copy.deepcopy(source_policy)
    task_rules["policy_id"] = "output_task_rules"
    documents = _index_with(world, silent_source, task_rules, drop={source_policy["policy_id"]})
    task = copy.deepcopy(example("task/task_cr_export_aggregate"))
    task["operation"] = "aggregate"
    task["policy_refs"]["output"] = [{"id": "output_task_rules", "version": task_rules["policy_version"]}]
    d = _decide(task, documents, "task_cr_export_aggregate", types, reasons, config)
    assert _prerequisite(d, "P-AGGREGATION-RULES")["outcome"] == "missing"
    assert d["verdict"] == "PROVISIONAL" and "aggregation_rules_unknown" in codes(d)


def _task_policy(name, kind_doc, **changes):
    policy = copy.deepcopy(registry_doc(f"policies/{kind_doc}"))
    policy.update(policy_id=name, **changes)
    return policy


def test_silent_task_execution_policy_adds_no_requirement(world, types, reasons, config):
    base = registry_doc("policies/exec_cleanroom_demo")
    unrelated = [op for op in base["operations"] if op["operation"] != "export_aggregate"][:1]
    silent = _task_policy("exec_task_silent", "exec_cleanroom_demo", operations=unrelated)
    task = copy.deepcopy(example("task/task_cr_export_aggregate"))
    task["policy_refs"]["execution"] = [{"id": "exec_task_silent", "version": silent["policy_version"]}]
    d = _decide(task, _index_with(world, silent), "task_cr_export_aggregate", types, reasons, config)
    assert _prerequisite(d, "P-EXEC-OPERATION")["outcome"] == "satisfied" and d["verdict"] == "ELIGIBLE"


def test_task_execution_prohibition_still_blocks(world, types, reasons, config):
    base = registry_doc("policies/exec_cleanroom_demo")
    ops = [{**op, "permission": "prohibited"} for op in base["operations"] if op["operation"] == "export_aggregate"]
    prohibiting = _task_policy("exec_task_prohibits", "exec_cleanroom_demo", operations=ops)
    task = copy.deepcopy(example("task/task_cr_export_aggregate"))
    task["policy_refs"]["execution"] = [{"id": "exec_task_prohibits", "version": prohibiting["policy_version"]}]
    d = _decide(task, _index_with(world, prohibiting), "task_cr_export_aggregate", types, reasons, config)
    assert d["verdict"] == "BLOCKED" and "forbidden_operation" in codes(d)


def test_task_permission_cannot_fill_a_silent_source(world, types, reasons, config):
    base = registry_doc("policies/exec_cleanroom_demo")
    assert "calibrate" not in [op["operation"] for op in base["operations"]]
    template = base["operations"][0]
    permits = _task_policy(
        "exec_task_permits",
        "exec_cleanroom_demo",
        operations=[{**template, "operation": "calibrate", "permission": "permitted"}],
    )
    task = copy.deepcopy(example("task/task_cr_export_aggregate"))
    task["operation"] = "calibrate"
    task["policy_refs"]["execution"] = [{"id": "exec_task_permits", "version": permits["policy_version"]}]
    d = _decide(task, _index_with(world, permits), "task_cr_export_aggregate", types, reasons, config)
    assert _prerequisite(d, "P-EXEC-OPERATION")["outcome"] == "missing"


def test_task_output_restriction_tightens(world, types, reasons, config):
    base = registry_doc("policies/output_cleanroom_aggregate_only")
    rules = [
        {**r, "permitted_destinations": ["dest_somewhere_else"]}
        for r in base["artifact_rules"]
        if r["artifact_type"] == "aggregate_report"
    ]
    narrowing = _task_policy("output_task_narrows", "output_cleanroom_aggregate_only", artifact_rules=rules)
    task = copy.deepcopy(example("task/task_cr_export_aggregate"))
    task["policy_refs"]["output"] = [{"id": "output_task_narrows", "version": narrowing["policy_version"]}]
    d = _decide(task, _index_with(world, narrowing), "task_cr_export_aggregate", types, reasons, config)
    assert d["verdict"] == "BLOCKED" and "destination_not_permitted" in codes(d)


FEATURE_MAP = {"id": "map_cookie_household_features", "version": "1.0.0"}
ACTIVATION_MAP = {"id": "map_cookie_household_activation", "version": "1.0.0"}
SNAPSHOT = {"id": "relsnap_cookie_household_2026_10", "version": "1.0.0"}


def _household_task(mapping_refs, snapshot_refs):
    task = copy.deepcopy(example("task/task_seed_affinity_score"))
    task["units"]["modeling_unit"] = task["units"]["output_unit"] = HOUSEHOLD
    task["units"]["mapping_refs"] = mapping_refs
    task["units"]["relationship_snapshot_refs"] = snapshot_refs
    return task


def test_approved_feature_mapping_with_available_snapshot_satisfies_grain(world, types, reasons, config):
    d = _decide(_household_task([FEATURE_MAP], [SNAPSHOT]), world, "task_seed_affinity_score", types, reasons, config)
    grain = _prerequisite(d, "P-GRAIN-COMPATIBLE")
    assert grain["outcome"] == "satisfied"
    assert "unit_mapping:map_cookie_household_features@1.0.0" in grain["evidence_refs"]
    assert d["verdict"] == "ELIGIBLE"


def test_mapping_without_relationship_snapshot_is_provisional(world, types, reasons, config):
    d = _decide(_household_task([FEATURE_MAP], []), world, "task_seed_affinity_score", types, reasons, config)
    assert d["verdict"] == "PROVISIONAL" and "missing_relationship_evidence" in codes(d)


def test_activation_only_mapping_cannot_build_features(world, types, reasons, config):
    d = _decide(
        _household_task([ACTIVATION_MAP], [SNAPSHOT]), world, "task_seed_affinity_score", types, reasons, config
    )
    assert d["verdict"] == "BLOCKED" and "mapping_use_not_permitted" in codes(d)


def _mapping_variant(world, mapping_changes=None, snapshot_changes=None):
    mapping = copy.deepcopy(example("unit_mapping/map_cookie_household_features"))
    snapshot = copy.deepcopy(example("relationship_snapshot/relsnap_cookie_household_2026_10"))
    mapping.update(mapping_changes or {})
    snapshot.update(snapshot_changes or {})
    kinds = ("execution_policy", "output_policy", "source_profile", "dataset_manifest", "objective")
    return DocumentIndex([d for k in kinds for d in world.all(k)] + [mapping, snapshot])


@pytest.mark.parametrize(
    "mapping_changes,snapshot_changes,verdict,code",
    [
        ({"mapping_state": "revoked"}, None, "BLOCKED", "mapping_revoked"),
        ({"mapping_state": "draft", "approval": None}, None, "PROVISIONAL", "missing_unit_mapping"),
        ({"effective_until": "2026-10-10T00:00:00Z"}, None, "PROVISIONAL", "missing_unit_mapping"),
        (None, {"snapshot_state": "revoked"}, "BLOCKED", "relationship_snapshot_revoked"),
        (None, {"available_at": "2026-11-01T00:00:00Z"}, "PROVISIONAL", "missing_relationship_evidence"),
        (
            None,
            {"observed_cardinality": {"max_targets_per_source": 3, "max_sources_per_target": 6}},
            "BLOCKED",
            "mapping_cardinality_mismatch",
        ),
        ({"tenant_id": "tenant_other"}, None, "BLOCKED", "tenant_scope_mismatch"),
    ],
)
def test_mapping_and_snapshot_conditions(
    world, types, reasons, config, mapping_changes, snapshot_changes, verdict, code
):
    documents = _mapping_variant(world, mapping_changes, snapshot_changes)
    d = _decide(
        _household_task([FEATURE_MAP], [SNAPSHOT]), documents, "task_seed_affinity_score", types, reasons, config
    )
    assert d["verdict"] == verdict and code in codes(d)


REMOTE_MODEL = {"id": "byom_lookalike_remote", "version": "1.0.0"}
LOCAL_MODEL = {"id": "propensity_logreg_v1", "version": "1.0.0"}


def _fact(pid, value=True, reason=None):
    return {
        "prerequisite_id": pid,
        "value": value,
        "established_by": "reviewer",
        "evidence_refs": [f"evidence_{pid.lower()}"],
        "reason_code": reason,
        "observed_at": "2026-10-10T00:00:00Z",
    }


def _remote_world(world, payload_permission="permitted", payload_type="feature_snapshot", model_changes=None):
    exec_ws = copy.deepcopy(registry_doc("policies/exec_workspace_demo"))
    template = exec_ws["operations"][0]
    exec_ws["operations"].append({**template, "operation": "remote_inference", "permission": "permitted"})
    out_ws = copy.deepcopy(registry_doc("policies/output_workspace_demo"))
    if payload_permission is not None:
        out_ws["artifact_rules"].append(
            {
                "artifact_type": payload_type,
                "permission": payload_permission,
                "permitted_output_type_ids": [],
                "permitted_destinations": ["endpoint_partner_lookalike"] if payload_permission == "permitted" else [],
            }
        )
    models = [
        copy.deepcopy(example("model_registration/model_byom_lookalike_remote")),
        example("model_registration/model_propensity_logreg_v1"),
    ]
    models[0].update(model_changes or {})
    kinds = ("execution_policy", "output_policy", "source_profile", "dataset_manifest", "objective")
    keep = [
        d
        for k in kinds
        for d in world.all(k)
        if d.get("policy_id") not in ("exec_workspace_demo", "output_workspace_demo")
    ]
    return DocumentIndex(keep + [exec_ws, out_ws, *models])


def _remote_task(operation="remote_inference", model_ref=REMOTE_MODEL):
    task = copy.deepcopy(example("task/task_seed_affinity_score"))
    task.update(operation=operation, model_ref=model_ref)
    return task


def _route_remote(task, documents, types, reasons, config, extra_facts=()):
    bundle = copy.deepcopy(example("evidence_bundle/bundle_task_seed_affinity_score"))
    bundle["task_ref"] = {"id": task["task_id"], "version": task["task_version"]}
    bundle["facts"] += list(extra_facts)
    return decide(task, documents=documents, bundle=bundle, types=types, reasons=reasons, config=config, now=NOW)


REMOTE_FACTS = [_fact("P-MODEL-FEATURES-AVAILABLE"), _fact("P-REMOTE-RECIPIENT-TERMS")]


def test_remote_lookalike_with_permitted_payload_is_eligible_without_validation(world, types, reasons, config):
    # Registration is not validation; a look-alike score keeps an exploratory claim, so no validation is required.
    d = _route_remote(_remote_task(), _remote_world(world), types, reasons, config, REMOTE_FACTS)
    assert d["verdict"] == "ELIGIBLE", codes(d)
    assert "P-MODEL-VALIDATED" not in [p["prerequisite_id"] for p in d["prerequisites"]]


def test_remote_inference_without_payload_permission_is_provisional(world, types, reasons, config):
    d = _route_remote(_remote_task(), _remote_world(world, None), types, reasons, config, REMOTE_FACTS)
    assert _prerequisite(d, "P-REMOTE-PAYLOAD")["outcome"] == "missing"
    assert d["verdict"] == "PROVISIONAL" and "missing_output_policy" in codes(d)


def test_prohibited_row_payload_blocks_remote_inference(world, types, reasons, config):
    d = _route_remote(_remote_task(), _remote_world(world, "prohibited"), types, reasons, config, REMOTE_FACTS)
    assert d["verdict"] == "BLOCKED" and "forbidden_row_level_egress" in codes(d)


def test_permitted_aggregate_payload_is_not_blocked_by_row_rules(world, types, reasons, config):
    endpoint = copy.deepcopy(example("model_registration/model_byom_lookalike_remote")["execution"])
    endpoint["endpoint"]["payload_artifact_type"] = "aggregate_report"
    documents = _remote_world(world, "permitted", "aggregate_report", {"execution": endpoint})
    d = _route_remote(_remote_task(), documents, types, reasons, config, REMOTE_FACTS)
    assert _prerequisite(d, "P-REMOTE-PAYLOAD")["outcome"] == "satisfied"


def test_recipient_terms_must_be_confirmed(world, types, reasons, config):
    d = _route_remote(_remote_task(), _remote_world(world), types, reasons, config, REMOTE_FACTS[:1])
    assert d["verdict"] == "PROVISIONAL" and "recipient_terms_unverified" in codes(d)


@pytest.mark.parametrize(
    "operation,model_ref,model_changes,verdict,code",
    [
        ("score", REMOTE_MODEL, None, "BLOCKED", "model_execution_mismatch"),  # endpoint model scored as local
        ("remote_inference", None, None, "PROVISIONAL", "missing_model_registration"),
        ("remote_inference", REMOTE_MODEL, {"registration_state": "revoked"}, "BLOCKED", "model_registration_revoked"),
        (
            "remote_inference",
            REMOTE_MODEL,
            {"registration_state": "suspended"},
            "PROVISIONAL",
            "model_registration_not_current",
        ),
        (
            "remote_inference",
            REMOTE_MODEL,
            {"valid_until": "2026-10-12T00:00:00Z"},
            "PROVISIONAL",
            "model_registration_not_current",
        ),
        ("remote_inference", REMOTE_MODEL, {"tenant_id": "tenant_other"}, "BLOCKED", "tenant_scope_mismatch"),
        ("score", LOCAL_MODEL, None, "BLOCKED", "model_contract_mismatch"),  # propensity model on a look-alike task
    ],
)
def test_model_registration_conditions(
    world, types, reasons, config, operation, model_ref, model_changes, verdict, code
):
    task = _remote_task(operation, model_ref)
    d = _route_remote(task, _remote_world(world, model_changes=model_changes), types, reasons, config, REMOTE_FACTS)
    assert d["verdict"] == verdict and code in codes(d), codes(d)


def test_in_boundary_model_cannot_be_called_remotely(world, types, reasons, config):
    task = copy.deepcopy(example("task/task_propensity_train_no_labels"))
    task.update(operation="remote_inference", model_ref=LOCAL_MODEL, requested_artifact="score_file")
    d = _route_remote(task, _remote_world(world), types, reasons, config, REMOTE_FACTS)
    assert d["verdict"] == "BLOCKED" and "model_execution_mismatch" in codes(d)


def test_existing_registered_model_inference_needs_no_labels(world, types, reasons, config):
    task = copy.deepcopy(example("task/task_propensity_train_no_labels"))
    task.update(operation="infer", model_ref=LOCAL_MODEL, requested_artifact="score_file")
    facts = [
        _fact(p)
        for p in ("P-MODEL-VALIDATED", "P-POPULATION-COMPATIBLE", "P-FEATURE-TIMING", "P-MODEL-FEATURES-AVAILABLE")
    ]
    exec_ws = copy.deepcopy(registry_doc("policies/exec_workspace_demo"))
    exec_ws["operations"].append({**exec_ws["operations"][0], "operation": "infer", "permission": "permitted"})
    kinds = ("output_policy", "source_profile", "dataset_manifest", "objective")
    docs = DocumentIndex(
        [d for k in kinds for d in world.all(k)]
        + [p for p in world.all("execution_policy") if p["policy_id"] != "exec_workspace_demo"]
        + [exec_ws, example("model_registration/model_propensity_logreg_v1")]
    )
    bundle = copy.deepcopy(example("evidence_bundle/bundle_task_propensity_train_no_labels"))
    bundle["facts"] = [f for f in bundle["facts"] if f["prerequisite_id"] != "P-LABELS-QUALIFIED"] + facts
    d = decide(task, documents=docs, bundle=bundle, types=types, reasons=reasons, config=config, now=NOW)
    assert _prerequisite(d, "P-MODEL-REGISTERED")["outcome"] == "satisfied"
    assert "P-LABELS-QUALIFIED" not in [p["prerequisite_id"] for p in d["prerequisites"]]
    assert d["verdict"] == "ELIGIBLE", codes(d)
