"""Spatial-uniformity metric for correspondence sets.

The problem statement requires match points "maintaining uniform distribution
across the images" but names no metric, so this module proposes one.

Why a uniformity metric is needed at all
----------------------------------------
Because RMSE cannot see the failure. Measured on this project's synthetic
homography benchmark -- six point layouts, all with **400 points and identical
0.5 px noise**, so only the spatial distribution differs:

===================  ==========  ================  ===============
layout               fit RMSE    error at probes   worst-case
===================  ==========  ================  ===============
grid (even)          0.698       0.049             0.114
uniform random       0.699       0.071             0.142
one quadrant         0.701       0.309             0.768
two clusters         0.705       0.390             1.092
diagonal band        0.717       0.999             2.393
tight blob           0.724       1.653             5.861
===================  ==========  ================  ===============

Fit RMSE spans 0.698-0.724 -- essentially constant. True error away from the
matched points spans 0.114-5.861 px, a **51x range**. A clustered solution
reports sub-pixel RMSE while being nearly six pixels wrong elsewhere in the same
image. Since the problem statement asks for sub-pixel accuracy *across* the
image, RMSE alone cannot substantiate the claim; something has to measure
whether the correspondences constrain the transform everywhere.

The proposed metric
-------------------
Three complementary numbers, and one headline score.

**coverage** ``C`` -- fraction of ``g x g`` grid cells containing at least one
point. Directly measures regional absence, which is what forces the transform to
extrapolate.

**normalised entropy** ``H`` -- Shannon entropy of the per-cell counts divided by
``log(g^2)``, so 1.0 is a perfectly even spread. Measures density skew among the
cells that *are* occupied.

**headline score** ``U = sqrt(C * H)`` -- geometric mean, so a near-zero in
either component drags the score down instead of being averaged away.

**Clark-Evans index** ``R`` -- mean nearest-neighbour distance divided by the
value expected under complete spatial randomness. Grid-free. ``R < 1``
clustered, ``R ~ 1`` random, ``R > 1`` dispersed.

Why all four, and not fewer
---------------------------
*Coverage alone fails*: 64 occupied cells with 5000 points in one and 1 in each
of the rest gives ``C = 1.0``, which looks perfect. ``H = 0.03`` catches it.

*Entropy alone fails*: four cells at 25% each and 60 empty gives ``H = 0.33``,
which is unalarming, while ``C = 0.06`` is emphatic. The two respond sharply to
different failures, which is why the score multiplies them.

*Both grid metrics are blind to arrangement inside a cell.* Measured here: 512
points arranged as 64 tight blobs, one per cell, score ``C = 1.00``, ``H = 1.00``,
``U = 1.00`` -- indistinguishable from an ideal spread -- while Clark-Evans gives
``R = 0.101``, correctly reporting severe clustering. ``R`` is the check the grid
cannot perform, so it is reported alongside rather than folded into ``U``.

``R`` is deliberately **not** gated on. Real detectors always clump at fine scale
-- inlier sets from SIFT/ASIFT/AKAZE/RIFT2 measured 0.63/0.29/0.32/0.24 here,
all with healthy coverage -- so any threshold strict enough to catch the blob
case would reject every real result. The actionable signal is *disagreement*: a
high ``U`` with a low ``R``, exposed as
:attr:`UniformityMetrics.grid_contradicted_by_neighbours`.

*Uniformity is scale-dependent.* A set even at 4x4 can be clustered at 16x16, so
:func:`uniformity_profile` reports across several grid sizes.

Choice of default grid
----------------------
``g = 8`` gives 64 cells, eight times the 8 degrees of freedom of a homography.
The point of the metric is transform conditioning, so the cell count should
comfortably exceed the parameter count being constrained; much finer and
per-cell counts become sampling noise rather than signal.

Validation
----------
``U`` ranks the six layouts above in the same order as their worst-case error,
Spearman ``-0.83``. That is the evidence for using it as a gate.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

#: Default grid resolution. See "Choice of default grid" above.
DEFAULT_GRID = 8

#: Grid sizes used by :func:`uniformity_profile` for the multi-scale view.
PROFILE_GRIDS = (4, 8, 16)

#: Below this, a correspondence set is too clustered to support a whole-image
#: sub-pixel claim. Calibrated against the benchmark: the layouts scoring under
#: it had worst-case errors of 0.77 px and up, versus 0.14 px for those above.
UNIFORMITY_GATE = 0.7

#: Clark-Evans value below which fine-scale clumping is worth a second look.
#: This is a **diagnostic, not a gate** -- see :attr:`UniformityMetrics.is_clustered`.
#: Real detector output routinely sits below it, so failing it is not a defect.
CLUSTERED_R = 0.25


@dataclass
class UniformityMetrics:
    """How evenly correspondences are spread across the source image."""

    coverage: float
    entropy: float
    cv: float
    clark_evans: float
    grid: int
    n_points: int
    occupied_cells: int
    total_cells: int

    @property
    def score(self) -> float:
        """Headline ``U = sqrt(coverage * entropy)``, in ``[0, 1]``.

        Geometric rather than arithmetic so a near-zero in either component
        drags the score down instead of being averaged away.
        """
        return float(np.sqrt(max(self.coverage, 0.0) * max(self.entropy, 0.0)))

    @property
    def is_clustered(self) -> bool:
        """Diagnostic flag for fine-scale clumping. **Not** a pass/fail criterion.

        Real feature detectors always clump at fine scale, because keypoints
        concentrate on textured structure -- measured on this project's synthetic
        scene, inlier sets from SIFT, ASIFT, AKAZE and RIFT2 gave Clark-Evans
        values of 0.63, 0.29, 0.32 and 0.24 respectively, all with healthy
        coverage. So a low ``R`` on its own is normal, and gating on it would
        reject every real result.

        Read it *against* the grid score instead. The combination that warrants
        investigation is a high :attr:`score` with a low ``R``: the grid claims an
        excellent spread while the nearest-neighbour statistic says the points
        are tightly clumped inside their cells. That is the 64-tight-blobs case
        (``score`` 1.00, ``R`` 0.20), which the grid metrics genuinely cannot see.
        """
        return bool(np.isfinite(self.clark_evans)) and self.clark_evans < CLUSTERED_R

    @property
    def grid_contradicted_by_neighbours(self) -> bool:
        """Grid metrics claim a near-perfect spread but Clark-Evans disagrees.

        The specific blind spot worth acting on. Unlike :attr:`is_clustered`
        alone, this cannot fire on ordinary detector output, because real
        detectors do not reach a near-perfect grid score while clumping tightly.
        """
        return self.score > 0.95 and self.is_clustered

    @property
    def passes_gate(self) -> bool:
        """Whether this set is spread well enough to support a whole-image claim.

        Uses the grid score alone, because that is the part validated against
        extrapolation error (Spearman -0.83 with worst-case probe error).
        Clark-Evans is reported alongside but deliberately not gated on -- it has
        no such validation, and real detector output would fail any threshold
        strict enough to catch the blind-spot case.
        """
        return self.score >= UNIFORMITY_GATE

    def as_dict(self) -> dict:
        return {
            **asdict(self),
            "score": self.score,
            "is_clustered": self.is_clustered,
            "grid_contradicted_by_neighbours": self.grid_contradicted_by_neighbours,
            "passes_gate": self.passes_gate,
        }

    def __str__(self) -> str:
        verdict = "ok" if self.passes_gate else "POORLY SPREAD"
        if self.grid_contradicted_by_neighbours:
            verdict = "GRID/NN DISAGREE"
        return (
            f"U={self.score:.3f} (coverage={self.coverage:.3f} entropy={self.entropy:.3f}) "
            f"R={self.clark_evans:.3f} n={self.n_points} grid={self.grid} -> {verdict}"
        )


def cell_counts(pts: np.ndarray, shape: tuple[int, int], grid: int = DEFAULT_GRID) -> np.ndarray:
    """Histogram ``(N, 2)`` ``(x, y)`` points into a ``grid x grid`` cell grid."""
    h, w = shape
    pts = np.asarray(pts, dtype=np.float64).reshape(-1, 2)
    counts = np.zeros((grid, grid), dtype=np.int64)
    if len(pts) == 0:
        return counts
    col = np.clip((pts[:, 0] / max(w, 1) * grid).astype(int), 0, grid - 1)
    row = np.clip((pts[:, 1] / max(h, 1) * grid).astype(int), 0, grid - 1)
    np.add.at(counts, (row, col), 1)
    return counts


def clark_evans_index(pts: np.ndarray, shape: tuple[int, int]) -> float:
    """Mean nearest-neighbour distance over the value expected under randomness.

    ``R < 1`` clustered, ``R ~ 1`` random, ``R > 1`` dispersed. Grid-free, so it
    catches within-cell clustering that :func:`cell_counts` cannot see.

    Caveat: the expectation assumes an unbounded region, so points near the image
    border have their true nearest neighbour cut off and ``R`` is biased slightly
    low. The bias is small for the point counts here and identical across
    compared sets, so it does not affect ranking -- but do not read a value just
    under 1.0 as evidence of clustering on its own.
    """
    pts = np.asarray(pts, dtype=np.float64).reshape(-1, 2)
    if len(pts) < 2:
        return float("nan")

    from scipy.spatial import cKDTree

    distances, _ = cKDTree(pts).query(pts, k=2)
    observed = float(distances[:, 1].mean())
    h, w = shape
    expected = 0.5 * np.sqrt((h * w) / len(pts))
    return observed / expected if expected > 0 else float("nan")


def compute_uniformity(
    pts: np.ndarray, shape: tuple[int, int], grid: int = DEFAULT_GRID
) -> UniformityMetrics:
    """Measure how evenly ``pts`` cover an image of the given ``shape``."""
    counts = cell_counts(pts, shape, grid)
    total = int(counts.sum())
    n_cells = grid * grid
    occupied = int((counts > 0).sum())

    if total == 0:
        return UniformityMetrics(0.0, 0.0, float("inf"), float("nan"), grid, 0, 0, n_cells)

    p = counts.ravel() / total
    nonzero = p[p > 0]
    entropy = float(-(nonzero * np.log(nonzero)).sum() / np.log(n_cells)) if n_cells > 1 else 1.0
    mean = counts.mean()
    cv = float(counts.std() / mean) if mean > 0 else float("inf")

    return UniformityMetrics(
        coverage=occupied / n_cells,
        entropy=entropy,
        cv=cv,
        clark_evans=clark_evans_index(pts, shape),
        grid=grid,
        n_points=total,
        occupied_cells=occupied,
        total_cells=n_cells,
    )


def uniformity_profile(
    pts: np.ndarray, shape: tuple[int, int], grids=PROFILE_GRIDS
) -> dict[int, UniformityMetrics]:
    """Uniformity at several grid scales.

    A set even at 4x4 may be clustered at 16x16. Reporting one grid size hides
    that; the profile makes the scale dependence visible.
    """
    return {g: compute_uniformity(pts, shape, g) for g in grids}


def enforce_uniformity(
    pts: np.ndarray,
    shape: tuple[int, int],
    grid: int = DEFAULT_GRID,
    max_per_cell: int = 32,
    scores: np.ndarray | None = None,
) -> np.ndarray:
    """Indices of a spatially thinned subset, capped at ``max_per_cell`` per cell.

    A post-hoc corrective that improves the count distribution but **cannot
    improve coverage** -- it can only remove points, never invent them in an
    empty cell. Prefer per-tile capping in
    :class:`~lunar_reg.match.tiled.TiledMatcher`, and treat a low coverage score
    as a signal to change matching, not to thin harder.
    """
    pts = np.asarray(pts, dtype=np.float64).reshape(-1, 2)
    if len(pts) == 0:
        return np.empty(0, dtype=int)

    h, w = shape
    col = np.clip((pts[:, 0] / max(w, 1) * grid).astype(int), 0, grid - 1)
    row = np.clip((pts[:, 1] / max(h, 1) * grid).astype(int), 0, grid - 1)
    cell = row * grid + col

    keep: list[int] = []
    for c in np.unique(cell):
        idx = np.flatnonzero(cell == c)
        if len(idx) > max_per_cell:
            order = np.argsort(scores[idx])[::-1] if scores is not None else np.arange(len(idx))
            idx = idx[order[:max_per_cell]]
        keep.extend(idx.tolist())
    return np.sort(np.array(keep, dtype=int))
