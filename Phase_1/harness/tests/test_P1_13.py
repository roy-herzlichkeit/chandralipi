"""P1.13 — window-pair preparation, synthetic end to end (Phase_1/LLD/pairs.md). Protected (G05)."""

from __future__ import annotations

import numpy as np
import pytest
from _h1 import MOON_GEO, NAC_PROJ, pds4_label

X0, Y0, PSX = -2000.0, 615000.0, 0.5          # reference: 600 x 600 px at 0.5 m
LINES, SAMPLES = 400, 300                     # source: OHRC-like 0.25 m, maps to ref px (100 + s/2, 100 + l/2)
GEOMETRY_KEYS = {"ref_crop_c0", "ref_crop_r0", "ref_factor", "shift_e_m", "shift_s_m", "src_win_l0",
                 "src_win_s0", "src_win_lines", "src_win_samples", "gsd_m", "crop_geometry_source",
                 "prior_source"}


def _lonlat(c, r):
    from rasterio.warp import transform

    lon, lat = transform(NAC_PROJ, MOON_GEO, [X0 + c * PSX], [Y0 - r * PSX])
    return lat[0], lon[0]


@pytest.fixture
def scene(tmp_path):
    import cv2
    import rasterio
    from rasterio.transform import from_origin

    from lunar_reg.ingest.lro import GeoReference
    from lunar_reg.provenance import ValueSource

    rng = np.random.default_rng(5)
    g = cv2.GaussianBlur(rng.normal(0, 1, (600, 600)).astype(np.float32), (0, 0), 2.0)
    ref = (1 + (g - g.min()) / (g.max() - g.min()) * 250).astype(np.uint8)
    ref_path = tmp_path / "ref.tif"
    # the GeoTIFF's own transform is deliberately wrong (as GDAL's is for the NAC): only pixels are read
    with rasterio.open(ref_path, "w", driver="GTiff", width=600, height=600, count=1, dtype="uint8",
                       transform=from_origin(0, 0, 1, 1)) as ds:
        ds.write(ref, 1)
    geo = GeoReference(NAC_PROJ, X0, Y0, PSX, PSX, 600, 600, ValueSource.INFERRED)
    src = cv2.resize(ref[100:300, 100:250], (SAMPLES, LINES), interpolation=cv2.INTER_LINEAR)
    stem = "ch2_ohr_nrp_20240425T1406019344_d_img_d18"
    d = tmp_path / stem
    d.mkdir()
    corners = {"upper_left": _lonlat(100, 100), "upper_right": _lonlat(250, 100),
               "lower_left": _lonlat(100, 300), "lower_right": _lonlat(250, 300)}
    geometry = {}
    for k, (lat, lon) in corners.items():
        geometry[f"{k}_latitude"], geometry[f"{k}_longitude"] = lat, lon
    (d / f"{stem}.xml").write_text(pds4_label(lid=f"urn:isro:isda:ch2_ohr:{stem}",
                                              file_name=f"{stem}.img",
                                              axes=(("Line", LINES), ("Sample", SAMPLES)),
                                              geometry=geometry))
    (d / f"{stem}.img").write_bytes(src.tobytes())
    return d / f"{stem}.xml", ref_path, geo


def test_prepare_ok(scene):
    from lunar_reg.pairs import PrepStatus, PriorSource, prepare_window_pair

    label, ref_path, geo = scene
    out = prepare_window_pair(label, ref_path, geo, gsd_m=1.0, window_m=50.0, margin_m=10.0)
    assert out.status is PrepStatus.OK, out.detail
    pair = out.pair
    assert pair.prior_source is PriorSource.LABEL_CORNERS
    assert pair.source.shape == (50, 50) and pair.source.dtype == np.uint8
    assert pair.source_window == (100, 50, 200, 200)
    c = pair.prior @ np.array([25.0, 25.0, 1.0])
    assert c[:2] / c[2] == pytest.approx((35.0, 35.0), abs=1.0)
    extra = pair.geometry_extra()
    assert set(extra) == GEOMETRY_KEYS and extra["crop_geometry_source"] == "recorded"
    assert extra["ref_factor"] == pytest.approx(2.0)
    assert pair.provenance["reference_georef"] == "inferred"
    # pixel-centre convention (CONTRACTS C11): f = 200 / 50 = 4 -> (s0 + 1.5, l0 + 1.5)
    n = pair.source_to_native @ np.array([0.0, 0.0, 1.0])
    assert tuple(n[:2]) == pytest.approx((51.5, 101.5))


def test_shift_moves_crop(scene):
    from lunar_reg.pairs import prepare_window_pair

    label, ref_path, geo = scene
    a = prepare_window_pair(label, ref_path, geo, gsd_m=1.0, window_m=50.0, margin_m=10.0).pair
    b = prepare_window_pair(label, ref_path, geo, gsd_m=1.0, window_m=50.0, margin_m=10.0,
                            shift_m=(20.0, 0.0)).pair
    assert b.geometry_extra()["ref_crop_c0"] - a.geometry_extra()["ref_crop_c0"] == \
        pytest.approx(40, abs=1)
    assert b.shift_m == (20.0, 0.0) and b.provenance["shift_m"] == "inferred"


def test_outside_reference(scene):
    from lunar_reg.pairs import PrepStatus, prepare_window_pair

    label, ref_path, geo = scene
    out = prepare_window_pair(label, ref_path, geo, gsd_m=1.0, window_m=50.0, margin_m=10.0,
                              shift_m=(20000.0, 0.0))
    assert out.status is PrepStatus.OUTSIDE_REFERENCE and out.pair is None


def test_no_footprint(tmp_path, scene):
    from lunar_reg.pairs import PrepStatus, prepare_window_pair

    _, ref_path, geo = scene
    label = tmp_path / "ch2_ohr_nrp_x_d_img_d18.xml"
    label.write_text(pds4_label(lid="urn:isro:isda:ch2_ohr:x", file_name="x.img",
                                axes=(("Line", LINES), ("Sample", SAMPLES))))
    (tmp_path / "x.img").write_bytes(np.ones(LINES * SAMPLES, np.uint8).tobytes())
    out = prepare_window_pair(label, ref_path, geo, gsd_m=1.0, window_m=50.0, margin_m=10.0)
    assert out.status is PrepStatus.NO_FOOTPRINT
