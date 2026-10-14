from datetime import timedelta

import pytest
from conftest import NOW, ROOT

from aip.agents import (
    ActorContext,
    GatewayError,
    NullReasoningModel,
    ScriptedReasoningModel,
    ToolGateway,
    ToolSpec,
    make_proposal,
)
from aip.evaluation import load_suite, run_router, score
from aip.evaluation.routing_benchmark import Prediction
from aip.registry import DocumentIndex
from aip.routing import RouterConfig, decide

SUITE = ROOT / "fixtures" / "routing" / "development"


def gateway(seen):
    def read(tenant, args):
        seen.append(tenant)
        return {"artifact": args["artifact_id"]}

    return ToolGateway(
        {
            "read_artifact": ToolSpec("read_artifact", read),
            "submit_job": ToolSpec("submit_job", lambda t, a: "job", cost_units=5),
        }
    )


def test_gateway_enforces_allowlist_tenant_and_budget():
    seen = []
    gw = gateway(seen)
    ctx = ActorContext(tenant_id="tenant_demo", role="fitness", budget_units=2)
    assert gw.call(ctx, "read_artifact", {"artifact_id": "a1"}) == {"artifact": "a1"} and seen == ["tenant_demo"]
    with pytest.raises(GatewayError):
        gw.call(ctx, "submit_job", {})
    gw.call(ctx, "read_artifact", {"artifact_id": "a2"})
    with pytest.raises(GatewayError, match="budget_exceeded"):
        gw.call(ctx, "read_artifact", {"artifact_id": "a3"})
    assert [e["outcome"] for e in ctx.audit] == ["allowed", "denied_tool", "allowed", "denied_budget"]


def test_injected_authority_fields_are_rejected():
    gw = gateway([])
    ctx = ActorContext(tenant_id="tenant_demo", role="fitness", budget_units=10)
    with pytest.raises(GatewayError, match="authority"):
        gw.call(ctx, "read_artifact", {"artifact_id": "a1", "note": {"tenant_id": "tenant_other"}})


def test_proposals_are_advisory_and_use_registry_codes(reasons):
    raw = ScriptedReasoningModel(
        [{"proposed_verdict": "BLOCKED", "proposed_reasons": [{"code": "temporal_leakage"}]}]
    ).propose("fitness", {})
    p = make_proposal(
        proposal_id="p1",
        task_ref={"id": "t", "version": "1.0.0"},
        role="fitness",
        provider="scripted",
        model_id="scripted",
        prompt_template_ref={"id": "tmpl", "version": "1"},
        input_refs=[],
        raw=raw,
        reasons=reasons,
        now=NOW,
    )
    assert p["authority"] == "advisory"
    with pytest.raises(ValueError):
        make_proposal(
            proposal_id="p2",
            task_ref={"id": "t", "version": "1.0.0"},
            role="fitness",
            provider="x",
            model_id="x",
            prompt_template_ref={"id": "tmpl", "version": "1"},
            input_refs=[],
            raw={"proposed_verdict": "BLOCKED", "proposed_reasons": [{"code": "budget_exceeded"}]},
            reasons=reasons,
            now=NOW,
        )
    assert NullReasoningModel().propose("fitness", {})["proposed_verdict"] == "PROVISIONAL"


def test_rules_router_on_development_suite(types, reasons):
    cases = load_suite(SUITE)
    index = DocumentIndex()
    index.add_paths(
        sorted((ROOT / "registry" / "policies").glob("*.json"))
        + sorted((ROOT / "registry" / "profiles").glob("*.json"))
    )
    index.add_paths(sorted((SUITE / "world").glob("*.json")))
    config = RouterConfig(max_decision_ttl=timedelta(days=7))
    result = score(
        cases,
        run_router(
            cases,
            lambda t, b: decide(t, documents=index, bundle=b, types=types, reasons=reasons, config=config, now=NOW),
        ),
    )
    assert result["verdict_and_reason_accuracy"] == 1.0 and result["critical_false_safe_rate"] == 0.0


def test_reject_all_and_approve_all_routers_cannot_pass():
    cases = load_suite(SUITE)
    reject_all = score(cases, [Prediction(c.case["case_id"], "BLOCKED", ()) for c in cases])
    approve_all = score(cases, [Prediction(c.case["case_id"], "ELIGIBLE", ()) for c in cases])
    assert reject_all["false_block_rate"] == 1.0 and reject_all["verdict_accuracy"] < 0.5
    assert approve_all["critical_false_safe_rate"] == 1.0 and approve_all["premature_clearance_rate"] == 1.0
