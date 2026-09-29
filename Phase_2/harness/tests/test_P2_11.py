"""P2.11 — GPU run artefacts (Phase_2/LLD/runner_gpu_runs.md §P2.11). Protected (G05)."""

from __future__ import annotations

import json

import pytest
from _h2 import REPO

pytestmark = [pytest.mark.data, pytest.mark.gpu]
ANCHOR = "20240425T1406019344"


def test_run_record_cuda():
    from lunar_reg.runrecord import validate_run_record

    rr = REPO / "data/processed/gpu_run/anchor/run_record.json"
    assert rr.exists() and validate_run_record(rr) == []
    assert json.loads(rr.read_text())["device"].startswith("cuda")


def test_anchor_rows():
    from lunar_reg.results import load_index

    idx = load_index(REPO / "data/processed/results")
    rows = idx[idx["pair_id"].str.contains(ANCHOR)]
    gpu = rows[rows["x_device"].astype(str).str.startswith("cuda")]
    assert len(gpu) >= 1
    assert (gpu["x_seconds_match"] > 0).all() and (gpu["x_peak_vram_bytes"].fillna(0) > 0).any()
    assert gpu["x_native_status"].notna().any()


def test_docs():
    gpu = (REPO / "docs/GPU_RUN.md").read_text()
    vram = (REPO / "docs/VRAM_CONSTRAINTS.md").read_text()
    assert "data/processed/gpu_run" in gpu
    assert "configs/device_profiles/rtx4060-laptop.json" in vram and "MEASURED" in vram
