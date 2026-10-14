"""Every active PRD requirement must appear in the traceability table (BRD acceptance rule)."""

import re

from conftest import ROOT

PRD = (ROOT / "docs" / "spec" / "PRD.md").read_text(encoding="utf-8")


def _defined():
    return {m.group(1): m.group(2) for m in re.finditer(r"\*\*((?:N)?FR\d+) [^*]*?— ([^.*]+)\.\*\*", PRD)}


def _traced():
    table = PRD[PRD.index("| Business need") : PRD.index("Agent evaluation uses neutral")]
    ids = set(re.findall(r"N?FR\d+", table))
    for prefix, a, b in re.findall(r"(N?FR)(\d+) to (?:N?FR)?(\d+)", table):
        ids |= {f"{prefix}{i:02d}" for i in range(int(a), int(b) + 1)}
    return ids


def test_every_active_requirement_is_traced():
    active = {rid for rid, priority in _defined().items() if not priority.startswith("Retired")}
    assert len(active) >= 40
    assert sorted(active - _traced()) == []


def test_retired_requirements_are_not_traced_as_active():
    retired = {rid for rid, priority in _defined().items() if priority.startswith("Retired")}
    assert retired == {"FR30"}
