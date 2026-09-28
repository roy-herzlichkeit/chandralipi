"""Writing a registered product as a georeferenced GeoTIFF."""

from __future__ import annotations

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")

from lunar_reg.align.warp import save_registered_geotiff  # noqa: E402

CRS = "+proj=stere +lat_0=-90 +lat_ts=-69.3 +lon_0=32.3 +R=1737400 +units=m"


def _textured(h=64, w=80):
    rng = np.random.default_rng(3)
    return rng.integers(1, 255, (h, w), dtype=np.uint8)


def test_translation_lands_where_the_matrix_says(tmp_path):
    src = _textured()
    matrix = np.array([[1.0, 0, 10], [0, 1.0, 5], [0, 0, 1]])
    out = save_registered_geotiff(src, matrix, (100, 120), tmp_path / "reg.tif",
                                  crs=CRS, origin_xy=(-500.0, 600.0), pixel_size=4.0)
    with rasterio.open(out["path"]) as ds:
        data = ds.read(1)
    # Interior pixels copy exactly under a pure integer translation.
    assert np.array_equal(data[5 + 2:5 + 62, 10 + 2:10 + 78], src[2:62, 2:78])
    assert data[:5].max() == 0 and data[:, :10].max() == 0


def test_georeference_and_nodata_are_written(tmp_path):
    out = save_registered_geotiff(_textured(), np.eye(3), (70, 90), tmp_path / "g.tif",
                                  crs=CRS, origin_xy=(-11043.5, 638258.5), pixel_size=4.0)
    with rasterio.open(out["path"]) as ds:
        assert ds.crs is not None
        assert ds.transform.a == pytest.approx(4.0) and ds.transform.e == pytest.approx(-4.0)
        assert ds.transform.c == pytest.approx(-11043.5)
        assert ds.transform.f == pytest.approx(638258.5)
        assert ds.nodata == 0
    assert (tmp_path / "g.png").exists()
    assert out["shape"] == (70, 90)
    assert 0 < out["valid_fraction"] < 1


def test_provenance_tags_travel_with_the_file(tmp_path):
    out = save_registered_geotiff(_textured(), np.eye(3), (64, 80), tmp_path / "t.tif",
                                  crs=CRS, origin_xy=(0.0, 0.0), pixel_size=1.0,
                                  tags={"pair_id": "a-b_sift", "min_inliers": 5},
                                  preview_png=False)
    with rasterio.open(out["path"]) as ds:
        tags = ds.tags()
    assert tags["pair_id"] == "a-b_sift" and tags["min_inliers"] == "5"
    assert not (tmp_path / "t.png").exists()


def test_affine_2x3_matrix_is_accepted(tmp_path):
    matrix = np.array([[1.0, 0, 3], [0, 1.0, 4]])
    out = save_registered_geotiff(_textured(), matrix, (80, 100), tmp_path / "a.tif",
                                  crs=CRS, origin_xy=(0.0, 0.0), pixel_size=1.0,
                                  preview_png=False)
    assert out["valid_fraction"] > 0
