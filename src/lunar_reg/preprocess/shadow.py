"""Shadow normalisation for extreme sun-angle cases.

Step 4.2.2 of Makharia et al., in their IIRS/WAC track. The paper states the
*intent* precisely and the *method* not at all::

    "This technique adjusted the intensity values in shadowed regions to make
     features more visible while preserving overall scene contrast."
    "By normalizing shadows, we revealed features that would otherwise be lost
     in dark regions"

Note "revealed", not "removed": the goal is to recover structure inside shadow,
not to mask it out. No threshold, no formula and no parameters are given, so
three methods are offered here and all of their parameters are placeholders.

Which to use
------------
``gamma`` is the default because it matches the stated intent most directly --
it brightens shadowed pixels while preserving their relative structure. ``mask``
is the blunt alternative (flatten shadow so it generates no keypoints), useful
when shadow is so deep that nothing is recoverable and spurious keypoints are
the bigger problem. ``retinex`` divides out a smoothed illumination estimate,
which handles a smooth illumination gradient better than a hard threshold but
can halo at sharp shadow edges.
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)

SHADOW_METHODS = ("gamma", "mask", "retinex", "none")


def _effective_valid(image: np.ndarray, valid: np.ndarray | None, caller: str) -> np.ndarray:
    """Return ``valid & isfinite(image)`` as a bool array (Phase_1/LLD/preprocess_nodata.md §1).

    ``valid`` is the nodata mask (True = real data); it must match ``image``'s
    shape. When nothing is valid, one warning naming ``caller`` is logged and the
    caller returns its all-zero / all-NaN output.
    """
    arr = np.asarray(image)
    mask = np.asarray(valid, dtype=bool)
    if mask.shape != arr.shape:
        raise ValueError(f"{caller}: valid mask shape {mask.shape} != image shape {arr.shape}")
    if np.issubdtype(arr.dtype, np.floating):
        mask = mask & np.isfinite(arr)
    if not mask.any():
        logger.warning("%s: valid mask has no valid finite pixel; returning empty output", caller)
    return mask


def shadow_mask(
    image: np.ndarray, percentile: float = 5.0, valid: np.ndarray | None = None
) -> np.ndarray:
    """Boolean mask of probable cast shadow, by intensity percentile.

    A percentile rather than a fixed level, because absolute DN varies with
    sensor gain and exposure. The trade-off: at very low sun elevation a real
    scene may be 30%+ shadow, and a fixed 5% then labels only the deepest part.
    Report :func:`shadow_fraction` alongside any result that depends on this.

    With ``valid`` the percentile is taken over valid finite pixels only and the
    mask is False wherever ``valid`` is False.
    """
    image = np.asarray(image, dtype=np.float32)
    if valid is not None:
        v = _effective_valid(image, valid, "shadow_mask")
        if not v.any():
            return np.zeros(image.shape, dtype=bool)
        return (image <= np.percentile(image[v], percentile)) & v
    finite = image[np.isfinite(image)]
    if finite.size == 0:
        return np.zeros(image.shape, dtype=bool)
    return image <= np.percentile(finite, percentile)


def shadow_fraction(
    image: np.ndarray, percentile: float = 5.0, valid: np.ndarray | None = None
) -> float:
    """Fraction of the image the mask actually calls shadow.

    This is **not** reliably ``percentile / 100``. The mask uses ``<=``, so every
    pixel tied at the threshold value is included -- and real lunar shadow
    saturates at a handful of low DN values, so ties are the norm rather than an
    edge case. Measured on a synthetic scene with a deep-shadow quadrant, a
    nominal 5th-percentile threshold selected 9.1% of pixels.

    Always call this after choosing ``shadow_percentile`` to see what the
    threshold is really selecting; the requested percentile is a lower bound on
    the fraction treated as shadow, not the value.

    With ``valid`` the fraction is over valid finite pixels only.
    """
    if valid is not None:
        v = _effective_valid(image, valid, "shadow_fraction")
        if not v.any():
            return 0.0
        return float(shadow_mask(image, percentile, valid=v)[v].mean())
    return float(shadow_mask(image, percentile).mean())


def estimate_shadow_severity(
    image: np.ndarray, dark_level: float = 0.15, valid: np.ndarray | None = None
) -> float:
    """Fraction of pixels below an absolute darkness level, in ``[0, 1]``.

    Unlike :func:`shadow_fraction` this does not move with the percentile, so it
    is a real measure of how shadowed a scene is. Use it to decide *whether* a
    scene is an extreme sun-angle case at all -- the percentile approach labels
    5% of a fully-lit image as "shadow" regardless.

    With ``valid`` the range and the fraction use valid finite pixels only.
    """
    image = np.asarray(image, dtype=np.float32)
    if valid is not None:
        finite = image[_effective_valid(image, valid, "estimate_shadow_severity")]
    else:
        finite = image[np.isfinite(image)]
    if finite.size == 0:
        return 0.0
    lo, hi = float(finite.min()), float(finite.max())
    if hi <= lo:
        return 0.0
    return float(((finite - lo) / (hi - lo) < dark_level).mean())


def normalize_shadows(
    image: np.ndarray,
    method: str = "gamma",
    percentile: float = 5.0,
    gamma: float = 0.5,
    sigma: float = 25.0,
    valid: np.ndarray | None = None,
) -> np.ndarray:
    """Brighten or suppress shadowed regions.

    All parameters are placeholders -- the paper states none of them. See
    :mod:`lunar_reg.preprocess.params`.

    With ``valid`` every method takes its statistics from valid finite pixels
    only and the output is a float32 copy with NaN wherever ``valid`` is False
    (also for ``method="none"``).
    """
    if method not in SHADOW_METHODS:
        raise ValueError(f"method must be one of {SHADOW_METHODS}, got {method!r}")
    if valid is None:
        if method == "none":
            return np.asarray(image)
        if method == "gamma":
            return _gamma_shadow(image, percentile, gamma)
        if method == "mask":
            return _mask_shadow(image, percentile)
        return _retinex(image, sigma)

    v = _effective_valid(image, valid, "normalize_shadows")
    if not v.any():
        return np.full(np.shape(image), np.nan, dtype=np.float32)
    if method == "none":
        out = np.asarray(image, dtype=np.float32)
    elif method == "gamma":
        out = _gamma_shadow(image, percentile, gamma, valid=v)
    elif method == "mask":
        out = _mask_shadow(image, percentile, valid=v)
    else:
        out = _retinex(image, sigma, valid=v)
    # Copy: the helpers may hand back the caller's own float32 array unchanged.
    out = np.array(out, dtype=np.float32, copy=True)
    out[~v] = np.nan
    return out


def _gamma_shadow(
    image: np.ndarray, percentile: float, gamma: float, valid: np.ndarray | None = None
) -> np.ndarray:
    """Apply a brightening gamma inside shadow only.

    The intensity is renormalised **within the shadow range** ``[lo, threshold]``
    before the gamma is applied, not against the full image range. That detail is
    load-bearing: normalising against the full range makes the gamma output a
    tiny fraction of it, and the step then *darkens* shadow instead of lifting it
    -- the exact opposite of the paper's intent.

    The map is ``lo + ((x - lo) / (threshold - lo)) ** gamma * (threshold - lo)``,
    which for ``gamma < 1``:

    * brightens every shadowed pixel (``t**gamma > t`` on ``0 < t < 1``),
    * is monotonic, so structure inside the shadow survives -- the paper
      "revealed" features rather than removing them,
    * maps ``threshold`` to itself, so there is no seam at the shadow boundary,
    * leaves lit terrain untouched, preserving overall scene contrast.
    """
    arr = np.asarray(image, dtype=np.float32)
    mask = shadow_mask(arr, percentile, valid=valid)
    if not mask.any():
        return arr

    finite = arr[valid] if valid is not None else arr[np.isfinite(arr)]
    lo, hi = float(finite.min()), float(finite.max())
    if hi <= lo:
        return arr

    threshold = float(np.percentile(finite, percentile))
    span = threshold - lo
    if span <= 1e-6:
        # Shadow is a single quantised level; a gamma cannot reveal structure
        # that is not there. Leave it rather than manufacture detail.
        return arr

    out = arr.copy()
    t = np.clip((arr[mask] - lo) / span, 0.0, 1.0)
    out[mask] = lo + np.power(t, gamma) * span
    return out


def _mask_shadow(
    image: np.ndarray, percentile: float, valid: np.ndarray | None = None
) -> np.ndarray:
    """Flatten shadow to the scene median so it generates no keypoints."""
    arr = np.asarray(image, dtype=np.float32).copy()
    mask = shadow_mask(arr, percentile, valid=valid)
    usable = valid if valid is not None else np.isfinite(arr)
    lit = arr[usable & ~mask]
    if lit.size:
        arr[mask] = float(np.median(lit))
    return arr


def _retinex(image: np.ndarray, sigma: float, valid: np.ndarray | None = None) -> np.ndarray:
    """Single-scale retinex: divide out a Gaussian-blurred illumination estimate.

    Handles a smooth illumination gradient across the frame better than a hard
    threshold, but haloes at sharp shadow boundaries -- and lunar shadows at low
    sun elevation are about as sharp as boundaries get, so check the output.

    NaN and invalid pixels (A107) are filled with the median of the valid finite
    pixels before blurring, so they cannot spread NaN through the Gaussian, and
    are set back to NaN afterwards. On an all-finite image with ``valid=None``
    nothing is filled and the output is unchanged.
    """
    import cv2

    arr = np.asarray(image, dtype=np.float32)
    usable = np.isfinite(arr) if valid is None else valid & np.isfinite(arr)
    finite = arr[usable]
    if finite.size == 0:
        return arr
    lo, hi = float(finite.min()), float(finite.max())
    if hi <= lo:
        return arr

    filled = ~usable
    work = arr
    if filled.any():
        work = arr.copy()
        work[filled] = float(np.median(finite))

    scaled = (work - lo) / (hi - lo) + 1e-3
    illumination = cv2.GaussianBlur(scaled, (0, 0), sigma)
    reflectance = np.log(scaled) - np.log(np.maximum(illumination, 1e-6))

    kept = reflectance[usable]
    r_lo, r_hi = float(kept.min()), float(kept.max())
    if r_hi <= r_lo:
        return arr
    out = ((reflectance - r_lo) / (r_hi - r_lo) * (hi - lo) + lo).astype(np.float32)
    if filled.any():
        out[filled] = np.nan
    return out
