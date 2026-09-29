"""P0.11 — run_vikram numeric crop geometry (Phase_0/LLD/run_vikram_geometry.md). Protected (G05)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from _h0 import load_script

GEOMETRY_KEYS = {
    "ref_crop_c0": int, "ref_crop_r0": int, "ref_factor": float, "shift_e_m": float,
    "shift_s_m": float, "src_win_l0": int, "src_win_s0": int, "src_win_lines": int,
    "src_win_samples": int, "gsd_m": float, "crop_geometry_source": str,
}


@pytest.fixture
def rv():
    return load_script("run_vikram")


def test_stored_shift_legacy(rv):
    assert rv._stored_shift({"coarse_pass": "8 m/px LightGlue, 106 inliers, shift +556,-2888 m (E,S)"}) \
        == (556.0, -2888.0)
    assert rv._stored_shift({"search_prior": "prior shift 556,-2888 m (E,S)"}) == (556.0, -2888.0)
    assert rv._stored_shift({"coarse_pass": "coarse pass failed (too_few_matches); label prior used"}) \
        is None
    assert rv._stored_shift({}) is None


def test_geometry_extra(rv):
    geo = {"c0": 100, "r0": 200, "ref_factor": 4.0, "shift_e_m": 556.0, "shift_s_m": -2888.0,
           "src_win_l0": 10, "src_win_s0": 20, "src_win_lines": 12000, "src_win_samples": 12000,
           "label_centre": (1.0, 2.0)}
    extra = rv.geometry_extra(geo, 4.0)
    assert set(extra) == set(GEOMETRY_KEYS)
    for key, typ in GEOMETRY_KEYS.items():
        assert type(extra[key]) is typ, key
    assert extra["crop_geometry_source"] == "recorded"


def test_export_status_members(rv):
    assert {m.value for m in rv.ExportStatus} == {
        "exported", "recorded_geometry_missing", "settings_unrecorded", "input_missing",
        "write_failed"}


def _fake_result(pair_id, extra):
    from lunar_reg.results import PairResult

    pts = np.zeros((4, 2))
    return PairResult(pair_id, "src", "NAC_DTM_VIKRAMSITE1_M1442997156_100CM", "CH2_OHRC_RAW",
                      "LRO_NAC_ORTHO", "sift", pts, pts, None, np.eye(3), extra=extra)


def test_export_classification(rv, monkeypatch, tmp_path, capsys):
    tag = "20240425T1406019344"
    base = {"window_m": 3000.0, "margin_m": 1000.0, "gsd_m": 4.0}
    stored = {
        f"CH2_OHRC_RAW_{tag}-LRO_NAC_ORTHO_sift": _fake_result(
            f"CH2_OHRC_RAW_{tag}-LRO_NAC_ORTHO_sift",
            {**base, "ref_crop_c0": 10, "ref_crop_r0": 20, "ref_factor": 4.0,
             "shift_e_m": 0.0, "shift_s_m": 0.0, "crop_geometry_source": "recorded"}),
        f"CH2_OHRC_RAW_{tag}-LRO_NAC_ORTHO_akaze": _fake_result(
            f"CH2_OHRC_RAW_{tag}-LRO_NAC_ORTHO_akaze",
            {**base, "coarse_pass": "8 m/px LightGlue, 106 inliers, shift +556,-2888 m (E,S)"}),
        f"CH2_OHRC_RAW_{tag}-LRO_NAC_ORTHO_asift": _fake_result(
            f"CH2_OHRC_RAW_{tag}-LRO_NAC_ORTHO_asift", {**base}),
        f"CH2_OHRC_RAW_{tag}-LRO_NAC_ORTHO_orb": _fake_result(
            f"CH2_OHRC_RAW_{tag}-LRO_NAC_ORTHO_orb", {"window_m": 3000.0, "gsd_m": 4.0}),
    }
    import lunar_reg.align.warp as warp
    import lunar_reg.results as results

    monkeypatch.setattr(results, "load_index",
                        lambda root: pd.DataFrame({"pair_id": sorted(stored)}))
    monkeypatch.setattr(results, "load_pair", lambda pid, root: stored[pid])
    written = []

    def fake_save(src, matrix, shape, path, **kw):
        written.append((path, kw.get("tags", {})))
        return {"path": str(path), "shape": shape, "valid_fraction": 1.0}

    monkeypatch.setattr(warp, "save_registered_geotiff", fake_save)
    geo = {"c0": 1, "r0": 2, "ref_factor": 4.0, "shift_e_m": 556.0, "shift_s_m": -2888.0,
           "src_win_l0": 0, "src_win_s0": 0, "src_win_lines": 10, "src_win_samples": 10,
           "label_centre": (0.0, 0.0)}
    monkeypatch.setattr(rv, "prepare_pair", lambda *a, **k: (
        None, np.zeros((8, 8), np.uint8), np.zeros((8, 8), np.uint8), np.eye(3), 1.0, geo))
    monkeypatch.setattr(rv.glob, "glob", lambda pattern: [str(tmp_path / "label.xml")])

    class _DS:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    import rasterio

    monkeypatch.setattr(rasterio, "open", lambda *a, **k: _DS())
    monkeypatch.setattr(rv.Path, "exists", lambda self: True)
    code = rv.export_stored("")
    out = capsys.readouterr().out
    assert code == 1
    assert "recorded_geometry_missing" in out and "settings_unrecorded" in out
    assert len(written) == 2
    sources = sorted(tags.get("crop_geometry_source") for _, tags in written)
    assert sources == ["recorded", "regex_legacy"]
    for _, tags in written:
        assert tags.get("min_inliers") == "unrecorded" and tags.get("model") == "unrecorded"
