"""``lunar-reg register``/``inspect``/``overlap --crop-dir``, ``scripts/run_jaxa.py`` and
``scripts/run_ablation.py`` (Phase_1/LLD/jaxa_cli_ablation.md §4). Data-free: every input is
synthetic (``illumination_pair`` scenes, hand-built GeoTIFFs and labels)."""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from lunar_reg.cli import main

REPO = Path(__file__).resolve().parents[1]
MOON_R = 1737400.0
EQC0 = "+proj=eqc +lat_ts=0 +lat_0=0 +lon_0=0 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs"
EQC180 = "+proj=eqc +lat_ts=0 +lat_0=0 +lon_0=180 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs"
REGISTER_KEYS = {
    "pair_id",
    "status",
    "detail",
    "stage",
    "metrics",
    "uniformity",
    "conditioning",
    "transform",
    "extra",
}

LABEL = """<?xml version="1.0" encoding="UTF-8"?>
<Product_Observational xmlns="http://pds.nasa.gov/pds4/pds/v1">
  <Identification_Area><logical_identifier>urn:isro:isda:ch2_ohr:test_sun</logical_identifier>
  </Identification_Area>
  <Observation_Area><Discipline_Area>
    <sun_azimuth>303.9</sun_azimuth><sun_elevation>11.5</sun_elevation>
    <solar_incidence>78.5</solar_incidence>
  </Discipline_Area></Observation_Area>
  <File_Area_Observational><File><file_name>x.img</file_name></File>
    <Array_2D_Image><offset unit="byte">0</offset><axes>2</axes>
      <axis_index_order>Last Index Fastest</axis_index_order>
      <Element_Array><data_type>UnsignedByte</data_type></Element_Array>
      <Axis_Array><axis_name>Line</axis_name><elements>12</elements><sequence_number>1</sequence_number></Axis_Array>
      <Axis_Array><axis_name>Sample</axis_name><elements>10</elements><sequence_number>2</sequence_number></Axis_Array>
    </Array_2D_Image></File_Area_Observational>
</Product_Observational>
"""


def _script(name: str):
    spec = importlib.util.spec_from_file_location(f"_t_{name}", REPO / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pair(seed=4, shape=(320, 320)):
    from lunar_reg.eval.scenes import illumination_pair

    src, ref, _, _ = illumination_pair(
        shape=shape, seed=seed, source_sun=(300, 30), reference_sun=(300, 30)
    )
    return src, ref


def _tif(path: Path, arr: np.ndarray, crs: str | None = None, x0=0.0, y0=0.0, px=1.0, nodata=None):
    import rasterio
    from rasterio.transform import from_origin

    path.parent.mkdir(parents=True, exist_ok=True)
    profile = dict(
        driver="GTiff", width=arr.shape[1], height=arr.shape[0], count=1, dtype=arr.dtype
    )
    if crs is not None:
        profile.update(crs=crs, transform=from_origin(x0, y0, px, px))
    if nodata is not None:
        profile["nodata"] = nodata
    with rasterio.open(path, "w", **profile) as ds:
        ds.write(arr, 1)
    return path


# ---------------------------------------------------------------------------
# cli inspect / register / overlap
# ---------------------------------------------------------------------------


def test_inspect_prints_the_sun_line(tmp_path, capsys):
    label = tmp_path / "ch2_ohr_x.xml"
    label.write_text(LABEL)
    (tmp_path / "x.img").write_bytes(np.zeros(120, np.uint8).tobytes())
    assert main(["inspect", str(label)]) == 0
    out = capsys.readouterr().out
    assert "sun azim:   303.90 deg" in out
    assert "incidence:  78.50 deg" in out


def test_register_ok_writes_the_output_json_and_saves(tmp_path, capsys):
    src, ref = _pair()
    a, b = _tif(tmp_path / "a.tif", src), _tif(tmp_path / "b.tif", ref)
    out_json = tmp_path / "out" / "r.json"
    code = main(
        [
            "register",
            str(a),
            str(b),
            "--matcher",
            "sift",
            "--output",
            str(out_json),
            "--save-root",
            str(tmp_path / "store"),
        ]
    )
    printed = capsys.readouterr().out
    assert code == 0, printed
    doc = json.loads(out_json.read_text())
    assert set(doc) == REGISTER_KEYS
    assert doc["status"] == "ok" and doc["stage"] == "done"
    assert doc["pair_id"] == "a-b_sift"
    assert np.asarray(doc["transform"]).shape == (3, 3)
    assert doc["metrics"]["n_inliers"] >= 8
    assert doc["extra"]["source_downsample"] == 1.0
    assert doc["extra"]["downsample_source"] == "computed"
    assert "a-b_sift: ok" in printed
    assert (tmp_path / "store" / "pairs" / "a-b_sift.npz").exists()


def test_register_downsamples_to_max_px(tmp_path):
    src, ref = _pair(shape=(320, 320))
    a, b = _tif(tmp_path / "a.tif", src), _tif(tmp_path / "b.tif", ref)
    out_json = tmp_path / "r.json"
    main(["register", str(a), str(b), "--max-px", "160", "--output", str(out_json)])
    doc = json.loads(out_json.read_text())
    assert doc["extra"]["source_downsample"] == pytest.approx(2.0)
    assert doc["extra"]["reference_downsample"] == pytest.approx(2.0)
    assert doc["extra"]["max_px"] == 160


def test_register_failure_is_exit_1_with_classified_json(tmp_path):
    z = np.zeros((128, 128), np.uint8)
    a, b = _tif(tmp_path / "a.tif", z), _tif(tmp_path / "b.tif", z)
    out_json = tmp_path / "r.json"
    code = main(
        [
            "register",
            str(a),
            str(b),
            "--matcher",
            "sift",
            "--output",
            str(out_json),
            "--save-root",
            str(tmp_path / "store"),
        ]
    )
    assert code == 1
    doc = json.loads(out_json.read_text())
    assert set(doc) == REGISTER_KEYS
    assert doc["status"] == "too_few_matches" and doc["transform"] is None
    assert doc["metrics"] == {} and doc["stage"] == "match"
    assert (tmp_path / "store" / "failures.parquet").exists()


def test_overlap_crop_dir_reports_skipped_footprints(tmp_path, monkeypatch, capsys):
    import pandas as pd

    import lunar_reg.ingest.manifest as manifest_mod
    import lunar_reg.ingest.overlap as overlap_mod

    pairs = pd.DataFrame(
        [
            {
                "source_id": "OHRC_A",
                "reference_id": "TMC_B",
                "overlap_area_km2": 1.0,
                "source_fraction": 0.5,
                "reference_fraction": 0.5,
            }
        ]
    )
    diag = SimpleNamespace(report=lambda: "overlap: 1 pair(s)", n_pairs_considered=1)
    monkeypatch.setattr(manifest_mod, "read_manifest", lambda path: pd.DataFrame([{"x": 1}]))
    monkeypatch.setattr(overlap_mod, "find_overlapping_pairs", lambda *a, **k: (pairs, diag))
    monkeypatch.setattr(overlap_mod, "footprint_from_row", lambda row: None)
    code = main(["overlap", str(tmp_path / "m.parquet"), "--crop-dir", str(tmp_path / "crops")])
    assert code == 0
    out = capsys.readouterr().out
    assert "skipped 1, e.g. OHRC_A" in out
    assert "cropped 0 image(s)" in out


# ---------------------------------------------------------------------------
# scripts/run_jaxa.py
# ---------------------------------------------------------------------------


def test_run_jaxa_missing_inputs_are_input_missing(tmp_path, monkeypatch, capsys):
    from lunar_reg.runrecord import validate_run_record

    rj = _script("run_jaxa")
    monkeypatch.chdir(tmp_path)
    assert rj.main(["--root", str(tmp_path / "store")]) == 1
    out = capsys.readouterr().out
    assert "input_missing: 2" in out
    assert "data gap" in out
    assert {m.value for m in rj.PairPrepStatus} == {"ok", "input_missing", "no_overlap"}
    rr = tmp_path / rj.RUN_DIR / "run_record.json"
    assert validate_run_record(rr) == []
    counts = json.loads(rr.read_text())["outcome_counts"]
    assert counts["prep_input_missing"] == 2 and counts["ok"] == 0


def test_run_jaxa_same_pair_end_to_end(tmp_path, monkeypatch, capsys):
    """Two co-located synthetic 'TC' GeoTIFFs at the LLD paths register and are stored."""
    rj = _script("run_jaxa")
    monkeypatch.chdir(tmp_path)
    src, ref = _pair()
    src_path = Path(rj.SAME_SOURCE_GLOB.replace("*", "S"))
    ref_path = Path(rj.SAME_REFERENCE_GLOB.replace("*", "R"))
    _tif(src_path, src.astype(np.int16), EQC0, x0=672000.0, y0=612000.0, px=10.0, nodata=-32768)
    _tif(ref_path, ref.astype(np.int16), EQC0, x0=672000.0, y0=612000.0, px=10.0, nodata=-32768)
    store = tmp_path / "store"
    assert rj.main(["--root", str(store), "--matchers", "sift", "--only-pair", "same"]) == 0, (
        capsys.readouterr().out
    )
    from lunar_reg.results import load_pair

    r = load_pair("JAXA_SELENE_TC-JAXA_SELENE_TC_sift", store)
    assert r.source_sensor == r.reference_sensor == "JAXA_SELENE_TC"
    assert r.extra["common_gsd_m"] == pytest.approx(10.0)
    assert r.extra["crop_bounds"] == pytest.approx([672000.0, 608800.0, 675200.0, 612000.0])
    assert r.extra["common_gsd_m_source"] == "computed"
    assert r.extra["crop_bounds_source"] == "computed"
    assert r.extra["source_file"] == str(src_path)
    assert "pair_prep" in r.extra and "+proj=eqc" in r.extra["crs"]


def test_prepare_same_caps_the_longest_side_and_detects_no_overlap(tmp_path, monkeypatch):
    rj = _script("run_jaxa")
    monkeypatch.chdir(tmp_path)
    rng = np.random.default_rng(0)
    big = rng.integers(1, 1000, (300, 2400), dtype=np.int16)
    src_path = Path(rj.SAME_SOURCE_GLOB.replace("*", "S"))
    ref_path = Path(rj.SAME_REFERENCE_GLOB.replace("*", "R"))
    _tif(src_path, big, EQC0, x0=0.0, y0=3000.0, px=10.0, nodata=-32768)
    _tif(ref_path, big, EQC0, x0=4000.0, y0=3000.0, px=10.0, nodata=-32768)
    pair = rj.prepare_same()
    assert pair.status is rj.PairPrepStatus.OK
    # intersection 20000 m x 3000 m; g = max(10, 20000 / 1152)
    assert pair.gsd_m == pytest.approx(20000.0 / 1152)
    assert max(pair.source.shape) <= 1152 and pair.source.shape == pair.reference.shape
    assert pair.extra["crop_bounds"] == pytest.approx([4000.0, 0.0, 24000.0, 3000.0])

    _tif(ref_path, big, EQC0, x0=90000.0, y0=3000.0, px=10.0, nodata=-32768)
    assert rj.prepare_same().status is rj.PairPrepStatus.NO_OVERLAP


def test_prepare_cross_reprojects_onto_the_wac_grid(tmp_path, monkeypatch):
    """A 'TC' in eqc lon_0=180 over the middle of a 'WAC' grid in eqc lon_0=0."""
    rj = _script("run_jaxa")
    monkeypatch.chdir(tmp_path)
    rng = np.random.default_rng(1)
    wac_x0, wac_y0 = 3011000.0, 30000.0
    _tif(
        Path(rj.CROSS_REFERENCE_GLOB),
        rng.integers(1, 255, (60, 60), dtype=np.uint8),
        EQC0,
        x0=wac_x0,
        y0=wac_y0,
        px=100.0,
        nodata=0,
    )
    # TC covers WAC columns/rows 20..40 (2000 m) at 20 m/px, in the lon_0=180 frame.
    tc_x0 = wac_x0 + 2000.0 - math.pi * MOON_R
    tc_path = Path(rj.CROSS_SOURCE_GLOB.replace("*", "TC"))
    _tif(
        tc_path,
        rng.integers(1, 1000, (100, 100), dtype=np.int16),
        EQC180,
        x0=tc_x0,
        y0=wac_y0 - 2000.0,
        px=20.0,
        nodata=-32768,
    )
    pair = rj.prepare_cross()
    assert pair.status is rj.PairPrepStatus.OK, pair.detail
    assert pair.reference_sensor == "LRO_WAC" and pair.gsd_m == pytest.approx(100.0)
    assert pair.source.shape == pair.reference.shape
    assert 19 <= pair.source.shape[0] <= 22 and 19 <= pair.source.shape[1] <= 22
    left, bottom, right, top = pair.extra["crop_bounds"]
    assert left == pytest.approx(wac_x0 + 2000.0, abs=100.0)
    assert top == pytest.approx(wac_y0 - 2000.0, abs=100.0)
    assert pair.extra["georeference_status"] == "ran"
    assert pair.source_valid.mean() > 0.5
    # g is the WAC grid's own pixel size (archive metadata); the crop box is derived.
    assert pair.extra["common_gsd_m_source"] == "documented"
    assert pair.extra["crop_bounds_source"] == "computed"


# ---------------------------------------------------------------------------
# scripts/run_ablation.py
# ---------------------------------------------------------------------------


def test_run_ablation_skip_anchor_writes_a_valid_ablation(tmp_path, monkeypatch, capsys):
    from lunar_reg.preprocess.presets import PRESET_NAMES
    from lunar_reg.runrecord import validate_run_record

    ra = _script("run_ablation")
    monkeypatch.setattr(ra, "AZIMUTH_DELTAS", (0,))
    monkeypatch.setattr(ra, "SEEDS", (0,))
    code = ra.main(
        [
            "--skip-anchor",
            "--presets",
            "none,clahe_shadow",
            "--matchers",
            "sift",
            "--out",
            str(tmp_path),
        ]
    )
    assert code == 0
    doc = json.loads((tmp_path / "ablation.json").read_text())
    assert doc["winner"] in PRESET_NAMES and doc["reason"]
    assert doc["anchor"] == []
    assert len(doc["synthetic"]) == 2  # 2 presets x 1 matcher x 1 delta x 1 seed
    for row in doc["synthetic"]:
        assert row["label"] == "SYNTHETIC"
        assert {"preset", "matcher", "azimuth_delta_deg", "seed", "status", "truth_rms_px"} <= set(
            row
        )
    assert doc["labels"]["synthetic"] == "SYNTHETIC"
    assert doc["value_sources"]["truth_rms_px"] == "computed"
    assert validate_run_record(tmp_path / "run_record.json") == []
    assert f"winner: {doc['winner']}" in capsys.readouterr().out


def test_run_ablation_samples_synthetic_failures(tmp_path, monkeypatch, capsys):
    """A failed synthetic row keeps its detail; the first sample per status is printed and
    written to the run record (convention 2)."""
    import lunar_reg.pipeline as pipeline_mod

    ra = _script("run_ablation")
    monkeypatch.setattr(ra, "AZIMUTH_DELTAS", (0,))
    monkeypatch.setattr(ra, "SEEDS", (0,))

    def boom(*args, **kwargs):
        raise RuntimeError("CUDA out of memory (simulated)")

    monkeypatch.setattr(pipeline_mod, "_build_matcher", boom)
    code = ra.main(
        ["--skip-anchor", "--presets", "none", "--matchers", "sift", "--out", str(tmp_path)]
    )
    assert code == 1
    doc = json.loads((tmp_path / "ablation.json").read_text())
    (row,) = doc["synthetic"]
    assert row["status"] == "matcher_error"
    assert "CUDA out of memory (simulated)" in row["detail"]
    assert row["pair_id"] == "synthetic_d0_s0_none_sift"
    out = capsys.readouterr().out
    assert "synthetic_matcher_error: 1  e.g. synthetic_d0_s0_none_sift: " in out
    assert "CUDA out of memory (simulated)" in out
    rr = json.loads((tmp_path / "run_record.json").read_text())
    assert "CUDA out of memory (simulated)" in rr["notes"]
    assert rr["outcome_counts"] == {"synthetic_matcher_error": 1}


def test_run_ablation_rejects_unknown_presets(tmp_path):
    ra = _script("run_ablation")
    assert (
        ra.main(["--skip-anchor", "--skip-synthetic", "--presets", "bogus", "--out", str(tmp_path)])
        == 2
    )


def test_anchor_rows_one_per_matcher_including_unrun():
    from lunar_reg.pipeline import RunOutcome, RunStatus

    ra = _script("run_ablation")
    ok_result = SimpleNamespace(n_inliers=42, uniformity={"score": 0.81})
    ok = RunOutcome("p_sift", RunStatus.OK, result=ok_result, extra={"matcher": "sift"})
    bad = RunOutcome(
        "p_akaze",
        RunStatus.TOO_FEW_INLIERS,
        detail="after refit: 5",
        extra={"matcher": "akaze", "n_refit_inliers": 5},
    )
    prep = SimpleNamespace(is_failure=False, value="ok")
    report = SimpleNamespace(
        runs=[SimpleNamespace(product_id="X", prep=prep, prep_detail="", outcomes=[ok, bad])]
    )
    rows = ra.anchor_rows(report, "none", ("sift", "akaze", "lightglue"))
    by = {r["matcher"]: r for r in rows}
    assert by["sift"] == {
        "preset": "none",
        "matcher": "sift",
        "status": "ok",
        "n_inliers": 42,
        "u_score": pytest.approx(0.81),
        "pair_id": "p_sift",
    }
    assert by["akaze"]["status"] == "too_few_inliers" and by["akaze"]["n_inliers"] == 5
    assert by["akaze"]["u_score"] == 0.0
    assert by["lightglue"]["status"] == "not_run" and by["lightglue"]["n_inliers"] == 0

    empty = ra.anchor_rows(SimpleNamespace(runs=[]), "ohrc_nac", ("sift",))
    assert empty[0]["status"] == "not_run" and "not selected" in empty[0]["detail"]


@pytest.fixture(autouse=True)
def _no_argv_leak(monkeypatch):
    # start_run records sys.argv only when main() is called without argv; keep it stable.
    monkeypatch.setattr(sys, "argv", ["pytest"])
