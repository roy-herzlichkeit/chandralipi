"""Phase 1 contract tests: CONTRACTS.md C03 (preprocess), C08-C14, C20 (G16). Protected (G05)."""

from __future__ import annotations

import dataclasses
import inspect
import json

import numpy as np
import pytest
from _h1 import NAC_PROJ, REPO, TAGS_2023, cart_label, pds4_label, raster_bounds

# --------------------------------------------------------------------- C03 (P1.10 field)


def test_C03_preprocess_field():
    from lunar_reg.pipeline import PipelineConfig
    from lunar_reg.preprocess.presets import PRESET_NAMES

    fields = {f.name: f for f in dataclasses.fields(PipelineConfig)}
    assert "preprocess" in fields
    assert fields["preprocess"].default in PRESET_NAMES
    with pytest.raises(ValueError):
        PipelineConfig(preprocess="no_such_preset")


# --------------------------------------------------------------------- C08

C08_FILE_KEYS = {"path", "bytes", "sha256", "source", "url", "product_id", "instrument", "role",
                 "downloaded_utc", "recorded_by"}


def test_C08_roundtrip(tmp_path, monkeypatch):
    from lunar_reg.ingest.downloads import record_failure, record_file

    monkeypatch.chdir(tmp_path)
    (tmp_path / "data/raw/x").mkdir(parents=True)
    f = tmp_path / "data/raw/x/a.img"
    f.write_bytes(b"12345")
    man = tmp_path / "data/raw/DOWNLOADS.json"
    entry = record_file(f, source="LOCAL", product_id="a", instrument="DOC", role="data",
                        manifest=man)
    assert entry.path == "data/raw/x/a.img" and entry.bytes == 5
    record_file(f, source="LOCAL", product_id="a", instrument="DOC", role="data", manifest=man)
    record_failure("https://example.invalid/x", 503, "rejected", manifest=man)
    doc = json.loads(man.read_text())
    assert doc["schema"] == 1 and len(doc["files"]) == 1
    assert set(doc["files"][0]) == C08_FILE_KEYS
    assert doc["files"][0]["sha256"] == \
        "5994471abb01112afcc18159f6cc74b4f511b99806da59b3caf5a9c173cacfc5"
    assert doc["failures"][0]["http_status"] == 503


def test_C08_statuses(tmp_path, monkeypatch):
    from lunar_reg.ingest.downloads import DownloadStatus, record_failure, record_file, verify_downloads

    assert {m.value for m in DownloadStatus} == {
        "ok", "missing", "size_mismatch", "hash_mismatch", "unrecorded", "http_error"}
    assert DownloadStatus.UNRECORDED.is_suspicious and not DownloadStatus.UNRECORDED.is_failure
    monkeypatch.chdir(tmp_path)
    raw = tmp_path / "data/raw/ch2"
    raw.mkdir(parents=True)
    man = tmp_path / "data/raw/DOWNLOADS.json"
    files = {}
    for name in ("ok", "gone", "size", "hash"):
        files[name] = raw / f"{name}.img"
        files[name].write_bytes(b"abcdef")
        record_file(files[name], source="LOCAL", product_id=name, instrument="DOC", role="data",
                    manifest=man)
    files["gone"].unlink()
    files["size"].write_bytes(b"abc")
    files["hash"].write_bytes(b"abcdeX")
    (raw / "stray.img").write_bytes(b"x")
    record_failure("https://example.invalid/y", 503, "rejected", manifest=man)
    diag = verify_downloads(manifest=man, raw_root=tmp_path / "data/raw")
    assert diag.counts == {"ok": 1, "missing": 1, "size_mismatch": 1, "hash_mismatch": 1,
                           "unrecorded": 1, "http_error": 1}
    assert "missing" in diag.report()


# --------------------------------------------------------------------- C09


def test_C09_empty_root_all_absent(tmp_path):
    from lunar_reg.ingest.catalog import INSTRUMENTS, InstrumentStatus, build_catalog

    assert INSTRUMENTS == ("OHRC", "TMC2", "IIRS", "LRO_NAC", "LRO_NAC_DTM", "SELENE_TC")
    assert {m.value for m in InstrumentStatus} == {"present", "absent", "partial", "unreadable"}
    cat = build_catalog(tmp_path)
    assert set(cat.status) == set(INSTRUMENTS)
    assert all(s is InstrumentStatus.ABSENT for s in cat.status.values())
    assert "ABSENT" in cat.report().upper()


def _ohrc_tree(root, level="ncp", with_image=True):
    stem = f"ch2_ohr_{level}_20240425T1406019344_d_img_d18"
    d = root / "ch2/ohrc" / stem / "data/calibrated/20240425"
    d.mkdir(parents=True)
    (d / f"{stem}.xml").write_text(pds4_label(file_name=f"{stem}.img"))
    if with_image:
        (d / f"{stem}.img").write_bytes(np.zeros(120, np.uint8).tobytes())
    return d / f"{stem}.xml"


def test_C09_present_ohrc(tmp_path):
    from lunar_reg.ingest.catalog import InstrumentStatus, build_catalog

    _ohrc_tree(tmp_path)
    cat = build_catalog(tmp_path)
    assert cat.status["OHRC"] is InstrumentStatus.PRESENT
    entries = cat.products("OHRC")
    assert len(entries) == 1 and entries[0].level == "calibrated"
    assert entries[0].product_type == "data"


# --------------------------------------------------------------------- C10

C10_FIELDS = ["crs_proj4", "x0_m", "y0_m", "pixel_size_x_m", "pixel_size_y_m", "width", "height",
              "source", "note"]


def _nac_like_label(tmp_path, written_sign=+1):
    # 1/10-scale NAC raster (10 m pixels) whose true origin is the NAC's negative x.
    x0, y0, w, h, px = -11043.5, 638258.5, 2300, 4768, 10.0
    bounds = raster_bounds(x0, y0, w, h, px)
    path = tmp_path / "nac.xml"
    path.write_text(cart_label(written_sign * 11043.5, y0, w, h, px, bounds))
    return path


def test_C10_synthetic_label(tmp_path):
    from lunar_reg.ingest.lro import GeoReference, georeference_from_label
    from lunar_reg.provenance import ValueSource

    assert [f.name for f in dataclasses.fields(GeoReference)] == C10_FIELDS
    geo = georeference_from_label(_nac_like_label(tmp_path, +1))
    assert geo.x0_m == pytest.approx(-11043.5) and geo.y0_m == pytest.approx(638258.5)
    assert geo.pixel_size_x_m == pytest.approx(10.0) and (geo.width, geo.height) == (2300, 4768)
    assert geo.source is ValueSource.INFERRED
    assert "+proj=stere" in geo.crs_proj4 and "+lat_ts=-69.3" in geo.crs_proj4
    geo2 = georeference_from_label(_nac_like_label(tmp_path, -1))
    assert geo2.source is ValueSource.DOCUMENTED and geo2.x0_m == pytest.approx(-11043.5)


def test_C10_roundtrip(tmp_path):
    from lunar_reg.ingest.lro import GeoReference, georeference_from_label

    geo = georeference_from_label(_nac_like_label(tmp_path))
    cols, rows = np.array([0.0, 100.5, 2299.0]), np.array([0.0, 2000.25, 4767.0])
    lon, lat = geo.pixel_to_lonlat(cols, rows)
    c2, r2 = geo.lonlat_to_pixel(lon, lat)
    np.testing.assert_allclose(c2, cols, atol=1e-6)
    np.testing.assert_allclose(r2, rows, atol=1e-6)
    assert GeoReference.from_dict(json.loads(json.dumps(geo.as_dict()))) == geo
    a = geo.affine()
    assert (a.a, a.c, a.e, a.f) == pytest.approx((10.0, -11043.5, -10.0, 638258.5))


def test_C10_missing_pixel_scale(tmp_path):
    from lunar_reg.ingest.lro import LabelGeoreferenceError, georeference_from_label

    x0, y0, w, h, px = -11043.5, 638258.5, 230, 476, 100.0
    path = tmp_path / "bad.xml"
    path.write_text(cart_label(11043.5, y0, w, h, px, raster_bounds(x0, y0, w, h, px),
                               pixel_scale=False))
    with pytest.raises(LabelGeoreferenceError, match="pixel_scale_x"):
        georeference_from_label(path)


@pytest.mark.data
def test_C10_real_nac_sign():
    from lunar_reg.ingest.lro import georeference_from_label
    from lunar_reg.provenance import ValueSource

    label = REPO / "data/raw/reference/lro_nac_vikram/NAC_DTM_VIKRAMSITE1_M1442997156_100CM.xml"
    if not label.exists():
        pytest.skip(f"missing {label}")
    geo = georeference_from_label(label)
    assert geo.x0_m == pytest.approx(-11043.5, abs=0.01)
    assert geo.y0_m == pytest.approx(638258.5, abs=0.01)
    assert (geo.width, geo.height) == (23003, 47683)
    assert geo.source is ValueSource.INFERRED


# --------------------------------------------------------------------- C11


def test_C11_members():
    from lunar_reg.pairs import PrepOutcome, PrepStatus, PriorSource, WindowPair, prepare_window_pair

    assert {m.value for m in PriorSource} == {"geometry_grid", "label_corners", "bbox"}
    assert {m.value for m in PrepStatus} == {"ok", "label_unreadable", "no_footprint",
                                            "outside_reference", "empty_reference",
                                            "read_failed"}
    names = [f.name for f in dataclasses.fields(WindowPair)]
    for key in ("source", "reference", "source_valid", "reference_valid", "prior", "prior_source",
                "gsd_m", "source_window", "reference_window", "source_native_gsd_m",
                "reference_native_gsd_m", "source_to_native", "reference_to_native", "shift_m",
                "source_id", "reference_id", "provenance"):
        assert key in names, key
    assert [f.name for f in dataclasses.fields(PrepOutcome)] == ["status", "pair", "detail"]
    params = inspect.signature(prepare_window_pair).parameters
    for key in ("gsd_m", "window_m", "margin_m", "shift_m", "centre_line", "geometry_grid_path",
                "band_reduction"):
        assert key in params and params[key].kind is inspect.Parameter.KEYWORD_ONLY


def test_C11_unreadable_label(tmp_path):
    from lunar_reg.ingest.lro import GeoReference
    from lunar_reg.pairs import PrepStatus, prepare_window_pair
    from lunar_reg.provenance import ValueSource

    bad = tmp_path / "bad.xml"
    bad.write_text("<not xml")
    geo = GeoReference(NAC_PROJ, -11043.5, 638258.5, 1.0, 1.0, 100, 100, ValueSource.INFERRED)
    out = prepare_window_pair(bad, tmp_path / "ref.xml", geo, gsd_m=4.0, window_m=100.0,
                              margin_m=10.0)
    assert out.status is PrepStatus.LABEL_UNREADABLE and out.pair is None


# --------------------------------------------------------------------- C12


def test_C12_names_and_identity():
    from lunar_reg.preprocess.presets import PRESET_NAMES, PresetOutcome, apply_preset

    assert PRESET_NAMES == ("none", "ohrc_nac", "clahe_shadow")
    assert [f.name for f in dataclasses.fields(PresetOutcome)] == [
        "ok", "source", "reference", "detail", "history", "uses_placeholders"]
    img = np.random.default_rng(0).integers(1, 255, (64, 64)).astype(np.uint8)
    out = apply_preset("none", img, img.copy())
    assert out.ok and np.array_equal(out.source, img)
    with pytest.raises(ValueError):
        apply_preset("nope", img, img)


@pytest.mark.parametrize("name", ["ohrc_nac", "clahe_shadow"])
def test_C12_nodata_preserved(name):
    from lunar_reg.preprocess.presets import apply_preset

    img = np.random.default_rng(1).integers(1, 255, (96, 96)).astype(np.uint8)
    img[:, :10] = 0
    out = apply_preset(name, img, img.copy(), nodata=0)
    assert out.ok, out.detail
    assert out.source.dtype == np.uint8 and out.source.shape == img.shape
    assert (out.source[:, :10] == 0).all() and (out.source[:, 12:] > 0).mean() > 0.99


# --------------------------------------------------------------------- C13


def test_C13_synthetic_azimuth_recovered():
    from lunar_reg.eval.scenes import add_craters, fractal_terrain
    from lunar_reg.ingest.sun import AzimuthFit, fit_sun_azimuth, lambert_shade

    dtm = add_craters(fractal_terrain((256, 256), seed=2), seed=2).astype(np.float64) * 30.0
    image = lambert_shade(dtm, 3.0, 137.0, 16.0)
    image = image + np.random.default_rng(0).normal(0, 0.01, image.shape)
    fit = fit_sun_azimuth(dtm, 3.0, image, 16.0)
    assert isinstance(fit, AzimuthFit)
    d = abs((fit.azimuth_deg - 137.0 + 180) % 360 - 180)
    assert d <= 2.0, fit.azimuth_deg
    assert fit.peak_margin > 0 and fit.n_valid_px > 0
    assert len(fit.azimuths) == len(fit.ncc) == 360


def test_C13_ode_elevation(tmp_path):
    from lunar_reg.ingest.sun import SunGeometry, sun_from_ode_metadata
    from lunar_reg.provenance import ValueSource

    doc = {"ODEResults": {"Status": "Success", "Products": {"Product": [
        {"Product_name": "M1442997156LE.IMG", "Incidence_angle": "73.84"},
        {"Product_name": "M1443025251LE.IMG", "Incidence_angle": "74.65"}]}}}
    path = tmp_path / "ode.json"
    path.write_text(json.dumps(doc))
    sun = sun_from_ode_metadata(path, "M1442997156LE")
    assert isinstance(sun, SunGeometry)
    assert sun.elevation_deg == pytest.approx(90 - 73.84)
    assert sun.elevation_source is ValueSource.DOCUMENTED
    assert sun.azimuth_deg is None and sun.azimuth_source is ValueSource.UNKNOWN
    assert sun.as_tuple() is None
    doc["ODEResults"]["Products"]["Product"] = doc["ODEResults"]["Products"]["Product"][1]
    path.write_text(json.dumps(doc))
    assert sun_from_ode_metadata(path, "M1443025251LE").elevation_deg == pytest.approx(90 - 74.65)
    assert sun_from_ode_metadata(path, "M1").elevation_source in (
        ValueSource.UNKNOWN, ValueSource.DOCUMENTED)


# --------------------------------------------------------------------- C14


def _shift(dx, dy):
    return np.array([[1.0, 0, dx], [0, 1.0, dy], [0, 0, 1.0]])


def test_C14_identical():
    from lunar_reg.eval.agreement import AgreementResult, cross_matcher_agreement

    a = cross_matcher_agreement({"sift": _shift(5, 3), "akaze": _shift(5, 3)}, (100, 200))
    assert isinstance(a, AgreementResult)
    assert a.max_disagreement_px == pytest.approx(0.0) and a.passes and a.n_matchers == 2
    assert set(a.pairwise_px) == {"akaze|sift"}


def test_C14_known_offset():
    from lunar_reg.eval.agreement import cross_matcher_agreement

    ok = cross_matcher_agreement({"a": _shift(0, 0), "b": _shift(0.6, 0)}, (100, 100), gsd_m=4.0)
    assert ok.max_disagreement_px == pytest.approx(0.6) and ok.passes
    assert ok.max_disagreement_m == pytest.approx(2.4)
    bad = cross_matcher_agreement({"a": _shift(0, 0), "b": _shift(1.5, 0)}, (100, 100))
    assert not bad.passes
    one = cross_matcher_agreement({"a": _shift(0, 0)}, (100, 100))
    assert np.isnan(one.max_disagreement_px) and not one.passes
    aff = cross_matcher_agreement({"h": _shift(2, 1), "a": _shift(2, 1)[:2]}, (50, 50))
    assert aff.max_disagreement_px == pytest.approx(0.0)


# --------------------------------------------------------------------- C20

C20_KEYS = {"schema", "decision", "rule", "strips", "n_strips_passing", "reference_sun",
            "run_record", "created_utc"}
C20_STRIP_KEYS = {"tag", "best_matcher", "status", "n_inliers", "u_score", "agreement_px",
                  "passes_targets"}


def validate_c20(doc: dict) -> None:
    assert set(doc) == C20_KEYS
    assert doc["schema"] == 1 and doc["decision"] in ("BUILD_1B", "SKIP_1B")
    assert sorted(s["tag"] for s in doc["strips"]) == sorted(TAGS_2023)
    for s in doc["strips"]:
        assert set(s) == C20_STRIP_KEYS
    passing = sum(bool(s["passes_targets"]) for s in doc["strips"])
    assert doc["n_strips_passing"] == passing
    assert (doc["decision"] == "SKIP_1B") == (passing == len(TAGS_2023))


@pytest.mark.data
def test_C20_schema():
    path = REPO / "data/processed/vikram/exp1_gate.json"
    if not path.exists():
        pytest.skip("exp1_gate.json not produced yet (P1.20)")
    validate_c20(json.loads(path.read_text()))
