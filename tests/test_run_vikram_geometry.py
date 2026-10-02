"""run_vikram: numeric crop geometry, classified GeoTIFF export, no silent (0, 0) shift."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
TAG = "20240425T1406019344"
NAC = "NAC_DTM_VIKRAMSITE1_M1442997156_100CM"
GEOMETRY_TYPES = {
    "ref_crop_c0": int,
    "ref_crop_r0": int,
    "ref_factor": float,
    "shift_e_m": float,
    "shift_s_m": float,
    "src_win_l0": int,
    "src_win_s0": int,
    "src_win_lines": int,
    "src_win_samples": int,
    "gsd_m": float,
    "crop_geometry_source": str,
}
GEO = {
    "c0": 1,
    "r0": 2,
    "ref_factor": 4.0,
    "shift_e_m": 556.0,
    "shift_s_m": -2888.0,
    "src_win_l0": 0,
    "src_win_s0": 0,
    "src_win_lines": 10,
    "src_win_samples": 10,
    "label_centre": (0.0, 0.0),
}


@pytest.fixture
def rv():
    spec = importlib.util.spec_from_file_location("run_vikram", REPO / "scripts" / "run_vikram.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_stored_shift_parses_legacy_notes_and_never_defaults(rv):
    legacy = "8 m/px LightGlue, 106 inliers, shift +556,-2888 m (E,S)"
    assert rv._stored_shift({"coarse_pass": legacy}) == (556.0, -2888.0)
    assert rv._stored_shift({"search_prior": "prior shift 556,-2888 m (E,S)"}) == (556.0, -2888.0)
    current = "8 m/px LightGlue, 106 inliers, shift +556.125,-2888.500 m (E,S)"
    assert rv._stored_shift({"coarse_pass": current}) == (556.125, -2888.5)
    failed = "coarse pass failed (too_few_matches); label prior used"
    assert rv._stored_shift({"coarse_pass": failed}) is None
    assert rv._stored_shift({}) is None


def test_geometry_extra_has_exactly_the_c04_keys_and_types(rv):
    geo = {**GEO, "c0": np.int64(100), "r0": 200.0, "ref_factor": 4}
    extra = rv.geometry_extra(geo, 4)
    assert set(extra) == set(GEOMETRY_TYPES)
    for key, typ in GEOMETRY_TYPES.items():
        assert type(extra[key]) is typ, key
    assert extra["crop_geometry_source"] == "recorded"
    assert (extra["ref_crop_c0"], extra["ref_crop_r0"]) == (100, 200)


def test_coarse_note_keeps_three_decimals(rv, monkeypatch):
    """The coarse pass moved to lunar_reg.sites.runner (P1.16); its note still round-trips."""
    from types import SimpleNamespace

    from lunar_reg.ingest.lro import GeoReference
    from lunar_reg.pairs import PrepOutcome, PrepStatus, PriorSource, WindowPair
    from lunar_reg.pipeline import RunOutcome, RunStatus
    from lunar_reg.provenance import ValueSource
    from lunar_reg.sites import runner

    img = np.ones((8, 8), np.uint8)
    # prior puts the source centre (4, 4) at (3.75, 4.125); the match keeps it at (4, 4)
    prior = np.array([[1.0, 0, -0.25], [0, 1.0, 0.125], [0, 0, 1.0]])
    pair = WindowPair(
        img, img, img > 0, img > 0, prior, PriorSource.LABEL_CORNERS, 1.0, (0, 0, 8, 8),
        (0, 0, 8, 8), 1.0, 1.0, np.eye(3), np.eye(3), (0.0, 0.0), "src", "ref", {},
    )  # fmt: skip
    geo = GeoReference("+proj=stere", 0.0, 0.0, 1.0, 1.0, 100, 100, ValueSource.INFERRED)
    found = SimpleNamespace(transform=np.eye(3), n_inliers=42)
    monkeypatch.setattr(
        runner, "prepare_window_pair", lambda *a, **k: PrepOutcome(PrepStatus.OK, pair)
    )
    monkeypatch.setattr(
        runner, "register_pair", lambda *a, **k: RunOutcome("coarse", RunStatus.OK, result=found)
    )
    entry = SimpleNamespace(label_path="label.xml", geometry_grid_path=None)
    shift, note = runner._coarse(entry, runner.SiteConfig(), geo, TAG)
    assert shift == pytest.approx((0.25, -0.125))
    assert "42 inliers" in note and "shift +0.250,-0.125 m (E,S)" in note
    assert rv._stored_shift({"coarse_pass": note}) == pytest.approx((0.25, -0.125))


def _result(pair_id: str, extra: dict):
    from lunar_reg.results import PairResult

    pts = np.zeros((4, 2))
    return PairResult(
        pair_id, "src", NAC, "CH2_OHRC_RAW", "LRO_NAC_ORTHO", "sift", pts, pts, None, np.eye(3),
        extra=extra,
    )  # fmt: skip


@pytest.fixture
def export_env(rv, monkeypatch, tmp_path):
    """Patch the store, the I/O and the GeoTIFF writer; return (stored, written)."""
    import rasterio

    import lunar_reg.align.warp as warp
    import lunar_reg.results as results

    stored: dict = {}
    written: list = []

    def fake_save(src, matrix, shape, path, **kw):
        written.append((path, kw))
        return {"path": str(path), "shape": shape, "valid_fraction": 1.0}

    class _Dataset:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(
        results, "load_index", lambda root: pd.DataFrame({"pair_id": sorted(stored)})
    )
    monkeypatch.setattr(results, "load_pair", lambda pid, root: stored[pid])
    monkeypatch.setattr(warp, "save_registered_geotiff", fake_save)
    monkeypatch.setattr(
        rv, "prepare_pair",
        lambda *a, **k: (None, np.zeros((8, 8), np.uint8), np.zeros((8, 8), np.uint8), np.eye(3),
                         1.0, GEO),
    )  # fmt: skip
    monkeypatch.setattr(rv.glob, "glob", lambda pattern: [str(tmp_path / "label.xml")])
    monkeypatch.setattr(rasterio, "open", lambda *a, **k: _Dataset())
    monkeypatch.setattr(rv.Path, "exists", lambda self: True)
    return stored, written


SETTINGS = {"window_m": 3000.0, "margin_m": 1000.0, "gsd_m": 4.0}


def test_export_classifies_recorded_legacy_and_missing(rv, export_env, capsys):
    stored, written = export_env
    recorded = {
        **SETTINGS, "ref_crop_c0": 10, "ref_crop_r0": 20, "ref_factor": 4.0, "shift_e_m": 0.5,
        "shift_s_m": -0.5, "crop_geometry_source": "recorded", "model": "homography",
        "min_inliers": 5,
    }  # fmt: skip
    legacy = {**SETTINGS, "coarse_pass": "8 m/px LightGlue, 106 inliers, shift +556,-2888 m (E,S)"}
    for matcher, extra in (("sift", recorded), ("akaze", legacy), ("asift", dict(SETTINGS))):
        pid = f"CH2_OHRC_RAW_{TAG}-LRO_NAC_ORTHO_{matcher}"
        stored[pid] = _result(pid, extra)

    code = rv.export_stored("")
    out = capsys.readouterr().out
    assert code == 1
    assert "exported: 2" in out and "recorded_geometry_missing: 1" in out
    by_source = {kw["tags"]["crop_geometry_source"]: kw for _, kw in written}
    assert set(by_source) == {"recorded", "regex_legacy"}
    # Recorded geometry sets the origin; the legacy one uses the rebuilt crop (GEO c0/r0).
    assert by_source["recorded"]["origin_xy"] == (rv.NAC_X0 + 10, rv.NAC_Y0 - 20)
    assert by_source["regex_legacy"]["origin_xy"] == (rv.NAC_X0 + 1, rv.NAC_Y0 - 2)
    assert by_source["recorded"]["tags"]["model"] == "homography"
    assert by_source["regex_legacy"]["tags"]["min_inliers"] == "unrecorded"


def test_export_settings_unrecorded_and_input_missing(rv, export_env, monkeypatch, capsys):
    stored, written = export_env
    no_margin = f"CH2_OHRC_RAW_{TAG}-LRO_NAC_ORTHO_orb"
    stored[no_margin] = _result(no_margin, {"window_m": 3000.0, "gsd_m": 4.0, "ref_crop_c0": 1})
    code = rv.export_stored("")
    out = capsys.readouterr().out
    assert code == 1 and not written
    assert "settings_unrecorded: 1" in out and "margin_m" in out

    stored.clear()
    ok = f"CH2_OHRC_RAW_{TAG}-LRO_NAC_ORTHO_sift"
    stored[ok] = _result(ok, {**SETTINGS, "search_prior": "prior shift 556,-2888 m (E,S)"})
    monkeypatch.setattr(rv.glob, "glob", lambda pattern: [])
    assert rv.export_stored("") == 1
    assert "input_missing: 1" in capsys.readouterr().out


def test_export_write_failure_is_classified(rv, export_env, monkeypatch, capsys):
    import lunar_reg.align.warp as warp

    stored, _ = export_env
    pid = f"CH2_OHRC_RAW_{TAG}-LRO_NAC_ORTHO_sift"
    stored[pid] = _result(pid, {**SETTINGS, "search_prior": "prior shift 556,-2888 m (E,S)"})

    def broken(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(warp, "save_registered_geotiff", broken)
    assert rv.export_stored("") == 1
    assert "write_failed: 1" in capsys.readouterr().out


def test_export_all_ok_returns_zero(rv, export_env, capsys):
    stored, written = export_env
    pid = f"CH2_OHRC_RAW_{TAG}-LRO_NAC_ORTHO_sift"
    stored[pid] = _result(pid, {**SETTINGS, "search_prior": "prior shift 556,-2888 m (E,S)"})
    assert rv.export_stored("") == 0
    assert len(written) == 1 and "exported: 1" in capsys.readouterr().out
