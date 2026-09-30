"""P1.18 — RUN artefacts: archive, ablation, JAXA v2 (Phase_1/LLD/runs.md §P1.18). Protected (G05)."""

from __future__ import annotations

import json

import pytest
from _h1 import REPO

pytestmark = pytest.mark.data


def _rr_ok(path):
    from lunar_reg.runrecord import validate_run_record

    assert path.exists(), f"missing {path}"
    assert validate_run_record(path) == [], validate_run_record(path)


def test_archive():
    import pandas as pd

    idx = REPO / "data/processed/results_archive_20260929/index.parquet"
    assert idx.exists(), "v1 store not archived (G08)"
    assert len(pd.read_parquet(idx)) >= 13


def test_ablation():
    from lunar_reg.preprocess.presets import PRESET_NAMES

    doc = json.loads((REPO / "data/processed/ablation/ablation.json").read_text())
    assert doc["winner"] in PRESET_NAMES and doc["reason"]
    assert len(doc["anchor"]) == 12
    assert len(doc["synthetic"]) == 120
    for row in doc["anchor"]:
        assert {"preset", "matcher", "status", "n_inliers", "u_score"} <= set(row)
    _rr_ok(REPO / "data/processed/ablation/run_record.json")


def test_jaxa_v2():
    from lunar_reg.results import load_index

    _rr_ok(REPO / "data/processed/demo_real/v2/run_record.json")
    idx = load_index(REPO / "data/processed/results")
    jaxa = idx[idx["pair_id"].str.startswith("JAXA_SELENE_TC-")]
    assert len(jaxa) >= 1 and (jaxa["schema_version"] == 2).all()


def test_cross_instrument_record():
    """Review RC10/RC11: other CH-2 instruments are run when present and recorded when absent."""
    from lunar_reg.ingest.catalog import build_catalog

    rec_path = REPO / "data/processed/cross/run_record.json"
    _rr_ok(rec_path)
    rec = json.loads(rec_path.read_text())
    keys = [k for k in rec["outcome_counts"] if k.startswith("instrument_")]
    cat = build_catalog(REPO / "data/raw")
    for inst in ("TMC2", "IIRS"):
        assert any(k.startswith(f"instrument_{inst}_") for k in keys), inst
        if cat.status[inst].value == "present":
            assert (REPO / f"data/processed/cross/overlap_ohrc_{inst.lower()}.parquet").exists()
        else:
            assert f"{inst}: absent, not run" in rec["notes"]
