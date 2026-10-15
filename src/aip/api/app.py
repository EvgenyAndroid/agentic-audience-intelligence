"""The stage B API: upload a CSV, confirm what it holds, and have the router decide every method.

Endpoints (all under /v1, all requiring ``Authorization: Bearer <invite key>``):

  POST   /v1/datasets               body: the CSV (text/csv). Stores it, returns the column profile and
                                    suggested roles. Nothing is modeled or routed yet.
  POST   /v1/datasets/{id}/assess   body: the confirmation (roles, record type, sensitive columns,
                                    attestations). Returns the rule-based assessment.
  POST   /v1/datasets/{id}/route    Decides every task and ranks the methods; returns the bundle.
  POST   /v1/datasets/{id}/build/{method}
                                    Trains and scores one ELIGIBLE method; returns its models, held-out
                                    evaluation and the recommended model.
  POST   /v1/datasets/{id}/universe?rights_attested=true
                                    body: a second CSV of new records with the same key and feature columns.
                                    Kept with the upload, to expand audiences into.
  POST   /v1/datasets/{id}/expand/{method}
                                    Scores the universe with an ELIGIBLE method's models, fit on the upload.
  GET    /v1/datasets/{id}          The stored profile, confirmation and bundle, if any.
  DELETE /v1/datasets/{id}          Deletes the upload and everything derived from it.
  GET    /v1/record-types           Record types an upload can declare.

Invite keys are never stored: ``AIP_API_KEYS`` maps the SHA-256 of each key to its tenant id (``aip api-key``
issues one). Uploads are kept for ``AIP_RETENTION_HOURS`` (default 24; the live demo sets 1) at most, swept every
minute, row values are never logged,
and nothing here calls a language model.
"""

# No `from __future__ import annotations`: FastAPI resolves the local `Tenant` dependency alias at runtime.
import hashlib
import hmac
import json
import os
import threading
import time
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from aip import __version__, paths, uploads
from aip.registry import TypeRegistry
from aip.timeutil import format_ts, utcnow
from aip.uploads.store import MAX_DATASETS_PER_TENANT, NotFound, Store
from aip.workbench import documents as docs

Name = Annotated[str, Field(min_length=1, max_length=128)]
Label = Annotated[str, Field(min_length=1, max_length=120)]


class ConfirmationIn(BaseModel):
    title: Label
    unit_type: Name
    unit_label: Label
    key_column: Name
    observation_start: Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]
    observation_end: Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]
    collection_method: Literal[
        "tag_or_pixel",
        "sdk",
        "server_log",
        "crawl_extraction",
        "survey_response",
        "transaction_record",
        "vendor_model",
        "clean_room_output",
        "other",
    ] = "other"
    location: Literal["workspace", "cleanroom"] = "workspace"
    seed_column: Name | None = None
    seed_label: Label | None = None
    behavior_column: Name | None = None
    behavior_label: Label | None = None
    behavior_features: list[Name] = Field(default_factory=list, max_length=200)
    outcome_column: Name | None = None
    outcome_label: Label | None = None
    outcome_horizon_days: int = Field(default=30, ge=1, le=730)
    breakdown_column: Name | None = None
    sensitive_columns: list[Name] = Field(default_factory=list, max_length=200)
    excluded_columns: list[Name] = Field(default_factory=list, max_length=200)
    rights_attested: bool = False
    timing_attested: bool = False

    def to_confirmation(self) -> uploads.Confirmation:
        data = self.model_dump()
        for key in ("behavior_features", "sensitive_columns", "excluded_columns"):
            data[key] = tuple(data[key])
        return uploads.Confirmation(**data)


def _keys_from_env() -> dict[str, str]:
    raw = os.environ.get("AIP_API_KEYS", "{}")
    keys = json.loads(raw)
    if not isinstance(keys, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in keys.items()):
        raise ValueError("AIP_API_KEYS must be a JSON object of sha256(key) hex -> tenant id")
    return {k.lower(): v for k, v in keys.items()}


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def create_app(
    *,
    store: Store,
    keys: dict[str, str],
    allowed_origins: list[str],
    now: Callable[[], Any] = utcnow,
) -> FastAPI:
    app = FastAPI(title="Agentic Audience Intelligence API", version=__version__, docs_url=None, redoc_url=None)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        max_age=600,
    )

    @app.exception_handler(uploads.UploadError)
    async def upload_error(_: Request, exc: uploads.UploadError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"error": str(exc)})

    def tenant(authorization: Annotated[str | None, Header()] = None) -> str:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "An invite key is required.")
        digest = hash_key(authorization.removeprefix("Bearer ").strip())
        for known, tenant_id in keys.items():
            if hmac.compare_digest(known, digest):
                store.sweep(now())
                return tenant_id
        raise HTTPException(401, "This invite key is not recognised.")

    Tenant = Annotated[str, Depends(tenant)]

    def load(tenant_id: str, dataset_id: str, name: str) -> dict[str, Any] | None:
        try:
            return store.read(tenant_id, dataset_id, name)
        except NotFound as exc:
            raise HTTPException(404, "No such dataset (it may have expired).") from exc

    def table(tenant_id: str, dataset_id: str) -> uploads.Table:
        try:
            return uploads.parse_csv(store.raw(tenant_id, dataset_id))
        except NotFound as exc:
            raise HTTPException(404, "No such dataset (it may have expired).") from exc

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "engine_version": __version__}

    @app.get("/v1/record-types")
    def record_types(_: Tenant) -> list[dict[str, str]]:
        types = TypeRegistry.load()
        entries = [types.get(path.stem, docs.V) for path in sorted((paths.registry_dir() / "types").glob("*.json"))]
        return [{"type_id": e["type_id"], "label": e["label"], "grain": e["grain"]} for e in entries if e]

    @app.post("/v1/datasets", status_code=201)
    async def create(request: Request, tenant_id: Tenant) -> dict[str, Any]:
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > uploads.MAX_BYTES:
            raise HTTPException(413, f"The file is larger than {uploads.MAX_BYTES // (1024 * 1024)} MB.")
        if store.count(tenant_id) >= MAX_DATASETS_PER_TENANT:
            raise HTTPException(429, f"At most {MAX_DATASETS_PER_TENANT} uploads are kept at once; delete one first.")
        raw = await request.body()
        parsed = uploads.parse_csv(raw)
        profiles = uploads.profile_columns(parsed)
        meta = {
            "rows": len(parsed.rows),
            "byte_count": parsed.byte_count,
            "sha256": parsed.sha256,
            "columns": [p.as_dict() for p in profiles],
            "suggested_roles": uploads.suggest_roles(profiles),
        }
        dataset_id = store.create(tenant_id, raw, meta, now())
        return load(tenant_id, dataset_id, "meta") or {}

    @app.get("/v1/datasets/{dataset_id}")
    def get(dataset_id: str, tenant_id: Tenant) -> dict[str, Any]:
        return {
            "meta": load(tenant_id, dataset_id, "meta"),
            "confirmation": load(tenant_id, dataset_id, "confirmation"),
            "bundle": load(tenant_id, dataset_id, "bundle"),
        }

    @app.post("/v1/datasets/{dataset_id}/assess")
    def assess(dataset_id: str, body: ConfirmationIn, tenant_id: Tenant) -> dict[str, Any]:
        prep = uploads.prepare(table(tenant_id, dataset_id), body.to_confirmation(), dataset_id)
        store.write(tenant_id, dataset_id, "confirmation", body.model_dump())
        return {"dataset_id": dataset_id, "assessment": uploads.assessment(prep)}

    @app.post("/v1/datasets/{dataset_id}/route")
    def route(dataset_id: str, tenant_id: Tenant) -> dict[str, Any]:
        confirmation = load(tenant_id, dataset_id, "confirmation")
        if confirmation is None:
            raise HTTPException(409, "Confirm the dataset (POST .../assess) before routing it.")
        parsed = table(tenant_id, dataset_id)
        prep = uploads.prepare(parsed, ConfirmationIn(**confirmation).to_confirmation(), dataset_id)
        moment = now()
        bundle = uploads.route(prep, parsed, tenant_id=tenant_id, now=moment)
        bundle["manifest"] = {
            "evaluated_at": format_ts(moment),
            "engine_version": __version__,
            "snapshot_sha256": parsed.sha256,
            "computed": "on_request",
            "synthetic": False,
        }
        store.write(tenant_id, dataset_id, "bundle", bundle)
        return bundle

    @app.post("/v1/datasets/{dataset_id}/build/{method}")
    def build(dataset_id: str, method: str, tenant_id: Tenant) -> dict[str, Any]:
        bundle = load(tenant_id, dataset_id, "bundle")
        confirmation = load(tenant_id, dataset_id, "confirmation")
        if bundle is None or confirmation is None:
            raise HTTPException(409, "Route the dataset (POST .../route) before building an audience.")
        entry = bundle["decisions"].get(method)
        if entry is None or entry["role"] != "method":
            raise HTTPException(404, f"No method '{method}' for this dataset.")
        if entry["decision"]["verdict"] != "ELIGIBLE":
            raise HTTPException(409, f"The router has not made '{method}' ELIGIBLE ({entry['decision']['verdict']}).")
        prep = uploads.prepare(
            table(tenant_id, dataset_id), ConfirmationIn(**confirmation).to_confirmation(), dataset_id
        )
        result = uploads.build(prep, method)
        bundle["results"][method] = result
        store.write(tenant_id, dataset_id, "bundle", bundle)
        return {"dataset_id": dataset_id, "method": method, "result": result}

    def prepared(tenant_id: str, dataset_id: str) -> tuple[uploads.Prepared, uploads.Table]:
        confirmation = load(tenant_id, dataset_id, "confirmation")
        if confirmation is None:
            raise HTTPException(409, "Confirm the dataset (POST .../assess) first.")
        parsed = table(tenant_id, dataset_id)
        return uploads.prepare(parsed, ConfirmationIn(**confirmation).to_confirmation(), dataset_id), parsed

    @app.post("/v1/datasets/{dataset_id}/universe", status_code=201)
    async def universe(
        dataset_id: str, request: Request, tenant_id: Tenant, rights_attested: bool = False
    ) -> dict[str, Any]:
        if not rights_attested:
            raise HTTPException(422, "Attest that you have the right to use the universe for this purpose.")
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > uploads.MAX_BYTES:
            raise HTTPException(413, f"The file is larger than {uploads.MAX_BYTES // (1024 * 1024)} MB.")
        prep, _ = prepared(tenant_id, dataset_id)
        raw = await request.body()
        parsed = uploads.parse_csv(raw)
        read = uploads.read_universe(prep, parsed)
        meta = {
            "rows": len(read.keys),
            "byte_count": parsed.byte_count,
            "sha256": parsed.sha256,
            "breakdown": read.breakdown is not None,
            "rights_attested": True,
            "uploaded_at": format_ts(now()),
        }
        store.put_raw(tenant_id, dataset_id, "universe", raw)
        store.write(tenant_id, dataset_id, "universe", meta)
        return meta

    @app.post("/v1/datasets/{dataset_id}/expand/{method}")
    def expand(dataset_id: str, method: str, tenant_id: Tenant) -> dict[str, Any]:
        bundle = load(tenant_id, dataset_id, "bundle")
        if bundle is None:
            raise HTTPException(409, "Route the dataset (POST .../route) before expanding an audience.")
        entry = bundle["decisions"].get(method)
        if entry is None or entry["role"] != "method":
            raise HTTPException(404, f"No method '{method}' for this dataset.")
        if entry["decision"]["verdict"] != "ELIGIBLE":
            raise HTTPException(409, f"The router has not made '{method}' ELIGIBLE ({entry['decision']['verdict']}).")
        meta = load(tenant_id, dataset_id, "universe")
        if meta is None or not meta.get("rights_attested"):
            raise HTTPException(409, "Upload a universe (POST .../universe) before expanding into it.")
        prep, parsed = prepared(tenant_id, dataset_id)
        read = uploads.read_universe(prep, uploads.parse_csv(store.raw(tenant_id, dataset_id, "universe")))
        result = uploads.expand(prep, parsed, read, method)
        return {
            "dataset_id": dataset_id,
            "method": method,
            "universe": meta,
            "keys": list(read.keys),
            "breakdown_codes": None if read.breakdown is None else [int(c) for c in read.breakdown],
            "result": result,
        }

    @app.delete("/v1/datasets/{dataset_id}", status_code=204)
    def delete(dataset_id: str, tenant_id: Tenant) -> None:
        try:
            store.delete(tenant_id, dataset_id)
        except NotFound as exc:
            raise HTTPException(404, "No such dataset (it may have expired).") from exc

    return app


def _sweep_every(store: Store, seconds: float) -> None:
    """Delete expired uploads on a timer too, so retention holds even when no request arrives."""

    def loop() -> None:
        while True:
            time.sleep(seconds)
            try:
                store.sweep(utcnow())
            except OSError:
                pass

    threading.Thread(target=loop, name="aip-sweep", daemon=True).start()


def app_from_env() -> FastAPI:
    """The production app, configured from the environment (``uvicorn --factory aip.api.app:app_from_env``)."""
    origins = os.environ.get("AIP_ALLOWED_ORIGINS", "https://audiences.nofluffadvisory.com")
    store = Store(
        Path(os.environ.get("AIP_DATA_DIR", "/tmp/aip-uploads")),
        timedelta(hours=float(os.environ.get("AIP_RETENTION_HOURS", "24"))),
    )
    _sweep_every(store, 60)
    return create_app(
        store=store,
        keys=_keys_from_env(),
        allowed_origins=[o.strip() for o in origins.split(",") if o.strip()],
    )
