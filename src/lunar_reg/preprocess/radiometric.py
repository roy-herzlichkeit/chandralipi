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
from lunar_reg.preprocess.shadow import shadow_mask

logger = logging.getLogger(__name__)

#: PLACEHOLDER values -- the paper specifies neither. Sourced from the params
#: registry so provenance stays in one place.
DEFAULT_CLAHE_CLIP = CLAHE_CLIP_LIMIT.value
DEFAULT_CLAHE_GRID = CLAHE_TILE_GRID.value


def to_uint8(image: np.ndarray, percentiles: tuple[float, float] = (1.0, 99.0)) -> np.ndarray:
    """Percentile-stretch to 8-bit.

    OHRC and TMC-2 products arrive as 10/12/16-bit integers, and OpenCV's CLAHE
    accepts only uint8 or uint16. Percentile clipping rather than min/max keeps
    a single saturated pixel -- common near crater rims -- from crushing the
    rest of the histogram.
    """
    image = np.asarray(image)
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
) -> np.ndarray:
    """Contrast-limited adaptive histogram equalisation on a single-band image."""
    import cv2

    if image.dtype != np.uint8:
        image = to_uint8(image)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=grid_size)
    return clahe.apply(image)


def normalize_intensity(image: np.ndarray) -> np.ndarray:
    """Zero-mean, unit-variance normalisation over valid pixels.

    Removes the global brightness offset between two acquisitions. It does not
    address the *directional* component of illumination difference -- that is
    what CLAHE and shadow handling are for.
    """
    image = np.asarray(image, dtype=np.float32)
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


def suppress_shadows(image: np.ndarray, percentile: float = 5.0) -> np.ndarray:
    """Replace shadowed pixels with the scene median so they generate no features."""
    image = np.asarray(image, dtype=np.float32).copy()
    mask = shadow_mask(image, percentile)
    finite = image[np.isfinite(image) & ~mask]
    if finite.size:
        image[mask] = float(np.median(finite))
    return image


def invert(image: np.ndarray) -> np.ndarray:
    """Complement an 8-bit image: ``255 - pixel``.

    Paper step 4.2.2, and one of the few with an exact stated formula:
    "transformed pixel values to their complement (255 - pixel value)". Its
    stated purpose is making crater rim structures more detectable.
    """
    arr = image if image.dtype == np.uint8 else to_uint8(image)
    return (INVERSION_MAX.value - arr.astype(np.int16)).clip(0, 255).astype(np.uint8)


def dilate(
    image: np.ndarray,
    kernel_size: int = DILATION_KERNEL_SIZE.value,
    shape: str = DILATION_KERNEL_SHAPE.value,
) -> np.ndarray:
    """Morphological dilation to thicken crater rims and elevated structure.

    Paper step 4.2.3. The paper says only "using a defined structuring element"
    -- shape and size here are PLACEHOLDERS. An ellipse is the default because
    crater rims are roughly circular and a rectangular element biases them
    toward the axes.
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

    arr = image if image.dtype == np.uint8 else to_uint8(image)
    kernel = cv2.getStructuringElement(shapes[shape], (kernel_size, kernel_size))
    return cv2.dilate(arr, kernel)


def log_transform(image: np.ndarray, scale: float | None = None) -> np.ndarray:
    """Compress highlights and lift low-intensity detail.

    Paper step 4.2.3 of the IIRS/WAC track: "enhance low-intensity details while
    compressing higher-intensity values". No constant is given, so ``scale=None``
    derives the standard normalising one, ``c = 255 / log(1 + max)``.
    """
    arr = np.asarray(image, dtype=np.float32)
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return np.zeros(arr.shape, dtype=np.uint8)

    shifted = arr - min(0.0, float(finite.min()))
    peak = float(np.nanmax(shifted))
    if peak <= 0:
        return np.zeros(arr.shape, dtype=np.uint8)

    c = scale if scale is not None else 255.0 / math.log1p(peak)
    return np.clip(c * np.log1p(np.maximum(shifted, 0.0)), 0, 255).astype(np.uint8)


def match_histogram(source: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """Reshape ``source``'s intensity distribution to match ``reference``'s.

    Paper step 4.2.1 of the IIRS/WAC track, for radiometric consistency between
    sensors with different calibration. Implemented by mapping through the two
    empirical CDFs, which needs no parameters -- so unlike most of this module
    there is nothing here to tune.
    """
    src = source if source.dtype == np.uint8 else to_uint8(source)
    ref = reference if reference.dtype == np.uint8 else to_uint8(reference)

    src_hist = np.bincount(src.ravel(), minlength=256).astype(np.float64)
    ref_hist = np.bincount(ref.ravel(), minlength=256).astype(np.float64)
    src_cdf = np.cumsum(src_hist) / max(src.size, 1)
    ref_cdf = np.cumsum(ref_hist) / max(ref.size, 1)

    lookup = np.searchsorted(ref_cdf, src_cdf).clip(0, 255).astype(np.uint8)
    return lookup[src]


def standard_chain(
    image: np.ndarray,
    clahe: bool = True,
    suppress_shadow: bool = True,
    shadow_percentile: float = 5.0,
) -> np.ndarray:
    """Shorthand chain: shadow suppression then 8-bit normalisation then CLAHE.

    Kept as a convenience for single-image calls. For anything you intend to
    ablate or report, use :func:`lunar_reg.preprocess.pipeline.run_pipeline`,
    which follows the paper's actual structure and records what it did.

    Order matters: shadows are flattened first so they do not dominate the
    histogram that CLAHE then redistributes.
    """
    out = np.asarray(image)
    if suppress_shadow:
        out = suppress_shadows(out, shadow_percentile)
    out = to_uint8(out)
    if clahe:
        out = apply_clahe(out)
    return out
