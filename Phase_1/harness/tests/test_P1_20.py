"""P1.20 — 2023 diagnosis + exp-1 gate artefacts (Phase_1/LLD/runs.md §P1.20). Protected (G05)."""

from __future__ import annotations

import json

import pytest
from _h1 import REPO, TAGS_2023
from test_contracts_P1 import validate_c20

pytestmark = pytest.mark.data
CLASSES = ("PRIOR", "ILLUMINATION_SUSPECTED", "DATA", "UNRESOLVED")


def test_gate():
    validate_c20(json.loads((REPO / "data/processed/vikram/exp1_gate.json").read_text()))


def test_reference_sun():
    doc = json.loads((REPO / "data/processed/vikram/reference_sun/reference_sun.json").read_text())
    assert doc["sun"]["elevation_source"] == "documented"
    assert doc["sun"]["azimuth_source"] == "inferred"
    assert doc["sun"]["azimuth_frame"] == "grid_up_clockwise"
    assert (REPO / "data/processed/vikram/reference_sun/ncc_curve.csv").exists()


def test_run_records():
    from lunar_reg.runrecord import validate_run_record

    for rel in ("data/processed/vikram/reference_sun/run_record.json",
                "data/processed/vikram/exp1/raw_prior/run_record.json",
                "data/processed/vikram/exp1/run_record.json"):
        p = REPO / rel
        assert p.exists() and validate_run_record(p) == [], rel


def test_diagnosis_doc():
    text = (REPO / "docs/VIKRAM_2023_DIAGNOSIS.md").read_text()
    assert "data/processed/vikram/exp1_gate.json" in text
    for tag in TAGS_2023:
        assert tag in text
        section = text.split(tag, 1)[1][:4000]
        assert any(c in section for c in CLASSES), f"no cause class after {tag}"
