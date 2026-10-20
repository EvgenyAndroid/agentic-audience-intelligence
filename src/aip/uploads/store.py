"""Per-tenant storage for uploaded datasets, with a hard retention limit.

Each dataset is a folder holding the raw file, its column profile, the uploader's confirmation and the routed
bundle. Tenants are separated by folder (a hash of the tenant id) and a dataset id is only ever resolved inside
the caller's tenant folder, so one tenant cannot read, route or delete another's upload by guessing an id.
Everything older than the retention limit is deleted on the next request that touches the store.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import shutil
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from aip.timeutil import format_ts, parse_ts

DATASET_ID = re.compile(r"^up_[0-9a-f]{12}$")
MAX_DATASETS_PER_TENANT = 20


class NotFound(LookupError):
    pass


class Store:
    def __init__(self, root: Path, retention: timedelta) -> None:
        self.root = root
        self.retention = retention
        root.mkdir(parents=True, exist_ok=True)
        self._locks: dict[tuple[str, str], threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def lock(self, tenant_id: str, dataset_id: str) -> threading.Lock:
        """One lock per dataset. Every read-check-write of a dataset's confirmation, bundle or universe holds it,
        so a confirmation cannot change between a decision being checked and the work it permits. The API runs
        as one process, so an in-process lock covers every request."""
        with self._locks_guard:
            return self._locks.setdefault((tenant_id, dataset_id), threading.Lock())

    def _tenant_dir(self, tenant_id: str) -> Path:
        return self.root / hashlib.sha256(tenant_id.encode()).hexdigest()[:24]

    def _dir(self, tenant_id: str, dataset_id: str) -> Path:
        if not DATASET_ID.match(dataset_id):
            raise NotFound(dataset_id)
        path = self._tenant_dir(tenant_id) / dataset_id
        if not (path / "meta.json").is_file():
            raise NotFound(dataset_id)
        return path

    def sweep(self, now: datetime) -> int:
        """Delete every dataset past retention; returns how many were removed."""
        removed = 0
        for meta in self.root.glob("*/up_*/meta.json"):
            try:
                created = parse_ts(json.loads(meta.read_text(encoding="utf-8"))["created_at"])
            except (OSError, ValueError, KeyError):
                created = None
            if created is None or now - created >= self.retention:
                shutil.rmtree(meta.parent, ignore_errors=True)
                removed += 1
        return removed

    def count(self, tenant_id: str) -> int:
        return len(list(self._tenant_dir(tenant_id).glob("up_*/meta.json")))

    def create(self, tenant_id: str, raw: bytes, meta: dict[str, Any], now: datetime) -> str:
        dataset_id = f"up_{secrets.token_hex(6)}"
        path = self._tenant_dir(tenant_id) / dataset_id
        path.mkdir(parents=True)
        (path / "raw.csv").write_bytes(raw)
        expires = now + self.retention
        stamps = {"dataset_id": dataset_id, "created_at": format_ts(now), "expires_at": format_ts(expires)}
        self.write(tenant_id, dataset_id, "meta", {**meta, **stamps}, create=True)
        return dataset_id

    def raw(self, tenant_id: str, dataset_id: str, name: str = "raw") -> bytes:
        path = self._dir(tenant_id, dataset_id) / f"{name}.csv"
        if not path.is_file():
            raise NotFound(dataset_id)
        return path.read_bytes()

    def put_raw(self, tenant_id: str, dataset_id: str, name: str, raw: bytes) -> None:
        """Another file kept with an upload (a universe to expand into); deleted with it."""
        (self._dir(tenant_id, dataset_id) / f"{name}.csv").write_bytes(raw)

    def read(self, tenant_id: str, dataset_id: str, name: str) -> dict[str, Any] | None:
        path = self._dir(tenant_id, dataset_id) / f"{name}.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None

    def write(self, tenant_id: str, dataset_id: str, name: str, value: dict[str, Any], *, create: bool = False) -> None:
        folder = self._tenant_dir(tenant_id) / dataset_id if create else self._dir(tenant_id, dataset_id)
        (folder / f"{name}.json").write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def remove(self, tenant_id: str, dataset_id: str, name: str) -> None:
        """Delete one stored document (a no-op when it does not exist)."""
        (self._dir(tenant_id, dataset_id) / f"{name}.json").unlink(missing_ok=True)

    def delete(self, tenant_id: str, dataset_id: str) -> None:
        shutil.rmtree(self._dir(tenant_id, dataset_id))
