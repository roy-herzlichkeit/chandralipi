"""Diagnostic figures.

Two audiences: debugging a failing pair, and the submission deck. Everything
renders to a Matplotlib figure and writes to file rather than calling ``show``,
so the same functions work headless in a batch run.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from lunar_reg.eval.uniformity import DEFAULT_GRID, cell_counts
from lunar_reg.match.base import MatchResult

logger = logging.getLogger(__name__)


def _prep(image: np.ndarray) -> np.ndarray:
    from lunar_reg.preprocess.radiometric import to_uint8

    return image if image.dtype == np.uint8 else to_uint8(image)


def plot_matches(
    source: np.ndarray,
    reference: np.ndarray,
    result: MatchResult,
    max_lines: int = 200,
    inliers_only: bool = True,
    output_path: str | Path | None = None,
):
    """Side-by-side images with correspondence lines drawn between them."""
    import matplotlib.pyplot as plt

    subset = result.inliers() if (inliers_only and result.inlier_mask is not None) else result
    src, dst = _prep(source), _prep(reference)

    fig, ax = plt.subplots(figsize=(14, 7))
    h = max(src.shape[0], dst.shape[0])
    canvas = np.zeros((h, src.shape[1] + dst.shape[1]), dtype=np.uint8)
    canvas[: src.shape[0], : src.shape[1]] = src
    canvas[: dst.shape[0], src.shape[1] :] = dst
    ax.imshow(canvas, cmap="gray")

    n = min(max_lines, len(subset))
    if n:
        idx = np.linspace(0, len(subset) - 1, n).astype(int)
        for i in idx:
            x0, y0 = subset.src_pts[i]
            x1, y1 = subset.dst_pts[i]
            ax.plot([x0, x1 + src.shape[1]], [y0, y1], linewidth=0.5, alpha=0.6)

    ax.set_title(f"{result.matcher}: {len(subset)} matches ({n} drawn)")
    ax.axis("off")
    return _finish(fig, output_path)


def plot_uniformity(
    result: MatchResult,
    shape: tuple[int, int],
    grid: int = DEFAULT_GRID,
    output_path: str | Path | None = None,
):
    """Heatmap of match density per grid cell.

    The visual counterpart to
    :func:`~lunar_reg.eval.uniformity.compute_uniformity`: clustering shows up
    as a few bright cells against a dark field, which is far more persuasive in
    a report than the scalar alone.
    """
    import matplotlib.pyplot as plt

    counts = cell_counts(result.src_pts, shape, grid)
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(counts, cmap="viridis", interpolation="nearest")
    fig.colorbar(im, ax=ax, label="matches per cell")
    ax.set_title(f"Match distribution ({grid}x{grid} grid, n={counts.sum()})")
    return _finish(fig, output_path)


def plot_residuals(res: np.ndarray, output_path: str | Path | None = None):
    """Histogram of reprojection residuals with the 1-pixel line marked."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 4))
    if res.size:
        ax.hist(res, bins=50)
        ax.axvline(1.0, linestyle="--", color="red", label="1 px (sub-pixel threshold)")
        ax.axvline(float(np.percentile(res, 95)), linestyle=":", color="orange", label="p95")
        ax.legend()
    ax.set_xlabel("reprojection error (px)")
    ax.set_ylabel("count")
    ax.set_title("Residual distribution")
    return _finish(fig, output_path)


def plot_overlay(
    warped: np.ndarray, reference: np.ndarray, output_path: str | Path | None = None
):
    """False-colour overlay: source in red, reference in green.

    Correctly registered terrain reads as yellow-grey; any residual
    misregistration shows as coloured fringing along crater rims.
    """
    import matplotlib.pyplot as plt

    a, b = _prep(warped), _prep(reference)
    h = min(a.shape[0], b.shape[0])
    w = min(a.shape[1], b.shape[1])
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    rgb[..., 0] = a[:h, :w]
    rgb[..., 1] = b[:h, :w]

    fig, ax = plt.subplots(figsize=(10, 10))
    ax.imshow(rgb)
    ax.set_title("Registration overlay (red=source, green=reference)")
    ax.axis("off")
    return _finish(fig, output_path)


def _finish(fig, output_path):
    if output_path is not None:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        logger.info("wrote %s", output_path)
    return fig
