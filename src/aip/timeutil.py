"""UTC timestamp helpers matching the contract format (RFC 3339 with Z)."""

from __future__ import annotations

from datetime import UTC, datetime


def parse_ts(value: str) -> datetime:
    if not value.endswith("Z"):
        raise ValueError(f"timestamp must be UTC with Z suffix: {value!r}")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def format_ts(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("naive datetimes are not allowed")
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def utcnow() -> datetime:
    return datetime.now(UTC)
