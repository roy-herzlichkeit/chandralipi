"""Tiling is what keeps OHRC inside the memory budget, so its edges matter."""

from __future__ import annotations

import numpy as np
import pytest

from lunar_reg.ingest.tiling import Tile, estimate_full_load_bytes, plan_tiles


def test_tiles_cover_the_full_raster():
    tiles = plan_tiles(2000, 3000, tile_px=512, overlap=0.25)
    covered = np.zeros((2000, 3000), dtype=bool)
    for t in tiles:
        r0, c0, r1, c1 = t.bounds_px
        covered[r0:r1, c0:c1] = True
    assert covered.all(), "tiling left uncovered pixels"


def test_tiles_stay_in_bounds():
    for t in plan_tiles(1000, 700, tile_px=256, overlap=0.3):
        r0, c0, r1, c1 = t.bounds_px
        assert 0 <= r0 < r1 <= 1000
        assert 0 <= c0 < c1 <= 700


def test_raster_smaller_than_tile_yields_one_clipped_tile():
    tiles = plan_tiles(100, 80, tile_px=512)
    assert len(tiles) == 1
    assert (tiles[0].height, tiles[0].width) == (100, 80)


def test_overlap_increases_tile_count():
    assert len(plan_tiles(2000, 2000, 512, overlap=0.5)) > len(
        plan_tiles(2000, 2000, 512, overlap=0.0)
    )


@pytest.mark.parametrize("overlap", [-0.1, 1.0, 1.5])
def test_invalid_overlap_rejected(overlap):
    with pytest.raises(ValueError):
        plan_tiles(1000, 1000, 256, overlap=overlap)


def test_to_parent_shifts_by_tile_offset():
    tile = Tile(row_off=300, col_off=150, height=256, width=256)
    local = np.array([[0.0, 0.0], [10.5, 20.25]])
    np.testing.assert_allclose(tile.to_parent(local), [[150.0, 300.0], [160.5, 320.25]])


def test_to_parent_preserves_subpixel_precision():
    """Sub-pixel accuracy is the headline requirement; lifting must not round."""
    tile = Tile(row_off=7, col_off=13, height=64, width=64)
    out = tile.to_parent(np.array([[0.333333, 0.666666]]))
    assert out[0, 0] == pytest.approx(13.333333, abs=1e-9)
    assert out[0, 1] == pytest.approx(7.666666, abs=1e-9)


def test_full_ohrc_pair_does_not_fit_in_vram():
    """Regression guard on the premise this whole module rests on.

    One strip is ~4.3 GB in float32, which would fit alone. Registration needs
    the source and reference resident together, and that pair is what exceeds
    the 8 GB budget -- before any model weights or activations.
    """
    strip = estimate_full_load_bytes(90_000, 12_000, bands=1, dtype_size=4)
    assert strip == pytest.approx(4.32e9, rel=0.01)
    assert 2 * strip > 8 * 1024**3


def test_iirs_cube_is_large_even_at_modest_spatial_size():
    """The other memory trap: 256 bands multiplies a small raster into GBs."""
    cube = estimate_full_load_bytes(2000, 2000, bands=256, dtype_size=4)
    assert cube == pytest.approx(4.10e9, rel=0.01)  # ~3.8 GiB
    assert cube > 3 * 1024**3
