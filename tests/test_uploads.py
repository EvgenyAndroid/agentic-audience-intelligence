"""Stage B uploads: intake limits, column profiling, confirmation checks and routing of uploaded data."""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime

import numpy as np
import pytest

from aip import uploads

NOW = datetime(2026, 10, 15, 12, tzinfo=UTC)


def make_csv(n: int = 600, *, seed_count: int = 60, outcome_rate: float = 0.25, rng_seed: int = 7) -> bytes:
    rng = np.random.default_rng(rng_seed)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "customer_id",
            "orders_12m",
            "aov",
            "email_open_rate",
            "loyalty",
            "age_band_sensitive",
            "is_seed",
            "engaged_pattern",
            "purchased",
            "region",
        ]
    )
    for i in range(n):
        writer.writerow(
            [
                f"c{i:05d}",
                int(rng.integers(0, 20)),
                round(float(rng.normal(80, 20)), 2),
                "" if i % 17 == 0 else round(float(rng.random()), 3),
                int(rng.random() < 0.4),
                int(rng.random() < 0.5),
                int(i < seed_count),
                int(rng.random() < 0.2),
                int(rng.random() < outcome_rate),
                ["North", "South", "East", "West"][i % 4],
            ]
        )
    return buf.getvalue().encode()


def confirm(**overrides: object) -> uploads.Confirmation:
    base: dict[str, object] = dict(
        title="Customers",
        unit_type="person_key",
        unit_label="Customer",
        key_column="customer_id",
        observation_start="2026-07-01",
        observation_end="2026-09-30",
        collection_method="transaction_record",
        seed_column="is_seed",
        behavior_column="engaged_pattern",
        behavior_features=("orders_12m", "email_open_rate"),
        outcome_column="purchased",
        breakdown_column="region",
        sensitive_columns=("age_band_sensitive",),
        rights_attested=True,
        timing_attested=True,
    )
    base.update(overrides)
    return uploads.Confirmation(**base)  # type: ignore[arg-type]


def test_parse_and_profile() -> None:
    table = uploads.parse_csv(make_csv())
    assert len(table.rows) == 600 and table.sha256.startswith("sha256:")
    kinds = {p.name: p.kind for p in uploads.profile_columns(table)}
    assert kinds == {
        "customer_id": "identifier",
        "orders_12m": "count",
        "aov": "score",
        "email_open_rate": "share",
        "loyalty": "binary",
        "age_band_sensitive": "binary",
        "is_seed": "binary",
        "engaged_pattern": "binary",
        "purchased": "binary",
        "region": "category",
    }
    profiles = {p.name: p for p in uploads.profile_columns(table)}
    assert profiles["email_open_rate"].missing_rate == pytest.approx(36 / 600)
    assert profiles["region"].values == ("East", "North", "South", "West")
    # Values are only reported for small categorical columns, never for keys or numbers.
    assert profiles["customer_id"].values == () and profiles["aov"].values == ()


def test_suggested_roles_come_from_names_and_kinds() -> None:
    roles = uploads.suggest_roles(uploads.profile_columns(uploads.parse_csv(make_csv())))
    assert roles == {
        "key_column": "customer_id",
        "seed_column": "is_seed",
        "behavior_column": "engaged_pattern",
        "outcome_column": "purchased",
        "breakdown_column": "region",
    }


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        (b"", "empty"),
        (b"a,a\n" + b"1,2\n" * 60, "distinct"),
        (b"a,b\n" + b"1,2\n" * 10, "at least 50"),
        (b"a,b\n" + b"1,2\n" * 60 + b"1,2,3\n", "fields"),
        (b"\xff\xfe" + b"a,b\n", "UTF-8"),
    ],
)
def test_parse_rejects_bad_files(raw: bytes, message: str) -> None:
    with pytest.raises(uploads.UploadError, match=message):
        uploads.parse_csv(raw)


def test_parse_rejects_oversized_files(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(uploads, "MAX_BYTES", 100)
    with pytest.raises(uploads.UploadError, match="larger"):
        uploads.parse_csv(make_csv())


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"unit_type": "not_a_type"}, "Unknown record type"),
        ({"key_column": "region"}, "key column"),
        ({"seed_column": "aov"}, "yes/no"),
        ({"breakdown_column": "aov"}, "breakdown"),
        ({"seed_column": None, "behavior_column": None, "outcome_column": None}, "at least one"),
        ({"behavior_features": ("nope",)}, "not in the file"),
        ({"collection_method": "telepathy"}, "collection method"),
    ],
)
def test_prepare_rejects_inconsistent_confirmations(overrides: dict[str, object], message: str) -> None:
    with pytest.raises(uploads.UploadError, match=message):
        uploads.prepare(uploads.parse_csv(make_csv()), confirm(**overrides), "up_000000000001")


def test_small_seed_is_rejected() -> None:
    with pytest.raises(uploads.UploadError, match="fewer than 20"):
        uploads.prepare(uploads.parse_csv(make_csv(seed_count=5)), confirm(), "up_000000000001")


def test_prepare_builds_features_and_excludes_sensitive_columns() -> None:
    prep = uploads.prepare(uploads.parse_csv(make_csv()), confirm(), "up_000000000001")
    names = [f.name for f in prep.spec.features]
    assert names == ["orders_12m", "aov", "email_open_rate", "loyalty", "age_band_sensitive"]
    assert [f.name for f in prep.spec.features if f.sensitive] == ["age_band_sensitive"]
    assert prep.spec.methods == ("lookalike", "actalike", "propensity")
    assert len(prep.data.seed) == 60 and np.isnan(prep.data.x[0, names.index("email_open_rate")])
    assessment = uploads.assessment(prep)
    assert assessment["sensitive_excluded"] == ["age_band_sensitive"]


def verdicts(bundle: dict[str, object]) -> dict[str, str]:
    return {k: v["decision"]["verdict"] for k, v in bundle["decisions"].items()}  # type: ignore[attr-defined]


def test_attested_upload_is_eligible() -> None:
    table = uploads.parse_csv(make_csv())
    bundle = uploads.route(uploads.prepare(table, confirm(), "up_000000000001"), table, tenant_id="tenant_a", now=NOW)
    assert verdicts(bundle) == {
        "lookalike": "ELIGIBLE",
        "actalike": "ELIGIBLE",
        "propensity": "ELIGIBLE",
        "export_rows": "ELIGIBLE",
    }
    docs = bundle["documents"]
    assert docs["source_profile"]["tenant_id"] == "tenant_a"
    assert docs["dataset_manifest"]["snapshot"]["sha256"] == table.sha256
    assert bundle["recommendation"]["recommended_options"]


def test_unattested_rights_and_timing_hold_methods_provisional() -> None:
    table = uploads.parse_csv(make_csv())
    prep = uploads.prepare(table, confirm(rights_attested=False, timing_attested=False), "up_000000000001")
    bundle = uploads.route(prep, table, tenant_id="tenant_a", now=NOW)
    v = verdicts(bundle)
    assert v["lookalike"] == v["actalike"] == v["propensity"] == "PROVISIONAL"
    codes = {r["code"] for r in bundle["decisions"]["lookalike"]["decision"]["reasons"]}
    assert codes == {"unverified_permission", "missing_availability_evidence"}


def test_too_few_outcome_positives_hold_propensity_provisional() -> None:
    table = uploads.parse_csv(make_csv(outcome_rate=0.05))
    bundle = uploads.route(uploads.prepare(table, confirm(), "up_000000000001"), table, tenant_id="tenant_a", now=NOW)
    assert verdicts(bundle)["propensity"] == "PROVISIONAL"
    assert bundle["assessment"]["outcome"]["qualified"] is False


def test_cleanroom_blocks_row_export() -> None:
    table = uploads.parse_csv(make_csv())
    prep = uploads.prepare(table, confirm(location="cleanroom"), "up_000000000001")
    v = verdicts(uploads.route(prep, table, tenant_id="tenant_a", now=NOW))
    assert v["export_rows"] == "BLOCKED" and v["export_aggregate"] == "ELIGIBLE"


def test_policies_are_issued_per_tenant() -> None:
    a, b = uploads.tenant_policies("tenant_a", NOW), uploads.tenant_policies("tenant_b", NOW)
    assert {p["tenant_id"] for p in a} == {"tenant_a"} and {p["tenant_id"] for p in b} == {"tenant_b"}
    assert len(a) == len(uploads.UPLOAD_POLICIES)


@pytest.mark.parametrize("method", ["lookalike", "actalike", "propensity"])
def test_build_trains_and_evaluates_on_heldout_records(method: str) -> None:
    prep = uploads.prepare(uploads.parse_csv(make_csv()), confirm(), "up_000000000001")
    result = uploads.build(prep, method)
    assert len(result["models"]) == 2 and result["recommended"]["model_id"] in {m["model_id"] for m in result["models"]}
    for model in result["models"]:
        assert len(model["scores"]) == 600 and "_scores" not in model
    held = set(result["heldout"])
    assert held and result["fit_count"] > 0
    if method == "propensity":
        assert {"average_precision", "brier", "log_loss"} <= set(result["models"][0]["evaluation"])
    else:
        # records used to fit are never scored, so they cannot count toward held-out recall
        scored = {i for i, s in enumerate(result["models"][0]["scores"]) if s is not None}
        assert held <= scored | held and "0.1" in result["models"][0]["evaluation"]["recall_at"]


def test_build_rejects_methods_the_upload_does_not_support() -> None:
    prep = uploads.prepare(uploads.parse_csv(make_csv()), confirm(behavior_column=None), "up_000000000001")
    with pytest.raises(uploads.UploadError, match="not a method"):
        uploads.build(prep, "actalike")


def test_route_carries_keys_and_breakdown_codes_for_export() -> None:
    table = uploads.parse_csv(make_csv())
    bundle = uploads.route(uploads.prepare(table, confirm(), "up_000000000001"), table, tenant_id="tenant_a", now=NOW)
    ds = bundle["dataset"]
    assert ds["key_field"] == "customer_id" and ds["keys"][:2] == ["c00000", "c00001"]
    assert len(ds["breakdown"]["codes"]) == 600 and bundle["aggregate_rules"] is None


def universe_csv(raw: bytes, *, prefix: str = "u", drop: tuple[str, ...] = ()) -> bytes:
    """The same columns with new keys (and optionally some columns removed)."""
    rows = list(csv.reader(io.StringIO(raw.decode())))
    keep = [j for j, c in enumerate(rows[0]) if c not in drop]
    buf = io.StringIO()
    writer = csv.writer(buf)
    for i, row in enumerate(rows):
        cells = [f"{prefix}{c[1:]}" if j == 0 and i else c for j, c in enumerate(row)]
        writer.writerow([cells[j] for j in keep])
    return buf.getvalue().encode()


@pytest.mark.parametrize("method", ["lookalike", "actalike", "propensity"])
def test_expand_scores_a_universe_with_the_models_build_evaluated(method: str) -> None:
    table = uploads.parse_csv(make_csv())
    prep = uploads.prepare(table, confirm(), "up_000000000001")
    built = uploads.build(prep, method)
    # The upload itself as the universe: records already positive are left out, every other record gets the
    # score build gave it, so the expansion uses the very models the held-out evaluation describes.
    same = uploads.expand(prep, table, uploads.read_universe(prep, table), method)
    positive = {"lookalike": prep.data.seed, "actalike": prep.data.behavior}.get(method)
    if positive is None:
        assert prep.data.outcome is not None
        positive = np.flatnonzero(prep.data.outcome)
    assert same["rows"] == 600 and same["excluded"] == len(positive)
    for b, e in zip(built["models"], same["models"], strict=True):
        assert b["model_id"] == e["model_id"] and set(e["drivers"]) == {"0.01", "0.05", "0.1", "0.2", "0.5"}
        for i, (bs, es) in enumerate(zip(b["scores"], e["scores"], strict=True)):
            assert es is None if i in set(positive) else es == bs


def test_universe_with_new_keys_and_no_sensitive_column() -> None:
    raw = make_csv()
    table = uploads.parse_csv(raw)
    prep = uploads.prepare(table, confirm(), "up_000000000001")
    universe = uploads.read_universe(
        prep, uploads.parse_csv(universe_csv(make_csv(900, rng_seed=11), drop=("age_band_sensitive", "is_seed")))
    )
    assert universe.keys[0] == "u00000" and universe.breakdown is not None and len(universe.breakdown) == 900
    out = uploads.expand(prep, table, universe, "lookalike")
    assert out["excluded"] == 0 and out["rows"] == 900
    assert sum(s is not None for s in out["models"][0]["scores"]) > 800


@pytest.mark.parametrize(
    ("drop", "message"),
    [(("aov",), "missing columns the models need: aov"), (("customer_id",), "missing columns")],
)
def test_universe_needs_the_key_and_every_model_feature(drop: tuple[str, ...], message: str) -> None:
    table = uploads.parse_csv(make_csv())
    prep = uploads.prepare(table, confirm(), "up_000000000001")
    with pytest.raises(uploads.UploadError, match=message):
        uploads.read_universe(prep, uploads.parse_csv(universe_csv(make_csv(), drop=drop)))


def test_universe_rejects_non_numeric_features() -> None:
    table = uploads.parse_csv(make_csv())
    prep = uploads.prepare(table, confirm(), "up_000000000001")
    bad = universe_csv(make_csv()).replace(b"\nu00003,", b"\nu00003,lots", 1)
    with pytest.raises(uploads.UploadError, match="not a number"):
        uploads.read_universe(prep, uploads.parse_csv(bad))
