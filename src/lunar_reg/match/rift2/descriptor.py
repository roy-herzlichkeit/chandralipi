"""RIFT feature description: the 6x6 x N_o MIM histogram descriptor.

Clean-room implementation from RIFT (arXiv:1804.09493) section III-B-1 and
RIFT2 (arXiv:2303.00319) section II-B.

For each keypoint, take a ``J x J`` patch of the (recoded) MIM, weight it with a
Gaussian of standard deviation ``J/2``, split it into 6x6 sub-grids, build an
``N_o``-bin histogram of MIM values per sub-grid, concatenate, and normalise.
With the papers' ``N_o = 6`` that is a 6 x 6 x 6 = 216-dimensional vector.

The Gaussian weighting is not decoration -- it stops the descriptor changing
abruptly when the patch shifts by a pixel, which is what would otherwise make
the descriptor unstable under sub-pixel keypoint jitter.
"""

from __future__ import annotations

import logging

import numpy as np

from lunar_reg.match.rift2.mim import dominant_indices, recode_mim

logger = logging.getLogger(__name__)

#: Patch side in pixels. Paper-stated: RIFT section IV-B fixes ``J = 96``.
PATCH_SIZE = 96
#: Sub-grids per side. Paper-stated: "divide the local patch into 6x6 sub-grids".
N_GRIDS = 6


def _gaussian_weights(size: int) -> np.ndarray:
    """Gaussian window with sigma = size/2, per the paper."""
    coords = np.arange(size) - (size - 1) / 2.0
    sigma = size / 2.0
    line = np.exp(-(coords**2) / (2 * sigma**2))
    return np.outer(line, line)


def describe_patch(
    mim_patch: np.ndarray,
    n_orientations: int,
    n_grids: int = N_GRIDS,
    weights: np.ndarray | None = None,
) -> np.ndarray:
    """Build one descriptor from an already-recoded MIM patch.

    Returns an L2-normalised vector of length ``n_grids**2 * n_orientations``.
    """
    size = mim_patch.shape[0]
    if weights is None:
        weights = _gaussian_weights(size)

    descriptor = np.zeros((n_grids, n_grids, n_orientations), dtype=np.float32)
    edges = np.linspace(0, size, n_grids + 1).astype(int)

    for gy in range(n_grids):
        for gx in range(n_grids):
            cell = mim_patch[edges[gy]:edges[gy + 1], edges[gx]:edges[gx + 1]]
            cell_weights = weights[edges[gy]:edges[gy + 1], edges[gx]:edges[gx + 1]]
            # Weighted histogram over MIM index values (1..n_orientations).
            flat = cell.ravel() - 1
            valid = (flat >= 0) & (flat < n_orientations)
            if valid.any():
                descriptor[gy, gx] = np.bincount(
                    flat[valid], weights=cell_weights.ravel()[valid], minlength=n_orientations
                )[:n_orientations]

    vector = descriptor.ravel()
    norm = np.linalg.norm(vector)
    if norm > 0:
        vector = vector / norm
        # SIFT-style clip-and-renormalise: caps the influence of any single
        # dominant bin so one strong edge cannot swamp the descriptor.
        vector = np.clip(vector, 0, 0.2)
        renorm = np.linalg.norm(vector)
        if renorm > 0:
            vector = vector / renorm
    return vector.astype(np.float32)


def describe_keypoints(
    mim: np.ndarray,
    keypoints: np.ndarray,
    n_orientations: int,
    patch_size: int = PATCH_SIZE,
    n_grids: int = N_GRIDS,
    dominant_ratio: float = 0.8,
) -> tuple[np.ndarray, np.ndarray]:
    """Describe every keypoint, applying RIFT2's dominant-index recoding.

    A keypoint whose dominant index is ambiguous yields **two** descriptors, so
    the returned arrays are longer than ``keypoints``. Returns
    ``(points, descriptors)`` with one row of ``points`` per descriptor, so the
    two stay aligned.

    Keypoints too close to the border to fill a patch are dropped -- padding
    would fabricate MIM values and the descriptor would encode the padding.
    """
    mim = np.asarray(mim)
    rows, cols = mim.shape
    half = patch_size // 2
    weights = _gaussian_weights(patch_size)

    points: list[np.ndarray] = []
    descriptors: list[np.ndarray] = []

    for x, y in np.asarray(keypoints, dtype=float).reshape(-1, 2):
        cx, cy = int(round(x)), int(round(y))
        if cx - half < 0 or cy - half < 0 or cx + half > cols or cy + half > rows:
            continue

        patch = mim[cy - half:cy + half, cx - half:cx + half]
        if patch.shape != (patch_size, patch_size):
            continue

        for index in dominant_indices(patch, n_orientations, dominant_ratio):
            recoded = recode_mim(patch, index, n_orientations)
            descriptors.append(describe_patch(recoded, n_orientations, n_grids, weights))
            points.append(np.array([x, y]))

    if not descriptors:
        return np.empty((0, 2)), np.empty((0, n_grids * n_grids * n_orientations), np.float32)
    return np.vstack(points), np.vstack(descriptors)
