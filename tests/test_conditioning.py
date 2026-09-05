"""Stress tests for the conditioning metric, including the layouts that broke U.

Every case here is one the coverage/entropy score gets wrong. If a change makes
these pass under uniformity alone, the change has re-introduced the defect.
"""

from __future__ import annotations

import numpy as np
import pytest

from lunar_reg.eval.conditioning import (
    EXTRAPOLATION_GATE_PX,
    bootstrap_conditioning,
    conditioning_map,
    probe_grid,
)
from lunar_reg.eval.uniformity import compute_uniformity

SHAPE = (512, 512)
TRUE_H = np.array([[1.03, 0.012, 9.0], [-0.018, 0.995, -6.0], [1.2e-5, -8.0e-6, 1.0]])


def _apply(matrix, pts):
    pts = np.asarray(pts, dtype=np.float64).reshape(-1, 2)
    out = np.hstack([pts, np.ones((len(pts), 1))]) @ np.asarray(matrix).T
    return out[:, :2] / out[:, 2:3]


def _pair(src, noise=0.5, seed=7):
    rng = np.random.default_rng(seed)
    return np.asarray(src, dtype=np.float64), _apply(TRUE_H, src) + rng.normal(
        0, noise, (len(src), 2)
    )


def _even_grid(n=20):
    xs, ys = np.meshgrid(np.linspace(20, 492, n), np.linspace(20, 492, n))
    return np.column_stack([xs.ravel(), ys.ravel()])


def _one_corner(n=400, seed=7):
    return np.random.default_rng(seed).uniform(20, 160, (n, 2))


def _thin_diagonal(n=400, seed=7):
    rng = np.random.default_rng(seed)
    line = np.linspace(20, 492, n)
    return np.stack([line, line], -1) + rng.normal(0, 2, (n, 2))


def _border_only(n=400):
    per = n // 4
    edge = np.linspace(10, 502, per)
    return np.concatenate([
        np.stack([edge, np.full(per, 10.0)], -1),
        np.stack([edge, np.full(per, 502.0)], -1),
        np.stack([np.full(per, 10.0), edge], -1),
        np.stack([np.full(per, 502.0), edge], -1),
    ])


def _cell_centres():
    cells = np.stack(np.meshgrid(np.arange(8), np.arange(8)), -1).reshape(-1, 2)
    return cells * 64.0 + 32.0


def test_probe_grid_spans_the_image():
    probes = probe_grid(SHAPE, 5)
    assert probes.shape == (25, 2)
    assert probes[:, 0].min() == 0 and probes[:, 0].max() == pytest.approx(511)
    assert probes[:, 1].min() == 0 and probes[:, 1].max() == pytest.approx(511)


def test_even_grid_is_well_conditioned():
    metrics = bootstrap_conditioning(*_pair(_even_grid()), SHAPE)
    assert metrics.passes_gate
    assert metrics.p95_px < 1.0


@pytest.mark.parametrize("layout", [_one_corner(), _thin_diagonal()])
def test_pathological_clustering_is_rejected(layout):
    metrics = bootstrap_conditioning(*_pair(layout), SHAPE)
    assert not metrics.passes_gate
    assert metrics.p95_px > EXTRAPOLATION_GATE_PX
    assert "UNDER-CONSTRAINED" in str(metrics)


def test_border_layout_passes_where_uniformity_wrongly_fails():
    """The false alarm that motivated this module.

    Points around the frame edge constrain a homography extremely well -- their
    true worst-case error is the lowest of any layout tested -- yet the grid
    histogram sees mostly empty cells and fails them.
    """
    layout = _border_only()
    assert not compute_uniformity(layout, SHAPE).passes_gate
    assert bootstrap_conditioning(*_pair(layout), SHAPE).passes_gate


def test_sparse_lattice_is_penalised_where_uniformity_scores_perfect():
    """The miss that motivated this module.

    One point per cell of the metric's own 8x8 grid scores a flawless
    U = 1.000 with no diagnostic flag, while being several times less precise
    than a dense even grid. Conditioning must separate them.
    """
    lattice = _cell_centres()
    assert compute_uniformity(lattice, SHAPE).score == pytest.approx(1.0)

    sparse = bootstrap_conditioning(*_pair(lattice), SHAPE)
    dense = bootstrap_conditioning(*_pair(_even_grid()), SHAPE)
    assert sparse.p95_px > dense.p95_px


def test_cell_stuffing_cannot_game_the_metric():
    """Satisfying the grid does not by itself buy a good conditioning score.

    A matcher aware of the 8x8 grid could place points to maximise U. Doing so
    with everything crammed against one edge of each cell still leaves the fit
    poorly constrained, and the resampling estimate sees that where a histogram
    cannot.
    """
    cells = np.stack(np.meshgrid(np.arange(8), np.arange(8)), -1).reshape(-1, 2) * 64.0
    stuffed = np.repeat(cells, 6, axis=0) + np.tile(
        np.array([[1.0, 1.0], [1.5, 1.0], [2.0, 1.0], [1.0, 1.5], [1.5, 1.5], [2.0, 2.0]]),
        (64, 1),
    )
    assert compute_uniformity(stuffed, SHAPE).score == pytest.approx(1.0)
    # Every point sits within ~2 px of a cell corner, so the effective geometry
    # is the 64 corners, not 384 independent observations.
    assert bootstrap_conditioning(*_pair(stuffed), SHAPE).p95_px > bootstrap_conditioning(
        *_pair(_even_grid()), SHAPE
    ).p95_px


def test_result_is_reproducible():
    args = (*_pair(_even_grid()), SHAPE)
    assert bootstrap_conditioning(*args).p95_px == bootstrap_conditioning(*args).p95_px


def test_too_few_points_reports_infinity_not_a_number():
    src = np.array([[10.0, 10.0], [20.0, 20.0]])
    metrics = bootstrap_conditioning(src, _apply(TRUE_H, src), SHAPE)
    assert not np.isfinite(metrics.p95_px)
    assert not metrics.passes_gate


def test_mismatched_lengths_raise():
    with pytest.raises(ValueError, match="points"):
        bootstrap_conditioning(np.zeros((10, 2)), np.zeros((9, 2)), SHAPE)


def test_conditioning_map_is_worst_away_from_the_points():
    """A one-corner layout must light up on the opposite side of the frame."""
    layout = _one_corner()
    grid = conditioning_map(*_pair(layout), SHAPE, probe_n=8)
    assert grid.shape == (8, 8)
    # Points sit in the top-left; the bottom-right corner is the extrapolation.
    assert grid[-1, -1] > grid[0, 0]
