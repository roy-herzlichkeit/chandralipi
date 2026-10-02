"""P1.18 — RUN artefacts: archive, ablation, JAXA v2, cross pairs (runs.md). Protected (G05)."""

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
    """G41: other CH-2 instruments are paired with every listed reference they overlap, at any
    site; disjoint pairs are recorded with their distance; absent instruments are noted."""
    from lunar_reg.ingest.catalog import build_catalog

    rec_path = REPO / "data/processed/cross/run_record.json"
    _rr_ok(rec_path)
    rec = json.loads(rec_path.read_text())
    counts = rec["outcome_counts"]
    overlaps = json.loads((REPO / "data/processed/cross/overlaps.json").read_text())
    assert overlaps["schema"] == 1
    cands = overlaps["candidates"]
    cat = build_catalog(REPO / "data/raw")
    for inst in ("TMC2", "IIRS"):
        assert any(k.startswith(f"instrument_{inst}_") for k in counts), inst
        if cat.status[inst].value != "present":
            assert f"{inst}: absent, not run" in rec["notes"]
            continue
        rows = [c for c in cands if c["instrument"] == inst]
        assert rows, f"{inst} is present but has no overlap candidate"
        for c in rows:
            if c["status"] == "overlap":
                runs = REPO / "data/processed/cross/runs" / c["reference"]
                assert list(runs.glob("*/run_record.json")), f"no sub-run under {runs}"
            elif c["status"] == "disjoint":
                assert c["min_distance_km"] is not None
                assert c["source_product_id"] in rec["notes"]
    assert counts.get("pairs_run", 0) == sum(c["status"] == "overlap" for c in cands)
