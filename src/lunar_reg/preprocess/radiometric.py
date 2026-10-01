"""Intensity conditioning: normalisation, CLAHE, and the paper's enhancement steps.

Implements steps 4.1.3 (intensity normalisation) and the intensity parts of 4.2
from Makharia et al. (arXiv:2509.04775).

Two of these have paper-stated values -- normalisation targets 8-bit 0-255, and
inversion is exactly ``255 - pixel``. The rest (CLAHE clip limit and tile grid,
dilation structuring element, log transform constant) are **not stated in the
paper**; the defaults here are ours. See :mod:`lunar_reg.preprocess.params`.
"""

from __future__ import annotations

import logging
import math

import numpy as np

from lunar_reg.preprocess.params import (
    CLAHE_CLIP_LIMIT,
    CLAHE_TILE_GRID,
    DILATION_KERNEL_SHAPE,
    DILATION_KERNEL_SIZE,
    INVERSION_MAX,
    NORMALIZE_TARGET_MAX,
)
from lunar_reg.preprocess.shadow import _effective_valid, shadow_mask

logger = logging.getLogger(__name__)

#: PLACEHOLDER values -- the paper specifies neither. Sourced from the params
#: registry so provenance stays in one place.
DEFAULT_CLAHE_CLIP = CLAHE_CLIP_LIMIT.value
DEFAULT_CLAHE_GRID = CLAHE_TILE_GRID.value

#: With a nodata mask, uint8 outputs reserve 0 for nodata and put real data in
#: 1..255 (Phase_1/LLD/preprocess_nodata.md §2, same as scripts/run_vikram.stretch_u8).
VALID_U8_MIN = 1


def to_uint8(
    image: np.ndarray,
    percentiles: tuple[float, float] = (1.0, 99.0),
    valid: np.ndarray | None = None,
) -> np.ndarray:
    """Percentile-stretch to 8-bit.

    OHRC and TMC-2 products arrive as 10/12/16-bit integers, and OpenCV's CLAHE
    accepts only uint8 or uint16. Percentile clipping rather than min/max keeps
    a single saturated pixel -- common near crater rims -- from crushing the
    rest of the histogram.

    With ``valid`` (True = real data) the percentiles come from valid finite
    pixels only, valid pixels map into 1..255 by
    ``clip((x - lo) / max(hi - lo, 1e-6) * 254 + 1, 1, 255)`` and invalid pixels
    are 0.
    """
    image = np.asarray(image)
    if valid is not None:
        v = _effective_valid(image, valid, "to_uint8")
        out = np.zeros(image.shape, dtype=np.uint8)
        if not v.any():
            return out
        vals = image[v].astype(np.float32)
        lo, hi = np.percentile(vals, percentiles)
        scaled = (vals - lo) / max(float(hi - lo), 1e-6) * 254 + 1
        out[v] = np.clip(scaled, VALID_U8_MIN, 255).astype(np.uint8)
        return out
    finite = image[np.isfinite(image)]
    if finite.size == 0:
        return np.zeros(image.shape, dtype=np.uint8)
    lo, hi = np.percentile(finite, percentiles)
    if hi <= lo:
        return np.zeros(image.shape, dtype=np.uint8)
    scaled = (np.clip(image, lo, hi) - lo) / (hi - lo)
    # Paper step 4.1.3: "All datasets were normalised to an 8-bit range (0-255)".
    return (scaled * float(NORMALIZE_TARGET_MAX.value)).astype(np.uint8)


def apply_clahe(
    image: np.ndarray,
    clip_limit: float = DEFAULT_CLAHE_CLIP,
    grid_size: tuple[int, int] = DEFAULT_CLAHE_GRID,
    valid: np.ndarray | None = None,
) -> np.ndarray:
    """Contrast-limited adaptive histogram equalisation on a single-band image.

    With ``valid`` a non-uint8 input is stretched by ``to_uint8(image,
    valid=valid)`` first; after CLAHE invalid pixels are 0 and valid pixels are
    clipped to >= 1.
    """
    import cv2

    if valid is not None:
        v = _effective_valid(image, valid, "apply_clahe")
        if not v.any():
            return np.zeros(np.shape(image), dtype=np.uint8)
        arr = image if image.dtype == np.uint8 else to_uint8(image, valid=v)
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=grid_size)
        out = np.maximum(clahe.apply(arr), VALID_U8_MIN).astype(np.uint8)
        out[~v] = 0
        return out

    if image.dtype != np.uint8:
        image = to_uint8(image)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=grid_size)
    return clahe.apply(image)


def normalize_intensity(image: np.ndarray, valid: np.ndarray | None = None) -> np.ndarray:
    """Zero-mean, unit-variance normalisation over valid pixels.

    Removes the global brightness offset between two acquisitions. It does not
    address the *directional* component of illumination difference -- that is
    what CLAHE and shadow handling are for.

    With ``valid`` the mean and standard deviation come from valid finite
    pixels only and invalid pixels are NaN.
    """
    image = np.asarray(image, dtype=np.float32)
    if valid is not None:
        v = _effective_valid(image, valid, "normalize_intensity")
        out = np.full(image.shape, np.nan, dtype=np.float32)
        if not v.any():
            return out
        mean = image[v].mean()
        std = image[v].std()
        out[v] = 0.0 if std < 1e-8 else (image[v] - mean) / std
        return out
    valid = np.isfinite(image)
    if not valid.any():
        return np.zeros_like(image)
    mean = image[valid].mean()
    std = image[valid].std()
    if std < 1e-8:
        return np.zeros_like(image)
    out = np.zeros_like(image)
    out[valid] = (image[valid] - mean) / std
    return out


def suppress_shadows(
    image: np.ndarray, percentile: float = 5.0, valid: np.ndarray | None = None
) -> np.ndarray:
    """Replace shadowed pixels with the scene median so they generate no features.

    With ``valid`` the shadow mask and the replacement median use valid finite
    pixels only and invalid pixels are NaN.
    """
    image = np.asarray(image, dtype=np.float32).copy()
    if valid is not None:
        v = _effective_valid(image, valid, "suppress_shadows")
        if not v.any():
            return np.full(image.shape, np.nan, dtype=np.float32)
        mask = shadow_mask(image, percentile, valid=v)
        lit = image[v & ~mask]
        if lit.size:
            image[mask] = float(np.median(lit))
        image[~v] = np.nan
        return image
    mask = shadow_mask(image, percentile)
    finite = image[np.isfinite(image) & ~mask]
    if finite.size:
        image[mask] = float(np.median(finite))
    return image


def invert(image: np.ndarray, valid: np.ndarray | None = None) -> np.ndarray:
    """Complement an 8-bit image: ``255 - pixel``.

    Paper step 4.2.2, and one of the few with an exact stated formula:
    "transformed pixel values to their complement (255 - pixel value)". Its
    stated purpose is making crater rim structures more detectable.

    With ``valid`` 0 is reserved for nodata, so valid pixels map by
    ``256 - pixel`` (1..255 -> 255..1, clipped to 1..255) and invalid stay 0.
    """
    if valid is not None:
        v = _effective_valid(image, valid, "invert")
        out = np.zeros(np.shape(image), dtype=np.uint8)
        if not v.any():
            return out
        arr = image if image.dtype == np.uint8 else to_uint8(image, valid=v)
        flipped = INVERSION_MAX.value + VALID_U8_MIN - arr[v].astype(np.int16)
        out[v] = flipped.clip(VALID_U8_MIN, 255).astype(np.uint8)
        return out
    arr = image if image.dtype == np.uint8 else to_uint8(image)
    return (INVERSION_MAX.value - arr.astype(np.int16)).clip(0, 255).astype(np.uint8)


def dilate(
    image: np.ndarray,
    kernel_size: int = DILATION_KERNEL_SIZE.value,
    shape: str = DILATION_KERNEL_SHAPE.value,
    valid: np.ndarray | None = None,
) -> np.ndarray:
    """Morphological dilation to thicken crater rims and elevated structure.

    Paper step 4.2.3. The paper says only "using a defined structuring element"
    -- shape and size here are PLACEHOLDERS. An ellipse is the default because
    crater rims are roughly circular and a rectangular element biases them
    toward the axes.

    With ``valid`` a non-uint8 input is stretched with the mask, and invalid
    pixels are set back to 0 after dilation (dilation would otherwise spread
    valid values into the nodata border).
    """
    import cv2

    shapes = {
        "ellipse": cv2.MORPH_ELLIPSE,
        "rect": cv2.MORPH_RECT,
        "cross": cv2.MORPH_CROSS,
    }
    if shape not in shapes:
        raise ValueError(f"shape must be one of {sorted(shapes)}, got {shape!r}")
    if kernel_size < 1:
        raise ValueError(f"kernel_size must be >= 1, got {kernel_size}")

    kernel = cv2.getStructuringElement(shapes[shape], (kernel_size, kernel_size))
    if valid is not None:
        v = _effective_valid(image, valid, "dilate")
        if not v.any():
            return np.zeros(np.shape(image), dtype=np.uint8)
        arr = image if image.dtype == np.uint8 else to_uint8(image, valid=v)
        out = cv2.dilate(arr, kernel)
        out[~v] = 0
        return out
    arr = image if image.dtype == np.uint8 else to_uint8(image)
    return cv2.dilate(arr, kernel)


def log_transform(
    image: np.ndarray, scale: float | None = None, valid: np.ndarray | None = None
) -> np.ndarray:
    """Compress highlights and lift low-intensity detail.

    Paper step 4.2.3 of the IIRS/WAC track: "enhance low-intensity details while
    compressing higher-intensity values". No constant is given, so ``scale=None``
    derives the standard normalising one, ``c = 255 / log(1 + max)``.

    With ``valid`` the shift and the scale come from valid finite pixels only
    and invalid pixels are 0.
    """
    arr = np.asarray(image, dtype=np.float32)
    if valid is not None:
        v = _effective_valid(arr, valid, "log_transform")
        out = np.zeros(arr.shape, dtype=np.uint8)
        if not v.any():
            return out
        vals = arr[v]
        shifted_v = vals - min(0.0, float(vals.min()))
        peak_v = float(shifted_v.max())
        if peak_v <= 0:
            return out
        c = scale if scale is not None else 255.0 / math.log1p(peak_v)
        out[v] = np.clip(c * np.log1p(np.maximum(shifted_v, 0.0)), 0, 255).astype(np.uint8)
        return out
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return np.zeros(arr.shape, dtype=np.uint8)

    shifted = arr - min(0.0, float(finite.min()))
    peak = float(np.nanmax(shifted))
    if peak <= 0:
        return np.zeros(arr.shape, dtype=np.uint8)

    c = scale if scale is not None else 255.0 / math.log1p(peak)
    return np.clip(c * np.log1p(np.maximum(shifted, 0.0)), 0, 255).astype(np.uint8)


def match_histogram(
    source: np.ndarray,
    reference: np.ndarray,
    valid: np.ndarray | None = None,
    reference_valid: np.ndarray | None = None,
) -> np.ndarray:
    """Reshape ``source``'s intensity distribution to match ``reference``'s.

    Paper step 4.2.1 of the IIRS/WAC track, for radiometric consistency between
    sensors with different calibration. Implemented by mapping through the two
    empirical CDFs, which needs no parameters -- so unlike most of this module
    there is nothing here to tune.

    With ``valid`` / ``reference_valid`` each CDF comes from that image's valid
    pixels only (an omitted mask means every pixel of that image is valid), the
    lookup is applied to valid source pixels and invalid source pixels are 0.
    """
    if valid is not None or reference_valid is not None:
        return _match_histogram_valid(source, reference, valid, reference_valid)
    src = source if source.dtype == np.uint8 else to_uint8(source)
    ref = reference if reference.dtype == np.uint8 else to_uint8(reference)

    src_hist = np.bincount(src.ravel(), minlength=256).astype(np.float64)
    ref_hist = np.bincount(ref.ravel(), minlength=256).astype(np.float64)
    src_cdf = np.cumsum(src_hist) / max(src.size, 1)
    ref_cdf = np.cumsum(ref_hist) / max(ref.size, 1)

    lookup = np.searchsorted(ref_cdf, src_cdf).clip(0, 255).astype(np.uint8)
    return lookup[src]


def _match_histogram_valid(
    source: np.ndarray,
    reference: np.ndarray,
    valid: np.ndarray | None,
    reference_valid: np.ndarray | None,
) -> np.ndarray:
    """Masked branch of :func:`match_histogram` (Phase_1/LLD/preprocess_nodata.md §2)."""
    sv = _effective_valid(
        source, np.ones(np.shape(source), bool) if valid is None else valid, "match_histogram"
    )
    rv = _effective_valid(
        reference,
        np.ones(np.shape(reference), bool) if reference_valid is None else reference_valid,
        "match_histogram(reference)",
    )
    out = np.zeros(np.shape(source), dtype=np.uint8)
    if not sv.any() or not rv.any():
        return out
    src = source if source.dtype == np.uint8 else to_uint8(source, valid=sv)
    ref = reference if reference.dtype == np.uint8 else to_uint8(reference, valid=rv)
    src_vals = src[sv]
    ref_vals = ref[rv]

    src_cdf = np.cumsum(np.bincount(src_vals, minlength=256).astype(np.float64)) / src_vals.size
    ref_cdf = np.cumsum(np.bincount(ref_vals, minlength=256).astype(np.float64)) / ref_vals.size
    lookup = np.searchsorted(ref_cdf, src_cdf).clip(0, 255).astype(np.uint8)
    out[sv] = lookup[src_vals]
    return out


def standard_chain(
    image: np.ndarray,
    clahe: bool = True,
    suppress_shadow: bool = True,
    shadow_percentile: float = 5.0,
    valid: np.ndarray | None = None,
) -> np.ndarray:
    """Shorthand chain: shadow suppression then 8-bit normalisation then CLAHE.

    Kept as a convenience for single-image calls. For anything you intend to
    ablate or report, use :func:`lunar_reg.preprocess.pipeline.run_pipeline`,
    which follows the paper's actual structure and records what it did.

    Order matters: shadows are flattened first so they do not dominate the
    histogram that CLAHE then redistributes.

    ``valid`` is passed through to every step as the effective mask
    ``valid & isfinite(image)``, computed once on the input: after
    :func:`to_uint8` a NaN pixel is a finite 0 and would otherwise count as
    valid again in :func:`apply_clahe`.
    """
    out = np.asarray(image)
    if valid is not None:
        valid = _effective_valid(out, valid, "standard_chain")
    if suppress_shadow:
        out = suppress_shadows(out, shadow_percentile, valid=valid)
    out = to_uint8(out, valid=valid)
    if clahe:
        out = apply_clahe(out, valid=valid)
    return out
