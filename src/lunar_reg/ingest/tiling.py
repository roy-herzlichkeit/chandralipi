"""Tiling large products into matcher-sized work units.

VRAM CONSTRAINT -- this module exists because of it.

A single OHRC strip is on the order of 12,000 samples by 90,000 lines: ~2.2 GB
on disk at 16-bit, ~4.3 GB once promoted to float32. Registration needs *two*
of those resident simultaneously, plus model weights and activations, so the
pair alone is ~8.6 GB before a matcher has allocated anything -- past the 8 GB
card, and uncomfortable in host RAM on a 16 GB laptop.

So nothing in this pipeline ever loads a full product. Work is planned as
overlapping tiles sized by :func:`lunar_reg.device.plan_dense_tile`, and each
tile is pulled from disk with a rasterio windowed read at the moment it is
needed.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)

#: Fraction of tile side shared with each neighbour. Features near a tile edge
#: have a truncated descriptor support region, so without overlap the match
#: field develops periodic gaps on the seams -- which is exactly the clustering
#: artefact the uniform-distribution requirement penalises.
DEFAULT_OVERLAP: float = 0.25


@dataclass(frozen=True)
class Tile:
    """A rectangular read window in pixel coordinates of its parent product."""

    row_off: int
    col_off: int
    height: int
    width: int
    index: tuple[int, int] = (0, 0)

    @property
    def window(self):
        """As a :class:`rasterio.windows.Window` for windowed reads."""
        from rasterio.windows import Window

        return Window(self.col_off, self.row_off, self.width, self.height)

    @property
    def bounds_px(self) -> tuple[int, int, int, int]:
        """``(row_start, col_start, row_stop, col_stop)``."""
        return (self.row_off, self.col_off, self.row_off + self.height, self.col_off + self.width)

    def to_parent(self, xy: np.ndarray) -> np.ndarray:
        """Lift tile-local ``(x, y)`` coordinates back into parent pixel space.

        Every matcher works in tile-local coordinates; correspondences are
        useless until they are expressed in one common frame, so call this
        before any transform estimation.
        """
        xy = np.asarray(xy, dtype=np.float64)
        return xy + np.array([self.col_off, self.row_off], dtype=np.float64)


def plan_tiles(
    height: int,
    width: int,
    tile_px: int,
    overlap: float = DEFAULT_OVERLAP,
) -> list[Tile]:
    """Cover an ``height x width`` raster with overlapping square tiles.

    Edge tiles are shifted inward to keep a full-size window rather than being
    truncated, so every tile presents the matcher with the same input shape.
    A raster smaller than one tile yields a single clipped tile.
    """
    if not 0.0 <= overlap < 1.0:
        raise ValueError(f"overlap must be in [0, 1), got {overlap}")
    if tile_px <= 0:
        raise ValueError(f"tile_px must be positive, got {tile_px}")

    stride = max(1, int(round(tile_px * (1.0 - overlap))))
    tiles: list[Tile] = []

    def _starts(extent: int) -> list[int]:
        if extent <= tile_px:
            return [0]
        starts = list(range(0, extent - tile_px + 1, stride))
        if starts[-1] != extent - tile_px:
            starts.append(extent - tile_px)
        return starts

    for ti, row in enumerate(_starts(height)):
        for tj, col in enumerate(_starts(width)):
            tiles.append(
                Tile(
                    row_off=row,
                    col_off=col,
                    height=min(tile_px, height),
                    width=min(tile_px, width),
                    index=(ti, tj),
                )
            )
    logger.info(
        "planned %d tiles of %dpx (stride %d) over %dx%d raster",
        len(tiles),
        tile_px,
        stride,
        height,
        width,
    )
    return tiles


def iter_tiles(dataset, tiles: list[Tile], band: int = 1) -> Iterator[tuple[Tile, np.ndarray]]:
    """Yield ``(tile, array)`` pairs, reading one window at a time.

    ``dataset`` is an open rasterio dataset. Memory stays flat across the whole
    strip because only one tile is resident at any moment -- do not collect the
    arrays into a list.
    """
    for tile in tiles:
        yield tile, dataset.read(band, window=tile.window)


def estimate_full_load_bytes(height: int, width: int, bands: int = 1, dtype_size: int = 4) -> int:
    """Bytes a naive full-product load would take, for the "don't do that" log line."""
    return height * width * bands * dtype_size
