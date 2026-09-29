"""P2.02 — device profiles (Phase_2/LLD/device.md §P2.02). Protected (G05)."""

from __future__ import annotations

import dataclasses

from _h2 import REPO


def test_tilebudget_fields():
    from lunar_reg.device import TileBudget

    names = [f.name for f in dataclasses.fields(TileBudget)]
    assert names[-2:] == ["fits", "source"]


def test_analytic_fallback_is_inferred(monkeypatch):
    from lunar_reg import device
    from lunar_reg.provenance import ValueSource

    monkeypatch.setattr(device, "free_vram_bytes", lambda d="cuda": 6 * 2**30)
    b = device.plan_dense_tile("cuda", "fp16", "loftr", profile=None)
    assert b.source is ValueSource.INFERRED and b.fits
    monkeypatch.setattr(device, "free_vram_bytes", lambda d="cuda": 50 * 2**20)
    assert device.plan_dense_tile("cuda", "fp16", "loftr", profile=None).fits is False


def test_readme():
    text = (REPO / "configs/device_profiles/README.md").read_text()
    assert "lunar-reg benchmark" in text and "bytes_per_px" in text
