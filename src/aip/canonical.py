"""Strict JSON loading and canonical hashing.

Loading rejects NaN/Infinity and duplicate keys. Canonical form is sorted-key compact UTF-8 JSON.
It is deterministic for this platform's documents but is not RFC 8785 (JCS) number canonicalization.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class StrictJSONError(ValueError):
    """Raised for JSON that is valid syntax but violates platform rules."""


def _reject_constant(name: str) -> Any:
    raise StrictJSONError(f"non-finite number {name} is not allowed")


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise StrictJSONError(f"duplicate key {key!r}")
        out[key] = value
    return out


def loads(text: str) -> Any:
    return json.loads(text, parse_constant=_reject_constant, object_pairs_hook=_no_duplicate_keys)


def load_path(path: Path | str) -> Any:
    return loads(Path(path).read_text(encoding="utf-8"))


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha256_of(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def dump_path(value: Any, path: Path | str) -> None:
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
