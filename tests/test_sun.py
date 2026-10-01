"""Sun geometry (ingest/sun.py, CONTRACTS C13, Phase_1/LLD/sun_geometry.md §3)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from lunar_reg.ingest.sun import (
    AzimuthFit,
    SunGeometry,
    azimuth_elevation_from_vector,
    fit_sun_azimuth,
    lambert_shade,
    north_to_grid_azimuth,
    sun_from_label,
    sun_from_ode_metadata,
    sun_from_spice,
)
from lunar_reg.provenance import ValueSource

REPO = Path(__file__).resolve().parents[1]
KERNELS = REPO / "data/raw/reference/spice"
ODE_JSON = REPO / "data/raw/reference/lro_nac_vikram/ode/edrnac4_vikram_box.json"
NAC_PROJ = "+proj=stere +lat_0=-90 +lat_ts=-69.3 +lon_0=32.3 +R=1737400 +units=m +no_defs"


def _circ(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


# --------------------------------------------------------------- vector geometry


def test_vector_geometry_at_origin():
    az, el = azimuth_elevation_from_vector(np.array([1.0, 0.0, 0.0]), 0.0, 0.0)
    assert el == pytest.approx(90.0, abs=1e-9)
    az, el = azimuth_elevation_from_vector(np.array([0.0, 3.0, 0.0]), 0.0, 0.0)
    assert (az, el) == pytest.approx((90.0, 0.0), abs=1e-9)
    az, el = azimuth_elevation_from_vector(np.array([0.0, 0.0, 0.5]), 0.0, 0.0)
    assert _circ(az, 0.0) < 1e-9 and el == pytest.approx(0.0, abs=1e-9)
    assert 0.0 <= az < 360.0


def test_vector_geometry_east_at_vikram():
    lon = np.radians(32.32)
    east = np.array([-np.sin(lon), np.cos(lon), 0.0])
    az, el = azimuth_elevation_from_vector(east, -69.37, 32.32)
    assert (az, el) == pytest.approx((90.0, 0.0), abs=1e-9)
    az, _ = azimuth_elevation_from_vector(-east, -69.37, 32.32)
    assert az == pytest.approx(270.0, abs=1e-9)


def test_vector_geometry_zero_vector_raises():
    with pytest.raises(ValueError):
        azimuth_elevation_from_vector(np.zeros(3), 0.0, 0.0)


# ------------------------------------------------------------------ grid frame


def test_north_to_grid_on_central_meridian_is_identity():
    for az in (0.0, 123.0, 359.5):
        assert _circ(north_to_grid_azimuth(az, -69.37, 32.3, NAC_PROJ), az) < 1e-6


def test_north_to_grid_off_meridian_rotates():
    off = north_to_grid_azimuth(123.0, -69.37, 42.3, NAC_PROJ)
    assert _circ(off, 123.0) > 1.0


# ------------------------------------------------------------- hillshade + fit


def test_lambert_shade_flat_and_nan():
    s = lambert_shade(np.zeros((8, 8)), 3.0, 200.0, 25.0)
    assert s.dtype == np.float32
    assert np.allclose(s, np.sin(np.radians(25.0)), atol=1e-6)
    dtm = np.zeros((8, 8))
    dtm[3, 3] = np.nan
    assert np.isnan(lambert_shade(dtm, 3.0, 200.0, 25.0)[3, 3])


def test_lambert_shade_south_facing_slope_lit_by_south_sun():
    rows = np.arange(64, dtype=float)[:, None]
    dtm = np.tile(-0.5 * rows, (1, 64))  # height falls southward (image-down)
    south = float(np.nanmean(lambert_shade(dtm, 1.0, 180.0, 20.0)))
    north = float(np.nanmean(lambert_shade(dtm, 1.0, 0.0, 20.0)))
    assert south > north


def test_synthetic_azimuth_recovered():
    from lunar_reg.eval.scenes import add_craters, fractal_terrain

    dtm = add_craters(fractal_terrain((256, 256), seed=3), seed=3).astype(np.float64) * 30.0
    image = lambert_shade(dtm, 3.0, 137.0, 16.0)
    image = image + np.random.default_rng(7).normal(0, 0.01, image.shape)
    fit = fit_sun_azimuth(dtm, 3.0, image, 16.0)
    assert isinstance(fit, AzimuthFit)
    assert _circ(fit.azimuth_deg, 137.0) <= 2.0, fit.azimuth_deg
    assert fit.peak_margin > 0 and fit.n_valid_px > 0
    assert _circ(fit.second_peak_deg, fit.azimuth_deg) >= 20.0
    assert len(fit.azimuths) == len(fit.ncc) == 360


def test_fit_respects_valid_mask_and_step():
    from lunar_reg.eval.scenes import add_craters, fractal_terrain

    dtm = add_craters(fractal_terrain((128, 128), seed=1), seed=1).astype(np.float64) * 30.0
    image = lambert_shade(dtm, 3.0, 250.0, 20.0)
    valid = np.zeros(dtm.shape, bool)
    valid[:, :64] = True
    image[:, 64:] = 0.0  # garbage outside the mask must not matter
    fit = fit_sun_azimuth(dtm, 3.0, image, 20.0, valid=valid, step_deg=2.0)
    assert len(fit.azimuths) == 180
    assert fit.n_valid_px <= int(valid.sum())
    assert _circ(fit.azimuth_deg, 250.0) <= 2.0


def test_fit_shape_mismatch_raises():
    with pytest.raises(ValueError):
        fit_sun_azimuth(np.zeros((10, 10)), 3.0, np.zeros((10, 11)), 20.0)
    with pytest.raises(ValueError):
        fit_sun_azimuth(np.zeros((10, 10)), 3.0, np.zeros((10, 10)), 20.0, valid=np.ones((9, 9)))


def test_fit_flat_dtm_raises():
    with pytest.raises(ValueError):
        fit_sun_azimuth(np.zeros((16, 16)), 3.0, np.random.default_rng(0).random((16, 16)), 20.0)


# --------------------------------------------------------------------- ODE JSON


def _ode(tmp_path: Path, products) -> Path:
    path = tmp_path / "ode.json"
    doc = {"ODEResults": {"Status": "Success", "Products": {"Product": products}}}
    path.write_text(json.dumps(doc))
    return path


def test_ode_list_and_dict_forms(tmp_path):
    records = [
        {"Product_name": "M1442997156LE.IMG", "Incidence_angle": "73.84"},
        {"Product_name": "M1443025251LE.IMG", "Incidence_angle": "74.65"},
    ]
    sun = sun_from_ode_metadata(_ode(tmp_path, records), "m1443025251le")
    assert isinstance(sun, SunGeometry)
    assert sun.elevation_deg == pytest.approx(90 - 74.65)
    assert sun.elevation_source is ValueSource.DOCUMENTED
    assert sun.azimuth_deg is None and sun.azimuth_source is ValueSource.UNKNOWN
    assert sun.azimuth_frame == "grid_up_clockwise" and sun.as_tuple() is None
    assert "Product[1]" in sun.note
    single = sun_from_ode_metadata(_ode(tmp_path, records[0]), "M1442997156LE")
    assert single.elevation_deg == pytest.approx(90 - 73.84)


def test_ode_no_match(tmp_path):
    sun = sun_from_ode_metadata(
        _ode(tmp_path, [{"Product_name": "M1.IMG", "Incidence_angle": "50"}]), "M2"
    )
    assert sun.elevation_deg is None and sun.azimuth_deg is None
    assert sun.elevation_source is ValueSource.UNKNOWN and sun.azimuth_source is ValueSource.UNKNOWN
    assert sun.note == "no ODE record for M2"


# ------------------------------------------------------------------------ label


class _StubProduct:
    label_path = Path("stub.xml")

    def __init__(self, values):
        self.values = values

    def __getitem__(self, key):
        return self.values.get(key)


def test_sun_from_label_stub():
    sun = sun_from_label(_StubProduct({"sun_azimuth_deg": 61.79, "sun_elevation_deg": 8.11}))
    assert sun.as_tuple() == pytest.approx((61.79, 8.11))
    assert sun.azimuth_source is ValueSource.DOCUMENTED
    assert sun.elevation_source is ValueSource.DOCUMENTED
    assert sun.azimuth_frame == "label_unverified"
    d = sun.as_dict()
    assert d["azimuth_source"] == "documented" and d["azimuth_frame"] == "label_unverified"
    json.dumps(d)


def test_sun_from_label_missing_field():
    sun = sun_from_label(_StubProduct({"sun_elevation_deg": 8.11}))
    assert sun.azimuth_deg is None and sun.azimuth_source is ValueSource.UNKNOWN
    assert sun.elevation_source is ValueSource.DOCUMENTED and sun.as_tuple() is None
    assert "sun_azimuth_deg" in sun.note


# ------------------------------------------------------------------------ SPICE


def test_spice_missing_kernels_raises(tmp_path, monkeypatch):
    import sys
    import types

    furnished = []
    stub = types.SimpleNamespace(furnsh=furnished.append)
    monkeypatch.setitem(sys.modules, "spiceypy", stub)
    with pytest.raises(FileNotFoundError, match="naif0012.tls"):
        sun_from_spice("2023-07-03T04:18:08.914", -69.26, 32.18, tmp_path)
    assert furnished == []


def test_spice_without_spiceypy_names_the_extra(tmp_path, monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "spiceypy", None)
    with pytest.raises(ImportError, match="spice"):
        sun_from_spice("2023-07-03T04:18:08.914", -69.26, 32.18, tmp_path)


@pytest.mark.data
def test_spice_elevation_matches_ode_incidence():
    """SPICE elevation at the ODE centre/time of M1442997156LE vs ODE's 90 - incidence."""
    if not all((KERNELS / k).exists() for k in ("naif0012.tls", "pck00011.tpc", "de440s.bsp")):
        pytest.skip("SPICE kernels not fetched yet (P1.02 run step)")
    if not ODE_JSON.exists():
        pytest.skip("ODE box JSON not fetched yet (P1.02 run step)")
    try:
        import spiceypy  # noqa: F401
    except ImportError:
        pytest.skip("spiceypy not installed (spice extra, P1.11)")
    ode = sun_from_ode_metadata(ODE_JSON, "M1442997156LE")
    assert ode.elevation_deg == pytest.approx(90 - 73.84)
    sun = sun_from_spice("2023-07-03T04:18:08.914000Z", -69.2621, 32.1781, KERNELS)
    assert sun.azimuth_frame == "north_clockwise"
    assert sun.azimuth_source is ValueSource.COMPUTED
    assert sun.elevation_source is ValueSource.COMPUTED
    assert abs(sun.elevation_deg - (90.0 - 73.84)) <= 1.0
    assert 0.0 <= sun.azimuth_deg < 360.0


# ----------------------------------------------------------------------- script


def test_script_exits_2_when_inputs_missing(tmp_path, capsys, monkeypatch):
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "fit_reference_sun", REPO / "scripts/fit_reference_sun.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "ODE_JSON", tmp_path / "absent.json")
    code = mod.main(["--kernels", str(tmp_path / "nokernels"), "--out", str(tmp_path / "out")])
    assert code == 2
    err = capsys.readouterr().err
    assert "naif0012.tls" in err and "spice_lsk" in err and "absent.json" in err
    assert not (tmp_path / "out").exists()


def test_script_conventions_and_circular_diff():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "fit_reference_sun", REPO / "scripts/fit_reference_sun.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert set(mod.CONVENTIONS) == {"as_is", "plus_180", "mirror", "mirror_plus_180"}
    a = 61.0
    assert [
        mod.CONVENTIONS[k](a) % 360 for k in ("as_is", "plus_180", "mirror", "mirror_plus_180")
    ] == [
        61.0,
        241.0,
        299.0,
        119.0,
    ]
    assert mod.circular_signed(1.0, 359.0) == pytest.approx(2.0)
    assert mod.circular_signed(359.0, 1.0) == pytest.approx(-2.0)


def _load_script():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "fit_reference_sun", REPO / "scripts/fit_reference_sun.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_tif(path: Path, array: np.ndarray, x0: float, y0: float, px: float, nodata=None):
    import rasterio
    from affine import Affine

    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=array.shape[1],
        height=array.shape[0],
        count=1,
        dtype=array.dtype,
        transform=Affine(px, 0.0, x0, 0.0, -px, y0),
        nodata=nodata,
    ) as ds:
        ds.write(array, 1)


def test_script_end_to_end_synthetic(tmp_path, monkeypatch, capsys):
    """main() on SYNTHETIC rasters: hillshade at grid azimuth 137 -> fit within 2 deg of SPICE."""
    import cv2
    from rasterio.warp import transform

    from lunar_reg.eval.scenes import add_craters, fractal_terrain
    from lunar_reg.ingest import lro
    from lunar_reg.ingest.lro import GeoReference
    from lunar_reg.runrecord import validate_run_record

    mod = _load_script()
    geo_crs = "+proj=longlat +R=1737400 +no_defs"
    (cx,), (cy,) = transform(geo_crs, NAC_PROJ, [mod.SITE_LON], [mod.SITE_LAT])
    n_dtm = 400  # 1200 m at 3 m
    dtm = add_craters(fractal_terrain((n_dtm, n_dtm), seed=5), seed=5).astype(np.float32) * 30.0
    x0, y0 = round(cx) - 600.0, round(cy) + 600.0
    dtm_path = tmp_path / "dtm.tif"
    _write_tif(dtm_path, dtm, x0, y0, 3.0, nodata=-3.4028226550889045e38)
    fine = cv2.resize(dtm, (3 * n_dtm, 3 * n_dtm), interpolation=cv2.INTER_LINEAR)
    shade = lambert_shade(fine.astype(np.float64), 1.0, 137.0, 16.0)
    nac = (1 + np.nan_to_num(shade) * 4000).astype(np.uint16)
    nac_path = tmp_path / "nac.tif"
    _write_tif(nac_path, nac, x0, y0, 1.0, nodata=0)
    geo = GeoReference(NAC_PROJ, x0, y0, 1.0, 1.0, 3 * n_dtm, 3 * n_dtm, ValueSource.DOCUMENTED)
    monkeypatch.setattr(lro, "georeference_from_label", lambda path: geo)
    monkeypatch.setattr(mod, "DTM_TIF", dtm_path)
    monkeypatch.setattr(mod, "NAC_LABELS", {1: nac_path, 2: nac_path})
    ode = _ode(
        tmp_path,
        [
            {
                "Product_name": "M1442997156LE.IMG",
                "Incidence_angle": "73.84",
                "UTC_start_time": "2023-07-03T04:18:08.914000Z",
                "Center_latitude": str(mod.SITE_LAT),
                "Center_longitude": str(mod.SITE_LON),
            }
        ],
    )
    monkeypatch.setattr(mod, "ODE_JSON", ode)
    monkeypatch.setattr(mod, "missing_inputs", lambda kernels: [])
    spice_north = 137.0 + (
        137.0 - north_to_grid_azimuth(137.0, mod.SITE_LAT, mod.SITE_LON, NAC_PROJ)
    )
    fake = SunGeometry(
        spice_north, 16.0, ValueSource.COMPUTED, ValueSource.COMPUTED, "north_clockwise"
    )
    monkeypatch.setattr(mod, "sun_from_spice", lambda *a, **k: fake)
    out = tmp_path / "out"
    code = mod.main(["--half-size-m", "500", "--out", str(out)])
    printed = capsys.readouterr().out
    assert code == 0, printed
    doc = json.loads((out / "reference_sun.json").read_text())
    assert doc["sun"]["azimuth_frame"] == "north_clockwise"
    assert doc["cross_checks"]["ode_elevation_deg"] == pytest.approx(90 - 73.84)
    assert doc["cross_checks"]["elevation_diff_deg"] == pytest.approx(90 - 73.84 - 16.0)
    fit = doc["cross_checks"]["dtm_fit"]
    assert abs(fit["fit_minus_spice_deg"]) <= 2.0, fit
    assert fit["peak_margin"] > 0 and fit["n_valid_px"] > 0 and fit["source"] == "inferred"
    assert (out / "ncc_curve.csv").read_text().splitlines()[0] == "azimuth_deg,ncc"
    assert validate_run_record(out / "run_record.json") == []
    assert "dtm_fit_ok" in printed


def _run_without_dtm_fit(tmp_path, monkeypatch, mod, extra_args=()):
    """main() with SPICE faked, the ODE record present and the DTM fit unable to produce a value."""
    ode = _ode(
        tmp_path,
        [
            {
                "Product_name": "M1442997156LE.IMG",
                "Incidence_angle": "73.84",
                "UTC_start_time": "2023-07-03T04:18:08.914000Z",
                "Center_latitude": str(mod.SITE_LAT),
                "Center_longitude": str(mod.SITE_LON),
            }
        ],
    )
    monkeypatch.setattr(mod, "ODE_JSON", ode)
    monkeypatch.setattr(mod, "missing_inputs", lambda kernels: [])
    fake = SunGeometry(140.0, 16.0, ValueSource.COMPUTED, ValueSource.COMPUTED, "north_clockwise")
    monkeypatch.setattr(mod, "sun_from_spice", lambda *a, **k: fake)
    out = tmp_path / "out"
    code = mod.main(["--out", str(out), *extra_args])
    return code, out


def _assert_empty_dtm_fit(fit: dict, outcome: str) -> None:
    for key in (
        "azimuth_grid_deg",
        "ncc_peak",
        "second_peak_deg",
        "second_peak_ncc",
        "peak_margin",
        "n_valid_px",
        "step_deg",
        "fit_minus_spice_deg",
    ):
        assert key in fit and fit[key] is None, (key, fit)
    assert fit["source"] == ValueSource.UNKNOWN.value
    assert fit["note"].startswith(outcome)


def test_script_dtm_input_missing_writes_all_keys_unknown(tmp_path, monkeypatch, capsys):
    mod = _load_script()
    monkeypatch.setattr(mod, "DTM_TIF", tmp_path / "absent_dtm.tif")
    code, out = _run_without_dtm_fit(tmp_path, monkeypatch, mod)
    printed = capsys.readouterr().out
    assert code == 1, printed
    doc = json.loads((out / "reference_sun.json").read_text())
    _assert_empty_dtm_fit(doc["cross_checks"]["dtm_fit"], "dtm_input_missing")
    assert "dtm_input_missing" in printed
    assert not (out / "ncc_curve.csv").exists()


def test_script_dtm_fit_failed_writes_all_keys_unknown(tmp_path, monkeypatch, capsys):
    mod = _load_script()
    dtm, label = tmp_path / "dtm.tif", tmp_path / "nac.xml"
    dtm.write_bytes(b"")
    label.write_bytes(b"")
    monkeypatch.setattr(mod, "DTM_TIF", dtm)
    monkeypatch.setattr(mod, "NAC_LABELS", {1: label, 2: label})

    def boom(*a, **k):
        raise ValueError("synthetic failure")

    monkeypatch.setattr(mod, "dtm_cross_check", boom)
    code, out = _run_without_dtm_fit(tmp_path, monkeypatch, mod)
    printed = capsys.readouterr().out
    assert code == 1, printed
    fit = json.loads((out / "reference_sun.json").read_text())["cross_checks"]["dtm_fit"]
    _assert_empty_dtm_fit(fit, "dtm_fit_failed")
    assert "synthetic failure" in fit["note"]


def test_script_label_convention_without_labels_is_unknown(tmp_path, monkeypatch, capsys):
    from lunar_reg.ingest import catalog

    class _EmptyCatalog:
        def products(self, instrument, product_type="data"):
            return []

    mod = _load_script()
    monkeypatch.setattr(mod, "DTM_TIF", tmp_path / "absent_dtm.tif")
    monkeypatch.setattr(catalog, "build_catalog", lambda *a, **k: _EmptyCatalog())
    code, out = _run_without_dtm_fit(tmp_path, monkeypatch, mod, ["--label-convention"])
    capsys.readouterr()
    assert code == 1
    conv = json.loads((out / "label_convention.json").read_text())
    assert conv["per_strip"] == [] and conv["convention"] is None
    assert conv["max_diff_deg"] is None and conv["elevation_max_diff_deg"] is None
    assert conv["source"] == ValueSource.UNKNOWN.value
