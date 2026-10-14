"""Repository path discovery (pathlib only, Windows-safe)."""

from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    """Return the repository root: $AIP_HOME, else the nearest parent holding pyproject.toml and schemas/."""
    env = os.environ.get("AIP_HOME")
    if env:
        return Path(env).resolve()
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file() and (parent / "schemas").is_dir():
            return parent
    raise FileNotFoundError("Cannot locate the repository root; set the AIP_HOME environment variable.")


def schema_dir() -> Path:
    return repo_root() / "schemas" / "v1"


def registry_dir() -> Path:
    return repo_root() / "registry"
