"""Stage B HTTP API: invite keys, tenant isolation, the upload -> assess -> route flow, deletion and retention."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi", reason="the api extra is not installed")

from fastapi.testclient import TestClient  # noqa: E402
from test_uploads import make_csv  # noqa: E402

from aip.api.app import create_app, hash_key  # noqa: E402
from aip.uploads.store import Store  # noqa: E402

KEY_A, KEY_B = "aai_key_for_a", "aai_key_for_b"
ORIGIN = "https://audiences.nofluffadvisory.com"
CONFIRMATION: dict[str, Any] = {
    "title": "Customers",
    "unit_type": "person_key",
    "unit_label": "Customer",
    "key_column": "customer_id",
    "observation_start": "2026-07-01",
    "observation_end": "2026-09-30",
    "collection_method": "transaction_record",
    "seed_column": "is_seed",
    "behavior_column": "engaged_pattern",
    "behavior_features": ["orders_12m", "email_open_rate"],
    "outcome_column": "purchased",
    "breakdown_column": "region",
    "sensitive_columns": ["age_band_sensitive"],
    "rights_attested": True,
    "timing_attested": True,
}


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 15, 12, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def client(tmp_path: Path, clock: Clock) -> TestClient:
    app = create_app(
        store=Store(tmp_path / "store", timedelta(hours=24)),
        keys={hash_key(KEY_A): "tenant_a", hash_key(KEY_B): "tenant_b"},
        allowed_origins=[ORIGIN],
        now=clock,
    )
    return TestClient(app)


def auth(key: str = KEY_A) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


def upload(client: TestClient, key: str = KEY_A) -> str:
    r = client.post("/v1/datasets", content=make_csv(), headers={**auth(key), "Content-Type": "text/csv"})
    assert r.status_code == 201, r.text
    return str(r.json()["dataset_id"])


def test_health_needs_no_key(client: TestClient) -> None:
    assert client.get("/healthz").json()["status"] == "ok"


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer wrong"}, {"Authorization": "Basic x"}])
def test_requests_without_a_valid_key_are_refused(client: TestClient, headers: dict[str, str]) -> None:
    assert client.post("/v1/datasets", content=make_csv(), headers=headers).status_code == 401
    assert client.get("/v1/record-types", headers=headers).status_code == 401


def test_upload_assess_route(client: TestClient) -> None:
    r = client.post("/v1/datasets", content=make_csv(), headers={**auth(), "Content-Type": "text/csv"})
    body = r.json()
    assert r.status_code == 201
    assert body["rows"] == 600 and body["suggested_roles"]["key_column"] == "customer_id"
    assert body["expires_at"] == "2026-10-16T12:00:00Z"
    dataset_id = body["dataset_id"]

    assert client.post(f"/v1/datasets/{dataset_id}/route", headers=auth()).status_code == 409

    r = client.post(f"/v1/datasets/{dataset_id}/assess", json=CONFIRMATION, headers=auth())
    assert r.status_code == 200, r.text
    assert r.json()["assessment"]["sensitive_excluded"] == ["age_band_sensitive"]

    r = client.post(f"/v1/datasets/{dataset_id}/route", headers=auth())
    assert r.status_code == 200, r.text
    bundle = r.json()
    assert {k: v["decision"]["verdict"] for k, v in bundle["decisions"].items()} == {
        "lookalike": "ELIGIBLE",
        "actalike": "ELIGIBLE",
        "propensity": "ELIGIBLE",
        "export_rows": "ELIGIBLE",
    }
    assert bundle["manifest"]["synthetic"] is False

    stored = client.get(f"/v1/datasets/{dataset_id}", headers=auth()).json()
    assert stored["confirmation"]["title"] == "Customers" and stored["bundle"]["decisions"]


def test_invalid_confirmation_is_a_422_with_a_readable_message(client: TestClient) -> None:
    dataset_id = upload(client)
    r = client.post(f"/v1/datasets/{dataset_id}/assess", json={**CONFIRMATION, "key_column": "region"}, headers=auth())
    assert r.status_code == 422 and "key column" in r.json()["error"]
    r = client.post(f"/v1/datasets/{dataset_id}/assess", json={**CONFIRMATION, "location": "moon"}, headers=auth())
    assert r.status_code == 422


def test_a_bad_file_is_a_422(client: TestClient) -> None:
    r = client.post("/v1/datasets", content=b"a,b\n1,2\n", headers=auth())
    assert r.status_code == 422 and "at least 50" in r.json()["error"]


def test_tenants_cannot_see_each_others_uploads(client: TestClient) -> None:
    dataset_id = upload(client, KEY_A)
    assert client.get(f"/v1/datasets/{dataset_id}", headers=auth(KEY_B)).status_code == 404
    assert client.post(f"/v1/datasets/{dataset_id}/assess", json=CONFIRMATION, headers=auth(KEY_B)).status_code == 404
    assert client.delete(f"/v1/datasets/{dataset_id}", headers=auth(KEY_B)).status_code == 404
    assert client.get(f"/v1/datasets/{dataset_id}", headers=auth(KEY_A)).status_code == 200


def test_ids_outside_the_pattern_are_not_found(client: TestClient) -> None:
    assert client.get("/v1/datasets/..%2F..%2Fetc", headers=auth()).status_code == 404
    assert client.get("/v1/datasets/up_zzzzzzzzzzzz", headers=auth()).status_code == 404


def test_delete_removes_the_upload(client: TestClient) -> None:
    dataset_id = upload(client)
    assert client.delete(f"/v1/datasets/{dataset_id}", headers=auth()).status_code == 204
    assert client.get(f"/v1/datasets/{dataset_id}", headers=auth()).status_code == 404


def test_uploads_expire_after_retention(client: TestClient, clock: Clock) -> None:
    dataset_id = upload(client)
    clock.now += timedelta(hours=23)
    assert client.get(f"/v1/datasets/{dataset_id}", headers=auth()).status_code == 200
    clock.now += timedelta(hours=1)
    assert client.get(f"/v1/datasets/{dataset_id}", headers=auth()).status_code == 404


def test_record_types_and_cors(client: TestClient) -> None:
    types = client.get("/v1/record-types", headers=auth()).json()
    assert {"type_id": "person_key", "label": "Person key", "grain": "person"} in list(types)
    r = client.options(
        "/v1/datasets",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert r.headers["access-control-allow-origin"] == ORIGIN
    r = client.options(
        "/v1/datasets", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"}
    )
    assert "access-control-allow-origin" not in r.headers


def routed(client: TestClient, **overrides: Any) -> str:
    dataset_id = upload(client)
    assert (
        client.post(f"/v1/datasets/{dataset_id}/assess", json={**CONFIRMATION, **overrides}, headers=auth()).status_code
        == 200
    )
    assert client.post(f"/v1/datasets/{dataset_id}/route", headers=auth()).status_code == 200
    return dataset_id


def test_build_needs_a_route_first(client: TestClient) -> None:
    dataset_id = upload(client)
    assert client.post(f"/v1/datasets/{dataset_id}/build/lookalike", headers=auth()).status_code == 409


def test_build_refuses_a_method_the_router_did_not_make_eligible(client: TestClient) -> None:
    dataset_id = routed(client, timing_attested=False)
    r = client.post(f"/v1/datasets/{dataset_id}/build/lookalike", headers=auth())
    assert r.status_code == 409 and "PROVISIONAL" in r.json()["detail"]
    assert client.post(f"/v1/datasets/{dataset_id}/build/export_rows", headers=auth()).status_code == 404


def test_build_scores_an_eligible_method_and_stores_it(client: TestClient) -> None:
    dataset_id = routed(client)
    r = client.post(f"/v1/datasets/{dataset_id}/build/propensity", headers=auth())
    assert r.status_code == 200, r.text
    assert r.json()["result"]["recommended"]["model_id"] in {"logistic", "boosted"}
    stored = client.get(f"/v1/datasets/{dataset_id}", headers=auth()).json()["bundle"]
    assert set(stored["results"]) == {"propensity"}
    assert client.post(f"/v1/datasets/{dataset_id}/build/lookalike", headers=auth(KEY_B)).status_code == 404


def put_universe(client: TestClient, dataset_id: str, *, attested: bool = True, key: str = KEY_A) -> Any:
    flag = "true" if attested else "false"
    return client.post(
        f"/v1/datasets/{dataset_id}/universe?rights_attested={flag}",
        content=make_csv(800, rng_seed=5).replace(b"\nc", b"\nu"),
        headers={**auth(key), "Content-Type": "text/csv"},
    )


def test_universe_needs_a_confirmation_and_an_attestation(client: TestClient) -> None:
    dataset_id = upload(client)
    assert put_universe(client, dataset_id).status_code == 409
    dataset_id = routed(client)
    r = put_universe(client, dataset_id, attested=False)
    assert r.status_code == 422 and "right to use" in r.json()["detail"]
    r = put_universe(client, dataset_id)
    assert r.status_code == 201 and r.json()["rows"] == 800 and r.json()["breakdown"] is True


def test_expand_needs_a_universe_and_an_eligible_method(client: TestClient) -> None:
    dataset_id = routed(client)
    assert client.post(f"/v1/datasets/{dataset_id}/expand/lookalike", headers=auth()).status_code == 409
    provisional = routed(client, timing_attested=False)
    assert put_universe(client, provisional).status_code == 201
    r = client.post(f"/v1/datasets/{provisional}/expand/lookalike", headers=auth())
    assert r.status_code == 409 and "PROVISIONAL" in r.json()["detail"]


def test_expand_scores_the_universe_for_every_modeled_method(client: TestClient) -> None:
    dataset_id = routed(client)
    assert put_universe(client, dataset_id).status_code == 201
    for method in ("lookalike", "actalike", "propensity"):
        r = client.post(f"/v1/datasets/{dataset_id}/expand/{method}", headers=auth())
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["keys"][0] == "u00000" and len(body["breakdown_codes"]) == 800
        assert len(body["result"]["models"]) == 2 and len(body["result"]["models"][0]["scores"]) == 800
    assert client.post(f"/v1/datasets/{dataset_id}/expand/lookalike", headers=auth(KEY_B)).status_code == 404
