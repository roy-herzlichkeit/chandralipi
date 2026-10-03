"""Site runner GPU + native mode (Phase_2/LLD/runner_gpu_runs.md §P2.10).

Monkeypatched I/O as in tests/test_site_runner.py (P1.16): the catalog,
georeference and pair preparation are stubs, the native windows are read from
small GeoTIFFs in tmp, and ``refine_native_arrays`` is a stub that records the
prior it is given.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
ANCHOR = "20240425T1406019344"
PROJ = "+proj=stere +lat_0=-90 +lat_ts=-69.3 +lon_0=32.3 +R=1737400 +units=m"
#: (row_off, col_off, height, width) of the native windows used below
SRC_WIN = (5, 7, 64, 64)
REF_WIN = (10, 20, 96, 96)


def _to_native(x0, y0, native_wh, working_wh):
    fx, fy = native_wh[0] / working_wh[0], native_wh[1] / working_wh[1]
    return np.array([[fx, 0.0, x0 + (fx - 1) / 2], [0.0, fy, y0 + (fy - 1) / 2], [0, 0, 1.0]])


def _window_pair(**over):
    from lunar_reg.eval.scenes import illumination_pair
    from lunar_reg.pairs import PriorSource, WindowPair

    src, ref, H, _ = illumination_pair(
        shape=(256, 256), seed=0, source_sun=(300, 30), reference_sun=(300, 30)
    )
    ones = np.ones_like(src, bool)
    pair = WindowPair(
        source=src, reference=ref, source_valid=ones, reference_valid=ones.copy(), prior=H,
        prior_source=PriorSource.LABEL_CORNERS, gsd_m=4.0, source_window=SRC_WIN,
        reference_window=REF_WIN, source_native_gsd_m=0.5, reference_native_gsd_m=1.0,
        source_to_native=_to_native(SRC_WIN[1], SRC_WIN[0], (64, 64), (256, 256)),
        reference_to_native=_to_native(REF_WIN[1], REF_WIN[0], (96, 96), (256, 256)),
        shift_m=(0.0, 0.0), source_id="src", reference_id="NAC_REF",
        provenance={"src_gsd": "documented", "reference_georef": "inferred"},
    )  # fmt: skip
    return dataclasses.replace(pair, **over)


def _write_tif(path: Path, array: np.ndarray) -> Path:
    import rasterio

    with rasterio.open(path, "w", driver="GTiff", height=array.shape[0], width=array.shape[1],
                       count=1, dtype=array.dtype.name) as ds:  # fmt: skip
        ds.write(array, 1)
    return path


def _translation(x, y):
    return np.array([[1.0, 0, x], [0, 1.0, y], [0, 0, 1.0]])


@pytest.fixture
def env(monkeypatch, tmp_path):
    """Patched catalog/georeference/prep/open_product, stub refine, counted register_pair."""
    import rasterio

    from lunar_reg.align.native import NativeRefinement, NativeStatus
    from lunar_reg.ingest.catalog import CatalogEntry, InstrumentStatus, ProductCatalog
    from lunar_reg.ingest.lro import GeoReference
    from lunar_reg.ingest.manifest import ScanDiagnostics
    from lunar_reg.match.tiled import TileDiagnostics, TileOutcome, TileStatus
    from lunar_reg.pairs import PrepOutcome, PrepStatus
    from lunar_reg.provenance import ValueSource
    from lunar_reg.sites import runner

    label = tmp_path / f"ch2_ohr_nrp_{ANCHOR}_d_img_d18.xml"
    label.write_text("<x/>")
    entry = CatalogEntry(instrument="OHRC", product_id=label.stem, label_path=label,
                         image_path=None, level="raw", product_type="data",
                         geometry_grid_path=None)  # fmt: skip
    status = {
        k: InstrumentStatus.ABSENT
        for k in ("OHRC", "TMC2", "IIRS", "LRO_NAC", "LRO_NAC_DTM", "SELENE_TC")
    }
    status["OHRC"] = status["LRO_NAC"] = InstrumentStatus.PRESENT
    cat = ProductCatalog(entries=[entry], status=status, diagnostics=ScanDiagnostics())
    monkeypatch.setattr(runner, "build_catalog", lambda *a, **k: cat)
    geo = GeoReference(PROJ, 1000.0, 2000.0, 1.0, 1.0, 5000, 5000, ValueSource.INFERRED)
    monkeypatch.setattr(runner, "georeference_from_label", lambda *a, **k: geo)
    state = {"pair": _window_pair(), "open_error": None}
    monkeypatch.setattr(
        runner, "prepare_window_pair", lambda *a, **k: PrepOutcome(PrepStatus.OK, state["pair"])
    )

    rng = np.random.default_rng(1)
    src_tif = _write_tif(tmp_path / "src.tif", rng.integers(1, 4000, (100, 100), dtype=np.uint16))
    ref_arr = rng.uniform(1, 255, (200, 200)).astype(np.float32)
    ref_arr[:3] = np.nan  # outside the reference window; invalid pixels are zeroed anyway
    ref_tif = _write_tif(tmp_path / "ref.tif", ref_arr)
    opened: list[str] = []

    def fake_open(path):
        path = Path(path)
        opened.append(path.name)
        if path.suffix == ".xml":
            if state["open_error"] is not None:
                raise state["open_error"]
            return rasterio.open(src_tif)
        return rasterio.open(path)

    monkeypatch.setattr(runner, "open_product", fake_open)

    refine_calls: list[dict] = []
    result = {"status": NativeStatus.OK, "transform": None, "drift": 0.125, "keep_transform": True}

    def stub_refine(source, reference, prior, **kw):
        refine_calls.append({"source": source, "reference": reference, "prior": prior, **kw})
        tiles = TileDiagnostics()
        tiles.record(TileOutcome(0, TileStatus.OK, 30, "", (0, 0, 32, 32), (0, 0, 40, 40)))
        tiles.record(TileOutcome(1, TileStatus.EMPTY, 0, "", (0, 32, 32, 32), (0, 30, 40, 40)))
        tiles.record(TileOutcome(2, TileStatus.OK, 20, "", (32, 0, 32, 32), (30, 0, 40, 40)))
        transform = prior if result["transform"] is None else result["transform"]
        if not result["keep_transform"]:
            transform = None
        return NativeRefinement(result["status"], transform, 50, 40, result["drift"], tiles, "")

    monkeypatch.setattr(runner, "refine_native_arrays", stub_refine)

    calls: list[dict] = []
    real = runner.register_pair

    def counting(*a, **k):
        calls.append({"args": a, **k})
        return real(*a, **k)

    monkeypatch.setattr(runner, "register_pair", counting)

    def cfg(**kw):
        base = dict(
            matchers=("sift",),
            coarse=False,
            prior_shift_m=None,
            results_root=tmp_path / "store",
            out_dir=tmp_path / "out",
            save_registered=False,
            reference_sun_json=None,
            label_convention_json=None,
            reference_label=ref_tif,
        )
        base.update(kw)
        return runner.SiteConfig(**base)

    return {"runner": runner, "tmp": tmp_path, "cfg": cfg, "state": state, "geo": geo,
            "calls": calls, "refine_calls": refine_calls, "result": result, "opened": opened,
            "src_tif": src_tif, "ref_arr": ref_arr}  # fmt: skip


def _stored(env, matcher="sift"):
    from lunar_reg.results import load_pair

    return load_pair(f"CH2_OHRC_RAW_{ANCHOR}-LRO_NAC_ORTHO_{matcher}", env["tmp"] / "store")


def _counts(env) -> dict:
    return json.loads((env["tmp"] / "out" / "run_record.json").read_text())["outcome_counts"]


# ---------------------------------------------------------------------------
# defaults and native off
# ---------------------------------------------------------------------------


def test_defaults_keep_phase1_behaviour():
    from lunar_reg.sites.runner import SiteConfig

    cfg = SiteConfig()
    assert cfg.device is None and cfg.precision == "auto" and cfg.native is False
    assert cfg.native_matcher == "sift" and cfg.native_tile_px is None
    assert cfg.native_max_drift_coarse_px == 1.0


def test_native_off_no_native_keys(env):
    rep = env["runner"].run_site(env["cfg"](native=False))
    assert rep.any_ok and not env["refine_calls"] and not env["opened"]
    stored = _stored(env)
    assert not [k for k in stored.extra if k.startswith("native_")]
    assert rep.native is None and "native refinement" not in rep.report()
    assert not [k for k in _counts(env) if k.startswith("native_")]


def test_native_run_status_mirrors_native_status():
    from lunar_reg.align.native import NativeStatus
    from lunar_reg.sites.runner import NativeRunStatus

    assert {s.value for s in NativeStatus} <= {s.value for s in NativeRunStatus}
    assert not NativeRunStatus.NOT_APPLICABLE.is_failure
    assert not NativeRunStatus.NOT_SAVED.is_failure
    assert NativeRunStatus.READ_FAILED.is_failure and NativeRunStatus.DRIFT_EXCEEDED.is_failure


# ---------------------------------------------------------------------------
# native on
# ---------------------------------------------------------------------------


def test_native_keys_present_and_prior_in_window_px(env):
    from lunar_reg.align.native import lift_to_native

    rep = env["runner"].run_site(env["cfg"](native=True, native_tile_px=256,
                                            native_max_drift_coarse_px=0.5))  # fmt: skip
    assert rep.any_ok and len(env["refine_calls"]) == 1
    stored = _stored(env)
    extra = stored.extra
    for key in ("native_status", "native_n_matches", "native_n_inliers",
                "native_drift_coarse_px", "native_transform", "native_gsd_m",
                "native_tiles_ok", "native_tiles_empty", "native_provenance"):  # fmt: skip
        assert key in extra, key
    assert extra["native_status"] == "ok"
    assert extra["native_n_matches"] == 50 and extra["native_n_inliers"] == 40
    assert extra["native_drift_coarse_px"] == 0.125 and extra["native_gsd_m"] == 1.0
    assert extra["native_tiles_ok"] == 2 and extra["native_tiles_empty"] == 1
    prov = json.loads(extra["native_provenance"])
    assert prov["n_inliers"] == "measured" and prov["native_gsd_m"] == "inferred"

    pair = env["state"]["pair"]
    prior_full = lift_to_native(stored.transform, pair.source_to_native, pair.reference_to_native)
    call = env["refine_calls"][0]
    # the arrays are windows: the prior is moved into window px
    expected = np.linalg.inv(_translation(20, 10)) @ prior_full @ _translation(7, 5)
    np.testing.assert_allclose(call["prior"], expected, atol=1e-9)
    # the stub returns the prior unchanged, so the stored transform is the full-frame prior
    native_t = np.array(json.loads(extra["native_transform"])).reshape(3, 3)
    np.testing.assert_allclose(native_t, prior_full, atol=1e-9)
    assert call["source"].shape == (64, 64) and call["reference"].shape == (96, 96)
    assert call["matcher"] == "sift" and call["tile_px"] == 256
    assert call["source_native_gsd_m"] == 0.5 and call["reference_native_gsd_m"] == 1.0
    assert call["coarse_gsd_m"] == 4.0 and call["max_drift_coarse_px"] == 0.5
    # the windows hold the right pixels (source rows 5.., cols 7..; reference rows 10.., cols 20..)
    import rasterio

    with rasterio.open(env["src_tif"]) as ds:
        np.testing.assert_array_equal(call["source"], ds.read(1)[5:69, 7:71])
    np.testing.assert_array_equal(call["reference"], env["ref_arr"][10:106, 20:116])

    text = rep.report()
    assert "native refinement: 1 strip(s), 1 ok, 0 failed" in text and "native ok" in text
    counts = _counts(env)
    assert counts["native_ok"] == 1 and counts["native_read_failed"] == 0


def test_only_native_matcher_is_refined(env):
    rep = env["runner"].run_site(env["cfg"](native=True, native_matcher="akaze",
                                            matchers=("sift", "akaze")))  # fmt: skip
    assert rep.any_ok and len(env["refine_calls"]) == 1
    assert "native_status" in _stored(env, "akaze").extra
    assert "native_status" not in _stored(env, "sift").extra


def test_native_matcher_not_among_matchers_is_setup_error(env):
    with pytest.raises(ValueError, match="native_matcher"):
        env["runner"].run_site(env["cfg"](native=True, native_matcher="akaze"))


def test_failed_refinement_is_classified(env):
    from lunar_reg.align.native import NativeStatus

    env["result"]["status"] = NativeStatus.DRIFT_EXCEEDED
    rep = env["runner"].run_site(env["cfg"](native=True, save_registered=True))
    extra = _stored(env).extra
    assert extra["native_status"] == "drift_exceeded"
    assert "native_geotiff" not in extra  # only an OK refinement is written
    assert "native refinement: 1 strip(s), 0 ok, 1 failed" in rep.report()
    assert _counts(env)["native_drift_exceeded"] == 1


def test_source_coarser_than_reference_not_applicable(env):
    env["state"]["pair"] = _window_pair(source_native_gsd_m=5.0)
    rep = env["runner"].run_site(env["cfg"](native=True))
    extra = _stored(env).extra
    assert extra["native_status"] == "not_applicable" and "coarser" in extra["native_detail"]
    assert not env["refine_calls"] and not env["opened"]
    assert "0 failed" in rep.report() and _counts(env)["native_not_applicable"] == 1


def test_read_failure_is_classified(env):
    env["state"]["open_error"] = OSError("no such file")
    rep = env["runner"].run_site(env["cfg"](native=True))
    extra = _stored(env).extra
    assert extra["native_status"] == "read_failed" and "no such file" in extra["native_detail"]
    assert not env["refine_calls"]
    text = rep.report()
    assert "1 failed" in text and "read_failed: 1" in text
    assert _counts(env)["native_read_failed"] == 1


#: the stored keys LLD §P2.10 lists, present on every classified native outcome
_LLD_NATIVE_KEYS = ("native_status", "native_n_matches", "native_n_inliers",
                    "native_drift_coarse_px", "native_transform", "native_gsd_m")  # fmt: skip


def _scored_native_row(env):
    """The anchor's native row as Phase_2/benchmark/score.py q_native reads it."""
    from lunar_reg.results import load_index

    idx = load_index(env["tmp"] / "store")
    rows = idx[idx["pair_id"].str.contains(ANCHOR)]
    return rows[rows["x_native_status"].notna()].iloc[0]


@pytest.mark.parametrize("case", ["not_applicable", "read_failed", "rejected"])
def test_unrefined_outcomes_store_the_full_key_set(env, monkeypatch, case):
    import math

    if case == "not_applicable":
        env["state"]["pair"] = _window_pair(source_native_gsd_m=5.0)
    elif case == "read_failed":
        env["state"]["open_error"] = OSError("no such file")
    else:

        def raising(*a, **k):
            raise ValueError("bad prior")

        monkeypatch.setattr(env["runner"], "refine_native_arrays", raising)
    env["runner"].run_site(env["cfg"](native=True))
    extra = _stored(env).extra
    assert extra["native_status"] == case
    for key in _LLD_NATIVE_KEYS:
        assert key in extra, key
    assert extra["native_n_matches"] is None and extra["native_n_inliers"] is None
    assert extra["native_transform"] is None and math.isnan(extra["native_drift_coarse_px"])
    assert extra["native_gsd_m"] == 1.0
    assert json.loads(extra["native_provenance"]) == {"native_gsd_m": "inferred"}
    # the benchmark scorer's read of the row works (no KeyError / TypeError)
    row = _scored_native_row(env)
    assert row["x_native_status"] == case
    assert math.isnan(float(row["x_native_drift_coarse_px"]))


def test_refinement_without_transform_or_drift_keeps_the_columns(env):
    import math

    from lunar_reg.align.native import NativeStatus

    env["result"].update(status=NativeStatus.TOO_FEW_MATCHES, drift=None, keep_transform=False)
    env["runner"].run_site(env["cfg"](native=True))
    extra = _stored(env).extra
    assert extra["native_status"] == "too_few_matches"
    assert extra["native_n_matches"] == 50 and extra["native_n_inliers"] == 40
    assert extra["native_transform"] is None and math.isnan(extra["native_drift_coarse_px"])
    row = _scored_native_row(env)
    assert not (row["x_native_status"] == "ok" and float(row["x_native_drift_coarse_px"]) <= 1.0)


def test_working_gsd_geotiff_keeps_phase1_validity_mask(env, monkeypatch):
    """Q-P2.09-3(a) is open: the runner does not pass ``source_valid`` (A130 ones mask)."""
    import lunar_reg.align.warp as warp

    seen: list[dict] = []
    real = warp.save_registered_geotiff

    def spy(*a, **k):
        seen.append(k)
        return real(*a, **k)

    monkeypatch.setattr(warp, "save_registered_geotiff", spy)
    env["runner"].run_site(env["cfg"](native=False, save_registered=True))
    assert len(seen) == 1 and "source_valid" not in seen[0]


def test_already_stored_result_is_not_refined(env):
    runner = env["runner"]
    runner.run_site(env["cfg"](native=True))
    rep = runner.run_site(env["cfg"](native=True))
    assert len(env["refine_calls"]) == 1 and rep.not_saved
    assert "not_saved: 1" in rep.report() and _counts(env)["native_not_saved"] == 1


def test_native_geotiff_on_reference_native_grid(env):
    import rasterio

    env["result"]["transform"] = _translation(3, 4)  # window px -> reference window px
    rep = env["runner"].run_site(env["cfg"](native=True, save_registered=True))
    assert not rep.geotiff_failures
    extra = _stored(env).extra
    pair_id = f"CH2_OHRC_RAW_{ANCHOR}-LRO_NAC_ORTHO_sift"
    path = env["tmp"] / "out" / "registered" / f"{pair_id}_native.tif"
    assert extra["native_geotiff"] == str(path) and path.exists()
    # the working-GSD GeoTIFF is still written beside it
    assert extra["registered_geotiff"].endswith(f"{pair_id}.tif")
    with rasterio.open(env["src_tif"]) as ds:
        src = ds.read(1)[5:69, 7:71]
    with rasterio.open(path) as ds:
        assert (ds.height, ds.width) == (96, 96) and ds.crs is not None
        # reference window origin: geo (1000, 2000) + (col 20, row 10) at 1 m
        assert ds.transform.c == pytest.approx(1020.0) and ds.transform.f == pytest.approx(1990.0)
        assert ds.transform.a == pytest.approx(1.0) and ds.transform.e == pytest.approx(-1.0)
        out = ds.read(1)
    assert out[4 + 10, 3 + 10] == src[10, 10]
    assert out[0, 0] == 0  # outside the warped source window: nodata
    rr = json.loads((env["tmp"] / "out" / "run_record.json").read_text())
    assert any(a.endswith("_native.tif") for a in rr["artefacts"])


def test_native_geotiff_write_failure_reported(env, monkeypatch):
    import lunar_reg.align.warp as warp

    def broken(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(warp, "warp_blockwise", broken)
    rep = env["runner"].run_site(env["cfg"](native=True, save_registered=True))
    extra = _stored(env).extra
    assert extra["native_status"] == "ok" and "disk full" in extra["native_geotiff_error"]
    assert any("(native)" in f for f in rep.geotiff_failures)
    assert _counts(env)["native_geotiff_write_failed"] == 1


# ---------------------------------------------------------------------------
# device / precision into every PipelineConfig
# ---------------------------------------------------------------------------


def test_device_and_precision_reach_every_pipeline_config(env):
    rep = env["runner"].run_site(
        env["cfg"](device="cpu", precision="fp32", coarse=True, coarse_matcher="sift")
    )
    assert rep.any_ok and len(env["calls"]) == 2  # coarse + fine
    for call in env["calls"]:
        config = call["args"][3]
        assert config.device == "cpu" and config.precision == "fp32"


# ---------------------------------------------------------------------------
# CLI flags
# ---------------------------------------------------------------------------


def _run_vikram():
    spec = importlib.util.spec_from_file_location("_rv_native", REPO / "scripts" / "run_vikram.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _cli_cfg(monkeypatch, argv):
    from types import SimpleNamespace

    from lunar_reg.sites import runner

    seen = {}

    def fake(cfg):
        seen["cfg"] = cfg
        return SimpleNamespace(any_ok=True, report=str)

    monkeypatch.setattr(runner, "run_site", fake)
    assert _run_vikram().main(argv) == 0
    return seen["cfg"]


def test_cli_native_flags(monkeypatch):
    cfg = _cli_cfg(monkeypatch, ["--matchers", "sift,akaze", "--device", "cuda",
                                 "--precision", "fp16", "--native", "--native-matcher", "akaze",
                                 "--native-tile-px", "256"])  # fmt: skip
    assert cfg.device == "cuda" and cfg.precision == "fp16"
    assert cfg.native and cfg.native_matcher == "akaze" and cfg.native_tile_px == 256


def test_cli_defaults_keep_native_off(monkeypatch):
    cfg = _cli_cfg(monkeypatch, [])
    assert cfg.device is None and cfg.precision == "auto"
    assert cfg.native is False and cfg.native_matcher == "sift" and cfg.native_tile_px is None
