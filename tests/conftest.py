from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from aip import paths
from aip.canonical import load_path
from aip.contracts.validator import default_schema_set
from aip.registry import DocumentIndex, ReasonCodeRegistry, TypeRegistry
from aip.routing import RouterConfig

ROOT = paths.repo_root()
NOW = datetime(2026, 10, 14, 12, tzinfo=UTC)


@pytest.fixture(scope="session")
def schemas():
    return default_schema_set()


@pytest.fixture(scope="session")
def types():
    return TypeRegistry.load()


@pytest.fixture(scope="session")
def reasons():
    return ReasonCodeRegistry.load()


@pytest.fixture(scope="session")
def world():
    index = DocumentIndex()
    index.add_paths(
        sorted((ROOT / "registry" / "policies").glob("*.json"))
        + sorted((ROOT / "registry" / "profiles").glob("*.json"))
    )
    for kind in ("dataset_manifest", "objective", "source_profile"):
        index.add_paths(sorted((ROOT / "examples" / "valid" / kind).glob("*.json")))
    return index


@pytest.fixture(scope="session")
def config():
    return RouterConfig(max_decision_ttl=timedelta(days=7))


def example(rel: str) -> dict:
    return load_path(ROOT / "examples" / "valid" / f"{rel}.json")


def registry_doc(rel: str) -> dict:
    return load_path(ROOT / "registry" / f"{rel}.json")


def repo_path(*parts: str) -> Path:
    return ROOT.joinpath(*parts)
