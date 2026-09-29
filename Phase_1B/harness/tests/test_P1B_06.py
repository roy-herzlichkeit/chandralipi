"""P1B.06 — bridge run artefacts (Phase_1B/LLD/bridge_runner.md §P1B.06). Protected (G05)."""

from __future__ import annotations

import json

import pytest
from _h1b import REPO, TAGS_2023

pytestmark = pytest.mark.data


def test_calibration():
    doc = json.loads((REPO / "data/processed/bridge/azimuth_calibration.json").read_text())
    assert doc["convention"] in ("as_is", "plus_180", "mirror", "mirror_plus_180")
    assert doc["source"] == "inferred"


def test_rows_and_records():
    from lunar_reg.results import load_index
    from lunar_reg.runrecord import validate_run_record

    for rel in ("data/processed/bridge/run/run_record.json",
                "data/processed/bridge/rift2/run_record.json"):
        assert validate_run_record(REPO / rel) == [], rel
    idx = load_index(REPO / "data/processed/results")
    for tag in TAGS_2023:
        assert idx["pair_id"].str.contains(tag).any()
    bridge_or_failed = idx["pair_id"].str.contains("_bridge-").any()
    from lunar_reg.results import load_failures

    fails = load_failures(REPO / "data/processed/results")
    assert bridge_or_failed or fails["pair_id"].str.contains("_bridge-").any()


def test_doc():
    text = (REPO / "docs/ILLUMINATION_BRIDGE.md").read_text()
    assert "data/processed/bridge/" in text
    for tag in TAGS_2023:
        assert tag in text
