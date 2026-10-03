"""Georeferenced blockwise warp and mask-based validity (Phase_2/LLD/native.md §P2.09)."""

from __future__ import annotations

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")

from rasterio.transform import from_origin  # noqa: E402

from lunar_reg.align.estimate import Transform  # noqa: E402
from lunar_reg.align.warp import save_registered_geotiff, warp_blockwise  # noqa: E402

SRC_CRS = "+proj=eqc +R=1737400 +units=m +no_defs"
DST_CRS = "+proj=stere +lat_0=-90 +lat_ts=-69.3 +lon_0=32.3 +R=1737400 +units=m +no_defs"


def _write_src(path, data, *, nodata=None, transform=None):
    h, w = data.shape
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=w,
        height=h,
        count=1,
        dtype=data.dtype.name,
        crs=SRC_CRS,
        transform=transform or from_origin(100.0, 200.0, 1.0, 1.0),
        nodata=nodata,
    ) as ds:
        ds.write(data, 1)


def _textured(h, w, seed=0):
    return np.random.default_rng(seed).integers(1, 255, (h, w), dtype=np.uint8)


def test_output_georef_is_the_requested_one_not_the_source(tmp_path):
    src_path = tmp_path / "src.tif"
    _write_src(src_path, _textured(90, 120), nodata=7)
    dst_t = from_origin(-11043.5, 638258.5, 4.0, 4.0)
    out = tmp_path / "out.tif"
    with rasterio.open(src_path) as src:
        warp_blockwise(
            src,
            Transform(np.eye(3), "homography", 0, 0),
            out,
            (80, 100),
            dst_transform=dst_t,
            dst_crs=DST_CRS,
            nodata=0,
            block_px=32,
        )
        src_transform, src_crs = src.transform, src.crs
    with rasterio.open(out) as ds:
        assert ds.transform == dst_t
        assert ds.transform != src_transform
        assert "stere" in ds.crs.to_proj4()
        assert ds.crs != src_crs
        assert ds.nodata == 0
        assert ds.dtypes[0] == "uint8"
        assert (ds.height, ds.width) == (80, 100)


def test_identity_warp_reproduces_source_inside_valid_mask(tmp_path):
    data = _textured(70, 90, seed=1)
    data[20:30, 40:50] = 0  # source nodata cells
    src_path = tmp_path / "src.tif"
    _write_src(src_path, data, nodata=0)
    out = tmp_path / "id.tif"
    with rasterio.open(src_path) as src:
        # Output grid larger than the source: the extra rows/cols have no support.
        warp_blockwise(
            src,
            np.eye(3),
            out,
            (100, 128),
            dst_transform=from_origin(500.0, 900.0, 1.0, 1.0),
            dst_crs=DST_CRS,
            nodata=0,
            block_px=48,
        )
    with rasterio.open(out) as ds:
        got = ds.read(1)
    valid = data != 0
    np.testing.assert_array_equal(got[:70, :90][valid], data[valid])
    assert np.all(got[:70, :90][~valid] == 0)
    assert np.all(got[70:, :] == 0) and np.all(got[:, 90:] == 0)


def test_unsupported_and_masked_pixels_get_the_requested_nodata(tmp_path):
    data = np.full((40, 40), 5.0, dtype=np.float32)
    src_path = tmp_path / "src.tif"
    _write_src(src_path, data)  # no source nodata: the whole source is valid
    out = tmp_path / "shift.tif"
    shift = np.array([[1.0, 0.0, 10.0], [0.0, 1.0, 0.0]])  # 2x3 affine
    with rasterio.open(src_path) as src:
        warp_blockwise(
            src,
            shift,
            out,
            (40, 100),
            dst_transform=from_origin(500.0, 900.0, 1.0, 1.0),
            dst_crs=DST_CRS,
            nodata=-9999.0,
            block_px=16,
        )
    with rasterio.open(out) as ds:
        got = ds.read(1)
        assert ds.nodata == -9999.0
    np.testing.assert_allclose(got[:, 12:48], 5.0)
    assert np.all(got[:, :9] == -9999.0)
    assert np.all(got[:, 51:] == -9999.0)  # includes whole blocks with no support


def test_real_zeros_count_as_valid(tmp_path):
    src = np.full((100, 100), 50, dtype=np.uint8)
    src[40:60, 40:60] = 0  # real zeros inside the valid area
    out = save_registered_geotiff(
        src,
        np.eye(3),
        (100, 100),
        tmp_path / "r.tif",
        crs=SRC_CRS,
        origin_xy=(500.0, 900.0),
        pixel_size=1.0,
        preview_png=False,
    )
    assert out["valid_fraction"] == 1.0
    with rasterio.open(out["path"]) as ds:
        data = ds.read(1)
        mask = ds.dataset_mask()
        assert ds.nodata == 0
    old_rule = float((data > 0).mean())
    assert old_rule < 1.0  # the pre-P2.09 `warped > 0` rule undercounted
    assert np.all(mask == 255)  # the written mask, not nodata, defines validity
    assert not (tmp_path / "r.tif.msk").exists()


def test_mask_marks_pixels_without_source_support(tmp_path):
    src = np.full((50, 60), 9, dtype=np.uint8)
    matrix = np.array([[1.0, 0, 10], [0, 1.0, 5], [0, 0, 1]])
    out = save_registered_geotiff(
        src,
        matrix,
        (80, 100),
        tmp_path / "m.tif",
        crs=SRC_CRS,
        origin_xy=(500.0, 900.0),
        pixel_size=1.0,
        preview_png=False,
    )
    assert out["valid_fraction"] == pytest.approx(50 * 60 / (80 * 100))
    with rasterio.open(out["path"]) as ds:
        mask = ds.dataset_mask()
        data = ds.read(1)
    assert np.all(mask[5:55, 10:70] == 255)
    assert mask[:5].max() == 0 and mask[:, :10].max() == 0
    assert np.all(data[mask == 0] == 0)


def _blockwise(src_path, out, matrix, shape, *, nodata, block_px=32):
    with rasterio.open(src_path) as src:
        warp_blockwise(
            src,
            matrix,
            out,
            shape,
            dst_transform=from_origin(500.0, 900.0, 1.0, 1.0),
            dst_crs=DST_CRS,
            nodata=nodata,
            block_px=block_px,
        )
    with rasterio.open(out) as ds:
        return ds.read(1), ds.dataset_mask()


def test_source_nodata_differs_from_output_nodata(tmp_path):
    # Source nodata 7 on a block of 7s, output nodata 0: the source-nodata rule
    # (valid = != src nodata) must turn those pixels into the output nodata.
    data = _textured(60, 80, seed=3)
    data[data == 7] = 8  # 7 appears only where it means nodata
    data[15:30, 25:45] = 7
    src_path = tmp_path / "src7.tif"
    _write_src(src_path, data, nodata=7)
    got, mask = _blockwise(src_path, tmp_path / "o.tif", np.eye(3), (60, 80), nodata=0)
    hole = np.zeros(data.shape, dtype=bool)
    hole[15:30, 25:45] = True
    assert np.all(got[hole] == 0)
    assert np.all(mask[hole] == 0)
    assert not np.any(got[~hole] == 7)
    np.testing.assert_array_equal(got[~hole], data[~hole])  # neighbours keep their values
    assert np.all(mask[~hole] == 255)


@pytest.mark.parametrize("src_nodata", [np.nan, -9999.0])
def test_float_source_gap_does_not_bleed_into_valid_pixels(tmp_path, src_nodata):
    data = np.full((40, 40), 5.0, dtype=np.float32)
    data[18:22, 18:22] = src_nodata
    src_path = tmp_path / "srcf.tif"
    _write_src(src_path, data, nodata=src_nodata)
    shift = np.array([[1.0, 0.0, 0.3], [0.0, 1.0, 0.3]])  # sub-pixel: cubic touches the gap
    got, mask = _blockwise(src_path, tmp_path / "f.tif", shift, (40, 40), nodata=-1234.0)
    valid = mask == 255
    assert np.isfinite(got).all()
    np.testing.assert_allclose(got[valid], 5.0, atol=1e-4)
    assert np.all(got[~valid] == -1234.0)
    assert np.count_nonzero(~valid[10:30, 10:30]) == 16  # the 4x4 gap, nearest-warped


def test_valid_pixels_equal_to_nodata_stay_valid_in_the_dataset_mask(tmp_path):
    # No source nodata: real zeros and cubic undershoot (dark next to bright)
    # are valid output pixels whose value equals the output nodata 0.
    data = np.full((64, 64), 200, dtype=np.uint8)
    data[:, ::4] = 3
    data[30:34, 30:34] = 0
    src_path = tmp_path / "srcz.tif"
    _write_src(src_path, data)
    shift = np.array([[1.0, 0.0, 0.5], [0.0, 1.0, 0.0]])
    got, mask = _blockwise(src_path, tmp_path / "z.tif", shift, (64, 80), nodata=0, block_px=48)
    footprint = np.zeros(got.shape, dtype=bool)
    footprint[:, 1:64] = True  # columns whose nearest source pixel exists
    assert np.any(got[footprint] == 0)  # zeros inside the footprint exist ...
    assert np.all(mask[footprint] == 255)  # ... and the dataset mask keeps them valid
    assert np.all(mask[:, 66:] == 0) and np.all(got[:, 66:] == 0)
    assert not (tmp_path / "z.tif.msk").exists()


def test_save_registered_geotiff_uses_caller_source_validity(tmp_path):
    src = np.full((100, 100), 80, dtype=np.uint8)
    src[:, :50] = 0  # 0 = nodata (pairs.py convention), declared via source_valid
    src[60:70, 70:80] = 0  # a real zero inside the valid half
    valid = np.ones(src.shape, dtype=bool)
    valid[:, :50] = False
    out = save_registered_geotiff(
        src,
        np.eye(3),
        (100, 100),
        tmp_path / "v.tif",
        crs=SRC_CRS,
        origin_xy=(500.0, 900.0),
        pixel_size=1.0,
        preview_png=False,
        source_valid=valid,
    )
    assert out["valid_fraction"] == 0.5
    with rasterio.open(out["path"]) as ds:
        mask = ds.dataset_mask()
        data = ds.read(1)
    assert np.all(mask[:, :50] == 0) and np.all(mask[:, 50:] == 255)
    assert np.all(data[60:70, 70:80] == 0)  # real zero kept, and valid by the mask
    with pytest.raises(ValueError, match="source_valid shape"):
        save_registered_geotiff(
            src,
            np.eye(3),
            (100, 100),
            tmp_path / "bad.tif",
            crs=SRC_CRS,
            origin_xy=(500.0, 900.0),
            pixel_size=1.0,
            preview_png=False,
            source_valid=valid[:50],
        )
