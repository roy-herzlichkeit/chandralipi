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
    d = REPO / "data/processed/vikram/reference_sun"
    doc = json.loads((d / "reference_sun.json").read_text())
    assert doc["sun"]["azimuth_source"] == "computed" and doc["sun"]["elevation_source"] == "computed"
    assert doc["sun"]["azimuth_frame"] == "north_clockwise"
    assert "ode_elevation_deg" in doc["cross_checks"] and "dtm_fit" in doc["cross_checks"]
    assert (d / "ncc_curve.csv").exists()
    conv = json.loads((d / "label_convention.json").read_text())
    assert conv["convention"] in ("as_is", "plus_180", "mirror", "mirror_plus_180")


def test_run_records():
    from lunar_reg.runrecord import validate_run_record

    for rel in ("data/processed/vikram/reference_sun/run_record.json",
                "data/processed/vikram/exp1/raw_prior/run_record.json",
                "data/processed/vikram/exp1/run_record.json"):
        p = REPO / rel
        assert p.exists() and validate_run_record(p) == [], rel


def test_diagnosis_doc():
    """Review RC12: the class comes from diagnosis.json and appears as one exact line per strip."""
    import re

    diag = json.loads((REPO / "data/processed/vikram/exp1/diagnosis.json").read_text())
    assert diag["schema"] == 1 and set(diag["strips"]) == set(TAGS_2023)
    text = (REPO / "docs/VIKRAM_2023_DIAGNOSIS.md").read_text()
    assert "data/processed/vikram/exp1_gate.json" in text
    sections = re.split(r"^### ", text, flags=re.M)
    for tag in TAGS_2023:
        cls = diag["strips"][tag]["class"]
        assert cls in CLASSES
        body = next((s for s in sections if s.startswith(tag)), None)
        assert body is not None, f"no '### {tag}' heading"
        lines = re.findall(r"^Classification: (\w+)\s*$", body, flags=re.M)
        assert lines == [cls], f"{tag}: doc says {lines}, diagnosis.json says {cls}"
