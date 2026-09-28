"""Applying a transform to produce the registered product.

MEMORY CONSTRAINT: the deliverable is a *registered product*, and for OHRC that
product is far too large to warp in one call. ``cv2.warpPerspective`` on a
12000x90000 strip would need ~4 GB for the output alone plus a full-resolution
input, and it has no windowed mode.

:func:`warp_blockwise` therefore warps into an output raster one block at a
time, reading only the source region each block actually needs, so peak memory
is set by block size rather than by product size.
"""

from __future__ import annotations

import logging

import numpy as np

from lunar_reg.align.estimate import Transform

logger = logging.getLogger(__name__)

#: Output block edge in pixels. 2048^2 float32 is ~16 MB per block.
DEFAULT_BLOCK_PX = 2048


def warp_array(
    image: np.ndarray, transform: Transform, output_shape: tuple[int, int]
) -> np.ndarray:
    """Warp an in-memory array. Use only when the whole raster comfortably fits."""
    import cv2

    h, w = output_shape
    matrix = transform.matrix
    if matrix.shape == (3, 3):
        return cv2.warpPerspective(image, matrix, (w, h), flags=cv2.INTER_CUBIC)
    return cv2.warpAffine(image, matrix, (w, h), flags=cv2.INTER_CUBIC)


def _inverse(matrix: np.ndarray) -> np.ndarray:
    if matrix.shape == (3, 3):
        return np.linalg.inv(matrix)
    full = np.vstack([matrix, [0.0, 0.0, 1.0]])
    return np.linalg.inv(full)


def _source_bounds(inv: np.ndarray, row: int, col: int, h: int, w: int, margin: int = 8):
    """Bounding box in source pixels that an output block can draw from."""
    corners = np.array(
        [[col, row], [col + w, row], [col, row + h], [col + w, row + h]], dtype=np.float64
    )
    homogeneous = np.hstack([corners, np.ones((4, 1))])
    mapped = homogeneous @ inv.T
    mapped = mapped[:, :2] / mapped[:, 2:3]
    lo = np.floor(mapped.min(axis=0)).astype(int) - margin
    hi = np.ceil(mapped.max(axis=0)).astype(int) + margin
    return lo, hi


def warp_blockwise(
    src_dataset,
    transform: Transform,
    output_path,
    output_shape: tuple[int, int],
    block_px: int = DEFAULT_BLOCK_PX,
    profile_overrides: dict | None = None,
) -> None:
    """Warp an open rasterio dataset into a new file, block by block.

    For each output block the inverse transform gives the source region needed;
    only that region is read. Peak memory is roughly one output block plus its
    source footprint, so a 90,000-line OHRC strip warps in a few hundred MB.
    """
    import cv2
    import rasterio
    from rasterio.windows import Window

    inv = _inverse(transform.matrix)
    out_h, out_w = output_shape

    profile = src_dataset.profile.copy()
    profile.update(driver="GTiff", height=out_h, width=out_w, count=1, tiled=True,
                   blockxsize=512, blockysize=512, compress="deflate")
    if profile_overrides:
        profile.update(profile_overrides)

    src_h, src_w = src_dataset.height, src_dataset.width

    with rasterio.open(output_path, "w", **profile) as dst:
        for row in range(0, out_h, block_px):
            for col in range(0, out_w, block_px):
                h = min(block_px, out_h - row)
                w = min(block_px, out_w - col)

                lo, hi = _source_bounds(inv, row, col, h, w)
                x0, y0 = max(0, lo[0]), max(0, lo[1])
                x1, y1 = min(src_w, hi[0]), min(src_h, hi[1])
                if x1 <= x0 or y1 <= y0:
                    continue  # this output block has no source support

                patch = src_dataset.read(1, window=Window(x0, y0, x1 - x0, y1 - y0))

                # Compose: into patch-local source coords, warp, then into
                # block-local output coords.
                pre = np.array([[1, 0, -x0], [0, 1, -y0], [0, 0, 1]], dtype=np.float64)
                post = np.array([[1, 0, -col], [0, 1, -row], [0, 0, 1]], dtype=np.float64)
                full = transform.matrix
                if full.shape != (3, 3):
                    full = np.vstack([full, [0.0, 0.0, 1.0]])
                block_matrix = post @ full @ np.linalg.inv(pre)

                warped = cv2.warpPerspective(patch, block_matrix, (w, h), flags=cv2.INTER_CUBIC)
                dst.write(
                    warped.astype(profile["dtype"]), 1, window=Window(col, row, w, h)
                )

    logger.info("wrote registered product to %s (%dx%d)", output_path, out_w, out_h)


def save_registered_geotiff(
    source: np.ndarray,
    matrix: np.ndarray,
    output_shape: tuple[int, int],
    path,
    *,
    crs: str,
    origin_xy: tuple[float, float],
    pixel_size: float,
    tags: dict | None = None,
    preview_png: bool = True,
) -> dict:
    """Warp ``source`` onto the reference grid and write it as a georeferenced GeoTIFF.

    ``matrix`` maps source pixels to reference-grid pixels (the transform a
    :class:`~lunar_reg.results.PairResult` stores). The output grid is north-up
    with its upper-left corner at ``origin_xy`` in ``crs`` units and square
    pixels of ``pixel_size``. Zero is nodata: pixels with no source support.

    ``tags`` are written into the GeoTIFF metadata, so provenance (pair id,
    matcher, model, thresholds) travels with the file rather than living only in
    the results store. Returns a small summary: path, shape, valid fraction.

    In-memory: use :func:`warp_blockwise` for full-resolution OHRC strips.
    """
    from pathlib import Path

    import cv2
    import rasterio
    from rasterio.transform import Affine

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    h, w = output_shape
    full = matrix if matrix.shape == (3, 3) else np.vstack([matrix, [0.0, 0.0, 1.0]])
    warped = cv2.warpPerspective(source, full, (w, h), flags=cv2.INTER_CUBIC,
                                 borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    geotransform = Affine(pixel_size, 0.0, origin_xy[0], 0.0, -pixel_size, origin_xy[1])
    profile = {
        "driver": "GTiff", "height": h, "width": w, "count": 1,
        "dtype": warped.dtype.name, "crs": crs, "transform": geotransform,
        "nodata": 0, "compress": "deflate", "tiled": True,
        "blockxsize": 256, "blockysize": 256,
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(warped, 1)
        if tags:
            dst.update_tags(**{k: str(v) for k, v in tags.items()})
    if preview_png:
        cv2.imwrite(str(path.with_suffix(".png")), warped)
    valid = float((warped > 0).mean())
    logger.info("wrote registered GeoTIFF %s (%dx%d, %.0f%% valid)", path, w, h, valid * 100)
    return {"path": str(path), "shape": (h, w), "valid_fraction": valid}
