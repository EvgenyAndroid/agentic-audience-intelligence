import copy

import pytest
from conftest import NOW, example

from aip.exchange import AdcpListingConfig, UnsupportedMapping, build_activation_request, build_signal
from aip.representation import check_compatibility, evaluate_gts

REP = example("representation_descriptor/rep_semantic_direct")
PSEUDO = example("representation_descriptor/rep_vac_pseudo_nonsemantic")
CFG = AdcpListingConfig(
    "https://signals.example.invalid/agent",
    "custom",
    {"prof_web_events_ref": ["web_usage"]},
    seed_source_type="behavioral",
    training_data_jurisdictions=["US"],
    ai_act_risk_class="minimal",
)


def test_direct_compatibility_and_dimension_only_match():
    assert check_compatibility(REP, REP, NOW).outcome == "satisfied"
    other = copy.deepcopy(REP)
    other.update(space_id="another-space-d512", descriptor_id="rep_other")
    out = check_compatibility(REP, other, NOW)
    assert out.outcome == "violated" and out.reason_code == "representation_incompatible"


def test_pseudo_vectors_never_support_semantic_similarity():
    assert check_compatibility(REP, PSEUDO, NOW).reason_code == "representation_nonsemantic"


def test_projector_needs_alignment_evidence():
    other = copy.deepcopy(REP)
    other.update(space_id="another-space-d512", descriptor_id="rep_other")
    other["alignment"] = {
        "route": "projector",
        "projector_ref": {"id": "proj_1", "version": "1.0.0"},
        "alignment_evidence_ref": {"id": "gts_run_1", "version": "1.0.0"},
    }
    assert check_compatibility(REP, other, NOW).outcome == "satisfied"


def test_gts_bands():
    gts = example("alignment_test_set/gts_demo")
    sims = {("cnt_prog_cooking_17", "cnt_url_8842"): 0.71, ("cnt_url_8842", "cnt_url_9910"): 0.12}
    report = evaluate_gts(gts, lambda a, b: sims[(a, b)])
    assert report["all_passed"]
    assert not evaluate_gts(gts, lambda a, b: 0.4)["all_passed"]


def _inputs():
    return (
        example("release_manifest/release_prepared"),
        example("evidence_card/card_seed_affinity_exploratory"),
        example("objective/obj_seed_affinity_web"),
    )


def test_signal_validates_against_pinned_adcp_schema():
    signal = build_signal(*_inputs(), CFG)
    assert signal["value_type"] == "binary" and signal["audience_expansion"] is True
    assert signal["ext"]["aip"]["claim"] == {"type": "seed_affinity", "qualifier": "exploratory"}


def test_modeling_block_is_omitted_without_a_declared_seed_source():
    cfg = AdcpListingConfig("https://signals.example.invalid/agent", "custom", {"prof_web_events_ref": ["web_usage"]})
    assert "modeling" not in build_signal(*_inputs(), cfg)


def test_unsupported_claims_and_undeclared_data_sources_are_refused():
    manifest, card, objective = _inputs()
    agg = copy.deepcopy(card)
    agg["claim"] = {"type": "aggregate_measurement", "qualifier": "exploratory"}
    with pytest.raises(UnsupportedMapping):
        build_signal(manifest, agg, objective, CFG)
    with pytest.raises(UnsupportedMapping):
        build_signal(
            manifest, card, objective, AdcpListingConfig("https://signals.example.invalid/agent", "custom", {})
        )


def test_activation_request_enforces_idempotency_key_format():
    signal = build_signal(*_inputs(), CFG)
    assert build_activation_request(signal, [{"type": "platform", "platform": "demo-dsp"}], "idem_activation_0001_demo")
    with pytest.raises(UnsupportedMapping):
        build_activation_request(signal, [{"type": "platform", "platform": "demo-dsp"}], "short")
