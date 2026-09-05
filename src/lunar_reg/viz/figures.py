"""Rendered views of a registered pair, as plain RGB arrays.

Returning arrays rather than matplotlib figures is deliberate: the same
functions then serve the Streamlit dashboard, the demo script, and a report
without any of them owning a plotting backend or a display. Anything that can
show an image can show these.
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)

#: Inliers green, outliers red. Chosen for colour-blind legibility against grey
#: terrain: the two differ in lightness as well as hue, so they remain
#: distinguishable in a monochrome print of a report.
INLIER_COLOUR = (60, 220, 120)
OUTLIER_COLOUR = (235, 80, 70)


def to_rgb(image: np.ndarray) -> np.ndarray:
    """Any single- or three-band array to 8-bit RGB."""
    import cv2

    array = np.asarray(image)
    if array.ndim == 3 and array.shape[2] == 3:
        rgb = array
    else:
        if array.ndim == 3:
            array = array[..., 0]
        rgb = cv2.cvtColor(array, cv2.COLOR_GRAY2RGB)
    if rgb.dtype != np.uint8:
        finite = rgb[np.isfinite(rgb)]
        lo, hi = (float(finite.min()), float(finite.max())) if finite.size else (0.0, 1.0)
        span = hi - lo if hi > lo else 1.0
        rgb = np.clip((rgb - lo) / span * 255.0, 0, 255).astype(np.uint8)
    return rgb


def side_by_side_matches(
    source: np.ndarray,
    reference: np.ndarray,
    src_pts: np.ndarray,
    dst_pts: np.ndarray,
    inlier_mask: np.ndarray | None = None,
    max_lines: int = 120,
    scale: float = 1.0,
    draw_outliers: bool = True,
) -> np.ndarray:
    """Two images side by side with correspondence lines drawn between them.

    ``max_lines`` subsamples for legibility. The subsample is **evenly spaced
    through the point order, not random**, so the figure is reproducible and two
    runs can be compared honestly. Counts in the caption should always come from
    the full set, never from what is drawn.
    """
    import cv2

    left, right = to_rgb(source), to_rgb(reference)
    height = max(left.shape[0], right.shape[0])
    canvas = np.zeros((height, left.shape[1] + right.shape[1], 3), dtype=np.uint8)
    canvas[: left.shape[0], : left.shape[1]] = left
    canvas[: right.shape[0], left.shape[1]:] = right
    offset = left.shape[1]

    src = np.asarray(src_pts, dtype=np.float64) * scale
    dst = np.asarray(dst_pts, dtype=np.float64) * scale
    mask = (
        np.ones(len(src), dtype=bool) if inlier_mask is None
        else np.asarray(inlier_mask, dtype=bool)
    )

    order = np.arange(len(src))
    if not draw_outliers:
        order = order[mask]
    if len(order) > max_lines:
        order = order[np.linspace(0, len(order) - 1, max_lines).astype(int)]

    # Outliers first, so inliers are drawn on top and are never hidden.
    for is_inlier in (False, True):
        colour = INLIER_COLOUR if is_inlier else OUTLIER_COLOUR
        for i in order:
            if bool(mask[i]) != is_inlier:
                continue
            a = (int(round(src[i, 0])), int(round(src[i, 1])))
            b = (int(round(dst[i, 0])) + offset, int(round(dst[i, 1])))
            cv2.line(canvas, a, b, colour, 1, cv2.LINE_AA)
            cv2.circle(canvas, a, 3, colour, -1, cv2.LINE_AA)
            cv2.circle(canvas, b, 3, colour, -1, cv2.LINE_AA)
    return canvas


def warp_source(source: np.ndarray, transform: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    """Warp the source into the reference frame."""
    import cv2

    matrix = np.asarray(transform, dtype=np.float64)
    if matrix.shape == (2, 3):
        matrix = np.vstack([matrix, [0.0, 0.0, 1.0]])
    rows, cols = shape
    return cv2.warpPerspective(
        np.asarray(source), matrix, (cols, rows), flags=cv2.INTER_CUBIC
    )


def checkerboard(
    source: np.ndarray, reference: np.ndarray, transform: np.ndarray, tile: int = 64
) -> np.ndarray:
    """Alternating tiles of warped source and reference.

    The most honest registration check there is: a feature crossing a tile
    boundary either continues or it steps, and a one-pixel step is visible to
    the eye where a blend would smear it into a blur that reads as focus.
    """
    reference_rgb = to_rgb(reference)
    warped = to_rgb(warp_source(source, transform, reference.shape[:2]))

    rows, cols = reference_rgb.shape[:2]
    yy, xx = np.mgrid[0:rows, 0:cols]
    pick = (((yy // tile) + (xx // tile)) % 2).astype(bool)
    out = reference_rgb.copy()
    out[pick] = warped[pick]
    return out


def blend(
    source: np.ndarray, reference: np.ndarray, transform: np.ndarray, alpha: float = 0.5
) -> np.ndarray:
    """Straight alpha blend of warped source over reference."""
    import cv2

    warped = to_rgb(warp_source(source, transform, reference.shape[:2]))
    return cv2.addWeighted(warped, alpha, to_rgb(reference), 1.0 - alpha, 0.0)


def anaglyph(source: np.ndarray, reference: np.ndarray, transform: np.ndarray) -> np.ndarray:
    """Reference in red, warped source in cyan.

    Misregistration shows as coloured fringing whose direction indicates which
    way the error runs. Sharper than a blend at revealing sub-pixel residual
    shift, because the eye is very good at spotting colour edges.
    """
    reference_grey = to_rgb(reference)[..., 0]
    warped_grey = to_rgb(warp_source(source, transform, reference.shape[:2]))[..., 0]
    return np.dstack([reference_grey, warped_grey, warped_grey])


def coverage_heatmap(
    spread: np.ndarray, shape: tuple[int, int], gate_px: float = 1.0
) -> np.ndarray:
    """Colour the conditioning map: cool where trusted, hot where extrapolated.

    Turns the conditioning metric from a number into a picture of *where* the
    registration is trustworthy, which is the part a reviewer actually wants to
    see and the part a single RMSE cannot show.
    """
    import cv2

    grid = np.asarray(spread, dtype=np.float64)
    finite = np.isfinite(grid)
    normalised = np.zeros_like(grid)
    if finite.any():
        # Scale against the gate, so colour has a fixed meaning across pairs and
        # two pairs can be compared by eye: coolest at zero error, fully hot at
        # the gate and beyond.
        normalised[finite] = np.clip(grid[finite] / max(gate_px, 1e-6), 0.0, 1.0)
    normalised[~finite] = 1.0

    rows, cols = shape
    # Linear, not cubic: cubic overshoots at the border of a saturated map and
    # the ringing shows up as spurious cool speckles along the image edge, which
    # reads as "trusted here" in exactly the region that is least trusted.
    resized = cv2.resize(
        normalised.astype(np.float32), (cols, rows), interpolation=cv2.INTER_LINEAR
    )
    heat = cv2.applyColorMap((resized * 255).astype(np.uint8), cv2.COLORMAP_TURBO)
    return cv2.cvtColor(heat, cv2.COLOR_BGR2RGB)


def overlay_heatmap(base: np.ndarray, heat: np.ndarray, alpha: float = 0.45) -> np.ndarray:
    """Lay a heatmap over an image without losing the terrain underneath."""
    import cv2

    return cv2.addWeighted(heat, alpha, to_rgb(base), 1.0 - alpha, 0.0)


__all__ = [
    "INLIER_COLOUR",
    "OUTLIER_COLOUR",
    "anaglyph",
    "blend",
    "checkerboard",
    "coverage_heatmap",
    "overlay_heatmap",
    "side_by_side_matches",
    "to_rgb",
    "warp_source",
]
