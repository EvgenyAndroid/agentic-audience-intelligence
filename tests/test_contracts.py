import re

import pytest
from conftest import ROOT

from aip.canonical import StrictJSONError, load_path, loads
from aip.contracts.conformance import apply_patch, check_invalid, check_valid

VALID_FILES = sorted((ROOT / "examples" / "valid").rglob("*.json")) + sorted((ROOT / "registry").rglob("*.json"))
INVALID = load_path(ROOT / "examples" / "invalid" / "cases.json")["cases"]


@pytest.mark.parametrize("path", VALID_FILES, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_valid_documents_pass(schemas, path):
    [result] = check_valid(schemas, [path])
    assert result.passed, result.detail


@pytest.mark.parametrize("case", INVALID, ids=lambda c: c["id"])
def test_invalid_cases_fail_for_expected_reason(schemas, case, tmp_path):
    cases_file = tmp_path / "one.json"
    cases_file.write_text(__import__("json").dumps({"cases": [case]}), encoding="utf-8")
    [result] = check_invalid(schemas, cases_file, ROOT)
    assert result.passed, f"{case['description']}: found {result.detail}"


def test_every_kind_has_a_valid_example(schemas):
    kinds = {load_path(p)["kind"] for p in VALID_FILES}
    assert set(schemas.kinds) <= kinds


def test_schema_requirement_ids_exist_in_prd(schemas):
    prd = (ROOT / "docs" / "spec" / "PRD.md").read_text(encoding="utf-8")
    defined = set(re.findall(r"\*\*((?:N)?FR\d+)", prd))
    for kind, schema in schemas.schemas.items():
        for req in schema["x-prd-requirements"]:
            assert req in defined, f"{kind} references unknown requirement {req}"


def test_strict_loader_rejects_non_finite_and_duplicates():
    with pytest.raises(StrictJSONError):
        loads('{"x": Infinity}')
    with pytest.raises(StrictJSONError):
        loads('{"a": 1, "a": 2}')


def test_apply_patch_is_non_mutating():
    original = {"a": [1, 2]}
    patched = apply_patch(original, [{"op": "add", "path": "/a/-", "value": 3}])
    assert patched == {"a": [1, 2, 3]} and original == {"a": [1, 2]}
