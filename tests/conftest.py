"""Shared fixtures.

Tests here are deliberately data-free: they exercise geometry, budgeting, and
metric maths on synthetic arrays so the suite runs on any machine, with or
without a GPU or PDS4 products. Tests needing either are marked ``gpu``/``data``.
"""

from __future__ import annotations

import numpy as np
import pytest


@pytest.fixture
def rng():
    return np.random.default_rng(20260904)


@pytest.fixture
def synthetic_pair(rng):
    """A textured image and a known-homography warp of it.

    Returns ``(source, reference, homography)``. Ground truth is exact, so a
    matcher's residuals against this pair are a clean measure of its own error.
    """
    import cv2

    h = w = 512
    src = rng.integers(0, 255, (h, w), dtype=np.uint8)
    src = cv2.GaussianBlur(src, (7, 7), 2.0)
    # Add structure a detector can actually latch onto.
    for _ in range(40):
        cx, cy = rng.integers(40, w - 40), rng.integers(40, h - 40)
        radius, shade = int(rng.integers(8, 25)), int(rng.integers(60, 220))
        cv2.circle(src, (int(cx), int(cy)), radius, shade, -1)

    matrix = np.array([[1.02, 0.01, 12.0], [-0.015, 0.99, -7.0], [0.0, 0.0, 1.0]])
    ref = cv2.warpPerspective(src, matrix, (w, h), flags=cv2.INTER_CUBIC)
    return src, ref, matrix
