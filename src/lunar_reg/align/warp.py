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


def _full_matrix(transform) -> np.ndarray:
    """3x3 source-to-output matrix from a :class:`Transform` or a 2x3/3x3 array."""
    matrix = np.asarray(getattr(transform, "matrix", transform), dtype=np.float64)
    if matrix.shape == (2, 3):
        return np.vstack([matrix, [0.0, 0.0, 1.0]])
    if matrix.shape != (3, 3):
        raise ValueError(f"transform matrix must be 2x3 or 3x3, got shape {matrix.shape}")
    return matrix


def _source_valid(patch: np.ndarray, src_nodata) -> np.ndarray:
    """uint8 validity of a source patch: ``!= nodata``, or all ones when nodata is unset.

    A float patch's non-finite pixels (NaN, inf) are invalid as well, whatever
    the declared nodata, so they cannot reach a valid output pixel.
    """
    if src_nodata is None:
        valid = np.ones(patch.shape, dtype=bool)
    elif np.isnan(src_nodata):
        valid = ~np.isnan(patch)
    else:
        valid = patch != src_nodata
    if np.issubdtype(patch.dtype, np.floating):
        valid &= np.isfinite(patch)
    return valid.astype(np.uint8)


#: Passes of the 3x3 neighbour-mean fill in :func:`_fill_invalid`. Three passes
#: cover the 4x4 ``INTER_CUBIC`` support of any output pixel whose nearest source
#: pixel is valid (that support lies within 3 px of the nearest pixel).
_FILL_PASSES = 3


def _fill_invalid(patch: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Copy of ``patch`` whose invalid pixels hold a neutral value for interpolation.

    ``INTER_CUBIC`` blends a 4x4 neighbourhood, so a valid output pixel next to a
    source gap would otherwise mix in the nodata value (NaN propagates, -9999
    gives large spurious values). Each invalid pixel within ``_FILL_PASSES`` px
    of a valid one takes the mean of its valid 3x3 neighbours (grown pass by
    pass); farther ones become 0, which no valid output pixel's support reaches.
    Validity itself is unchanged: it still comes from the warped mask.
    """
    import cv2

    invalid = valid == 0
    if not invalid.any():
        return patch
    work = np.float64 if patch.dtype == np.float64 else np.float32
    have = (~invalid).astype(work)
    vals = np.where(invalid, 0, patch).astype(work)
    for _ in range(_FILL_PASSES):
        total = cv2.boxFilter(vals, -1, (3, 3), normalize=False)
        count = cv2.boxFilter(have, -1, (3, 3), normalize=False)
        grow = (have == 0) & (count > 0)
        if not grow.any():
            break
        vals[grow] = total[grow] / count[grow]
        have[grow] = 1
    if np.issubdtype(patch.dtype, np.integer):
        info = np.iinfo(patch.dtype)
        vals = np.clip(np.rint(vals), info.min, info.max)
    out = patch.copy()
    out[invalid] = vals[invalid].astype(patch.dtype)
    return out


def warp_blockwise(
    src_dataset,
    transform: Transform | np.ndarray,
    output_path,
    output_shape: tuple[int, int],
    *,
    dst_transform,
    dst_crs,
    nodata: float = 0,
    block_px: int = DEFAULT_BLOCK_PX,
    profile_overrides: dict | None = None,
) -> None:
    """Warp an open rasterio dataset onto the reference grid, block by block.

    ``transform`` (a :class:`Transform` or a 2x3/3x3 matrix) maps source pixels
    to output pixels. The output is georeferenced on the *reference* grid:
    ``dst_transform`` and ``dst_crs`` are written as given, and nothing is copied
    from the source profile (A083) except the pixel dtype.

    For each output block the inverse transform gives the source region needed;
    only that region is read. A source validity mask (``!= src nodata``, or all
    ones when the source declares no nodata; non-finite float pixels are always
    invalid) is warped with ``INTER_NEAREST`` alongside the image; output pixels
    whose warped mask is 0, including blocks with no source support at all, are
    written as ``nodata``. Invalid source pixels are filled with a neutral value
    before the ``INTER_CUBIC`` warp (:func:`_fill_invalid`), and the warp
    replicates the source edge, so nodata cannot bleed into valid output
    pixels. The warped mask is also written as the GeoTIFF's internal dataset
    mask (``write_mask``), so a valid pixel whose value equals ``nodata`` (a real
    zero, or cubic undershoot clipped to 0) stays valid for mask-aware readers.
    Peak memory is roughly one output block plus its source footprint (a few
    float copies of the footprint while filling invalid pixels), so a
    90,000-line OHRC strip warps in a few hundred MB.
    """
    import cv2
    import rasterio
    from rasterio.windows import Window

    full = _full_matrix(transform)
    inv = np.linalg.inv(full)
    out_h, out_w = output_shape
    dtype = np.dtype(src_dataset.dtypes[0])
    src_nodata = src_dataset.nodata

    profile = {
        "driver": "GTiff",
        "height": out_h,
        "width": out_w,
        "count": 1,
        "dtype": dtype.name,
        "crs": dst_crs,
        "transform": dst_transform,
        "nodata": nodata,
        "tiled": True,
        "blockxsize": 512,
        "blockysize": 512,
        "compress": "deflate",
    }
    if profile_overrides:
        profile.update(profile_overrides)

    src_h, src_w = src_dataset.height, src_dataset.width
    n_blocks = n_unsupported = 0
    n_valid_px = 0

    # Keep the dataset mask inside the .tif rather than as a .msk sidecar.
    with (
        rasterio.Env(GDAL_TIFF_INTERNAL_MASK=True),
        rasterio.open(output_path, "w", **profile) as dst,
    ):
        for row in range(0, out_h, block_px):
            for col in range(0, out_w, block_px):
                h = min(block_px, out_h - row)
                w = min(block_px, out_w - col)
                window = Window(col, row, w, h)
                n_blocks += 1

                lo, hi = _source_bounds(inv, row, col, h, w)
                x0, y0 = max(0, lo[0]), max(0, lo[1])
                x1, y1 = min(src_w, hi[0]), min(src_h, hi[1])
                if x1 <= x0 or y1 <= y0:
                    # No source support: the block is nodata, written explicitly.
                    n_unsupported += 1
                    dst.write(np.full((h, w), nodata, dtype=dtype), 1, window=window)
                    dst.write_mask(np.zeros((h, w), dtype=np.uint8), window=window)
                    continue

                patch = src_dataset.read(1, window=Window(x0, y0, x1 - x0, y1 - y0))
                valid = _source_valid(patch, src_nodata)

                # Compose: into patch-local source coords, warp, then into
                # block-local output coords.
                pre = np.array([[1, 0, -x0], [0, 1, -y0], [0, 0, 1]], dtype=np.float64)
                post = np.array([[1, 0, -col], [0, 1, -row], [0, 0, 1]], dtype=np.float64)
                block_matrix = post @ full @ np.linalg.inv(pre)

                # BORDER_REPLICATE: at the source edge the cubic support reads the
                # edge pixels, not a constant 0 (the mask decides validity there).
                warped = cv2.warpPerspective(
                    _fill_invalid(patch, valid),
                    block_matrix,
                    (w, h),
                    flags=cv2.INTER_CUBIC,
                    borderMode=cv2.BORDER_REPLICATE,
                )
                mask = cv2.warpPerspective(
                    valid,
                    block_matrix,
                    (w, h),
                    flags=cv2.INTER_NEAREST,
                    borderMode=cv2.BORDER_CONSTANT,
                    borderValue=0,
                )
                out = warped.astype(dtype)
                out[mask == 0] = nodata
                n_valid_px += int(np.count_nonzero(mask))
                dst.write(out, 1, window=window)
                dst.write_mask(np.where(mask > 0, 255, 0).astype(np.uint8), window=window)

    logger.info(
        "wrote registered product to %s (%dx%d, %d blocks, %d without source support, "
        "%.1f%% valid)",
        output_path,
        out_w,
        out_h,
        n_blocks,
        n_unsupported,
        100.0 * n_valid_px / max(1, out_h * out_w),
    )


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
    source_valid: np.ndarray | None = None,
) -> dict:
    """Warp ``source`` onto the reference grid and write it as a georeferenced GeoTIFF.

    ``matrix`` maps source pixels to reference-grid pixels (the transform a
    :class:`~lunar_reg.results.PairResult` stores). The output grid is north-up
    with its upper-left corner at ``origin_xy`` in ``crs`` units and square
    pixels of ``pixel_size``.

    Validity comes from a mask, not from pixel values (A130): ``source_valid``
    (non-zero = valid; a ones mask the size of ``source`` when None) is warped
    with ``INTER_NEAREST`` alongside the image, so real zeros inside the valid
    source footprint stay valid. Pass the pair's own validity (e.g.
    ``WindowPair.source_valid``) when ``source`` uses 0 as nodata; invalid
    source pixels are then filled with a neutral value before the
    ``INTER_CUBIC`` warp, and the warp replicates the source edge, so neither
    can bleed into valid output pixels. The mask is written into the GeoTIFF
    as its dataset mask (``write_mask``); pixels outside it are set to 0 and the
    profile keeps ``nodata=0`` for viewers that ignore masks.
    ``valid_fraction`` is the mean of the warped mask.

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
    full = _full_matrix(matrix)
    if source_valid is None:
        valid_src = np.ones(source.shape[:2], dtype=np.uint8)
    else:
        if source_valid.shape != source.shape[:2]:
            raise ValueError(
                f"source_valid shape {source_valid.shape} != source shape {source.shape[:2]}"
            )
        valid_src = (np.asarray(source_valid) != 0).astype(np.uint8)
    warped = cv2.warpPerspective(
        _fill_invalid(source, valid_src) if source.ndim == 2 else source,
        full,
        (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )
    mask = cv2.warpPerspective(
        valid_src,
        full,
        (w, h),
        flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    warped[mask == 0] = 0
    geotransform = Affine(pixel_size, 0.0, origin_xy[0], 0.0, -pixel_size, origin_xy[1])
    profile = {
        "driver": "GTiff",
        "height": h,
        "width": w,
        "count": 1,
        "dtype": warped.dtype.name,
        "crs": crs,
        "transform": geotransform,
        "nodata": 0,
        "compress": "deflate",
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
    }
    mask_uint8 = np.where(mask > 0, 255, 0).astype(np.uint8)
    # Keep the mask inside the .tif rather than as a .msk sidecar.
    with rasterio.Env(GDAL_TIFF_INTERNAL_MASK=True), rasterio.open(path, "w", **profile) as dst:
        dst.write(warped, 1)
        dst.write_mask(mask_uint8)
        if tags:
            dst.update_tags(**{k: str(v) for k, v in tags.items()})
    if preview_png:
        cv2.imwrite(str(path.with_suffix(".png")), warped)
    valid = float(mask.mean())
    logger.info("wrote registered GeoTIFF %s (%dx%d, %.0f%% valid)", path, w, h, valid * 100)
    return {"path": str(path), "shape": (h, w), "valid_fraction": valid}
