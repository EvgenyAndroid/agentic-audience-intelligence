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
