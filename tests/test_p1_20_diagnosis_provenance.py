"""P1.20 step 5: the classification artefact is reproducible and its numbers carry provenance.

Review finding (Q-P1.20-2): diagnosis.json must come from a kept program with a C15 run
record, and every number under ``rule_inputs`` must have a ``<name>_source`` sibling holding
a ValueSource value.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lunar_reg.provenance import ValueSource

REPO = Path(__file__).resolve().parents[1]
DIAG = REPO / "data/processed/vikram/exp1/diagnosis.json"
RECORD = REPO / "data/processed/vikram/exp1/diagnosis_run/run_record.json"
SOURCES = {v.value for v in ValueSource}

pytestmark = pytest.mark.data


def _numbers_without_source(node: dict, path: str = "") -> list[str]:
    """Paths of numeric (or null) leaves with no ``<key>_source`` sibling.

    A block-wide ``values_source`` covers every number in its block.
    """
    missing = []
    block_source = node.get("values_source") in SOURCES
    for key, val in node.items():
        here = f"{path}.{key}" if path else key
        if isinstance(val, dict):
            missing += _numbers_without_source(val, here)
        elif isinstance(val, bool) or key.endswith("_source"):
            continue
        elif isinstance(val, (int, float)) or val is None:
            sibling = node.get(f"{key}_source")
            group = key.startswith("live_store_") and node.get("live_store_rows_source") in SOURCES
            if not (sibling in SOURCES or block_source or group):
                missing.append(here)
    return missing


def _require_artefacts():
    if not DIAG.exists() or not RECORD.exists():
        pytest.skip("P1.20 artefacts not present")


def test_diagnosis_run_record_keeps_the_program():
    _require_artefacts()
    from lunar_reg.runrecord import validate_run_record

    assert validate_run_record(RECORD) == []
    rec = json.loads(RECORD.read_text())
    assert rec["command"][:2] == [".venv/bin/python", "-c"] and len(rec["command"]) == 3
    assert "data/processed/vikram/exp1/diagnosis.json" in rec["command"][2]
    assert "data/processed/vikram/exp1/diagnosis.json" in rec["artefacts"]
    classes = json.loads(DIAG.read_text())["strips"]
    assert rec["outcome_counts"]["strips"] == len(classes)
    for cls in {s["class"] for s in classes.values()}:
        n = sum(s["class"] == cls for s in classes.values())
        assert rec["outcome_counts"][f"class_{cls}"] == n


def test_rule_input_numbers_carry_a_source():
    _require_artefacts()
    strips = json.loads(DIAG.read_text())["strips"]
    for tag, strip in strips.items():
        assert _numbers_without_source(strip["rule_inputs"]) == [], tag


def test_source_check_flags_a_bare_number():
    assert _numbers_without_source({"x": 1.0}) == ["x"]
    assert _numbers_without_source({"x": 1.0, "x_source": "computed"}) == []
    assert _numbers_without_source({"x": 1.0, "x_source": "guess"}) == ["x"]
    assert _numbers_without_source({"g": {"n": 0, "values_source": "computed"}}) == []
