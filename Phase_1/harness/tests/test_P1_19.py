"""P1.19 — preset default applied from data + anchor in live store (Phase_1/LLD/runs.md §P1.19). Protected (G05)."""

from __future__ import annotations

import dataclasses
import json

import pytest
from _h1 import ANCHOR, REPO

pytestmark = pytest.mark.data


def test_default_equals_winner():
    from lunar_reg.pipeline import PipelineConfig
    from lunar_reg.preprocess.presets import choose_default_preset

    doc = json.loads((REPO / "data/processed/ablation/ablation.json").read_text())
    winner, _ = choose_default_preset(doc)
    default = {f.name: f.default for f in dataclasses.fields(PipelineConfig)}["preprocess"]
    assert default == winner == doc["winner"]


def test_doc_cites_artefact():
    text = (REPO / "docs/PREPROCESS_ABLATION.md").read_text()
    assert "data/processed/ablation/ablation.json" in text and "SYNTHETIC" in text


def test_anchor_in_live_store():
    from lunar_reg.results import load_index
    from lunar_reg.runrecord import validate_run_record

    rr = REPO / "data/processed/vikram/runs/p1_19_anchor/run_record.json"
    assert rr.exists() and validate_run_record(rr) == []
    idx = load_index(REPO / "data/processed/results")
    rows = idx[idx["pair_id"].str.contains(ANCHOR)]
    assert len(rows) >= 1 and (rows["schema_version"] == 2).all()
