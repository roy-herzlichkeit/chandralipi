"""P2.09 — georeferenced warp (Phase_2/LLD/native.md §P2.09). Protected (G05)."""

from __future__ import annotations

import numpy as np
from rasterio.transform import from_origin


def test_warp_blockwise_uses_dst_georef(tmp_path):
    import rasterio

    from lunar_reg.align.warp import warp_blockwise

    src_path = tmp_path / "src.tif"
    data = (np.arange(200 * 300) % 250 + 1).astype(np.uint8).reshape(200, 300)
    with rasterio.open(src_path, "w", driver="GTiff", width=300, height=200, count=1,
                       dtype="uint8", crs="+proj=eqc +R=1737400 +units=m +no_defs",
                       transform=from_origin(0, 0, 1, 1)) as ds:
        ds.write(data, 1)
    dst_t = from_origin(5000.0, 9000.0, 2.0, 2.0)
    dst_crs = "+proj=stere +lat_0=-90 +lat_ts=-69.3 +lon_0=32.3 +R=1737400 +units=m +no_defs"
    out = tmp_path / "out.tif"
    with rasterio.open(src_path) as src:
        warp_blockwise(src, np.eye(3), out, (200, 300), dst_transform=dst_t, dst_crs=dst_crs,
                       block_px=64)
    with rasterio.open(out) as w:
        assert w.transform == dst_t
        assert "stere" in w.crs.to_proj4()
        got = w.read(1)
    np.testing.assert_array_equal(got[10:190, 10:290], data[10:190, 10:290])


def test_valid_fraction_mask_based(tmp_path):
    from lunar_reg.align.warp import save_registered_geotiff

    src = np.ones((100, 100), np.uint8) * 50
    src[40:60, 40:60] = 0          # real zeros inside the valid area
    out = save_registered_geotiff(src, np.eye(3), (100, 100), tmp_path / "r.tif",
                                  crs="+proj=eqc +R=1737400 +units=m +no_defs",
                                  origin_xy=(0.0, 0.0), pixel_size=1.0, preview_png=False)
    assert out["valid_fraction"] > 0.99
