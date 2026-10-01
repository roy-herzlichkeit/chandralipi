"""Stage-by-stage attribution of registration error.

The problem statement asks for sub-pixel accuracy. When a pipeline misses that
target, "RMSE is 2.4 px" does not say what to fix. This module splits the error
into the stages that can each be changed independently:

  preprocessing  -> does the chain help or hurt the correspondences?
  matcher        -> how far is each correspondence from the true one?
  RANSAC         -> does the fit inherit that error, amplify it, or average it out?
  refinement     -> does ECC recover accuracy or drift away from truth?

Attribution needs a known transform, which real Chandrayaan-2 pairs do not have.
So this runs on :mod:`lunar_reg.eval.scenes`, where the transform is exact.
**Every number produced here is synthetic**, and conclusions transfer only as
far as the shading model does. What does transfer is the *ranking* of stages,
provided the failure mode is illumination-driven -- which is the case the scenes
are built to reproduce.

The decomposition
-----------------
Final error is the transform's, not any individual point's, so it is measured as
the RMS displacement the estimated transform induces against the true one over
the image grid. Attribution then uses an oracle:

``distribution``  Fit a transform -- the pipeline's own ``model``, by least
                  squares -- to the inlier source points paired with their
                  *true* reference positions. Correspondence error is removed,
                  so whatever remains is caused purely by where the points sit
                  -- a matcher that clusters its matches in one corner fits a
                  transform that is badly conditioned away from that corner.
``correspondence`` Fit to the same source points paired with the *matched*
                  positions. The increase over ``distribution`` is what the
                  matcher's localisation error costs after RANSAC has averaged
                  over it.

These are not additive in general; RANSAC can suppress correspondence noise, and
the numbers show whether it did. :attr:`ErrorBudget.shares` treats them as
independent in quadrature -- ``correspondence = sqrt(fit**2 - distribution**2)``
-- which is the decomposition :attr:`ErrorBudget.dominant` compares.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger(__name__)


def _apply(matrix: np.ndarray, pts: np.ndarray) -> np.ndarray:
    pts = np.asarray(pts, dtype=np.float64).reshape(-1, 2)
    homogeneous = np.hstack([pts, np.ones((len(pts), 1))])
    if matrix.shape == (3, 3):
        out = homogeneous @ np.asarray(matrix, dtype=np.float64).T
        return out[:, :2] / out[:, 2:3]
    return homogeneous @ np.asarray(matrix, dtype=np.float64).T


def transform_rms_px(
    estimated: np.ndarray, truth: np.ndarray, shape: tuple[int, int], step: int = 16
) -> float:
    """RMS disagreement between two transforms, in reference pixels.

    Comparing matrices entry by entry is meaningless -- a homography is only
    defined up to scale and its entries have wildly different units. Comparing
    where they *send points* is the quantity that matters, and sampling a grid
    over the whole image weights the comparison across the frame rather than
    wherever the matches happened to be.
    """
    rows, cols = shape
    yy, xx = np.mgrid[0:rows:step, 0:cols:step]
    grid = np.column_stack([xx.ravel(), yy.ravel()]).astype(np.float64)
    delta = _apply(estimated, grid) - _apply(truth, grid)
    return float(np.sqrt(np.mean(np.sum(delta**2, axis=1))))


@dataclass
class StageError:
    """One row of the budget."""

    stage: str
    rmse_px: float | None
    n_points: int | None = None
    note: str = ""

    def __str__(self) -> str:
        value = "  n/a  " if self.rmse_px is None else f"{self.rmse_px:7.3f}"
        count = "" if self.n_points is None else f"  n={self.n_points:<5d}"
        return f"  {self.stage:<34} {value} px{count}  {self.note}"


@dataclass
class ErrorBudget:
    """Attribution for one pair and one matcher."""

    matcher: str
    shape: tuple[int, int]
    stages: list[StageError] = field(default_factory=list)
    failed: str | None = None

    def add(
        self, stage: str, rmse_px: float | None, n_points: int | None = None, note: str = ""
    ) -> None:
        self.stages.append(StageError(stage, rmse_px, n_points, note))

    def get(self, stage: str) -> float | None:
        for entry in self.stages:
            if entry.stage == stage:
                return entry.rmse_px
        return None

    @property
    def shares(self) -> dict[str, float | None]:
        """The fit error split into its two causes, in pixels.

        ``distribution_px`` is the oracle fit (points where they are, true
        targets); ``correspondence_px = sqrt(fit**2 - distribution**2)`` is what
        the matcher's localisation error adds on top, assuming the two are
        independent. ``None`` when either stage is missing.
        """
        dist = self.get("transform: distribution only")
        fit = self.get("transform: RANSAC fit")
        if dist is None or fit is None:
            return {"distribution_px": dist, "correspondence_px": None}
        return {"distribution_px": dist, "correspondence_px": math.sqrt(max(fit**2 - dist**2, 0.0))}

    @property
    def dominant(self) -> str | None:
        """Which cause contributes most, or ``None`` when it is not separable.

        Compares the two :attr:`shares`. Returns ``None`` rather than guessing
        when the larger is within 25% of the smaller (the not-resolved band) --
        picking one on a coin-flip margin and then "fixing" it is worse than
        reporting that the experiment did not resolve it.
        """
        dist = self.get("transform: distribution only")
        fit = self.get("transform: RANSAC fit")
        if dist is None or fit is None or fit <= 0:
            return None
        corr = math.sqrt(max(fit**2 - dist**2, 0.0))
        if corr == 0 and dist == 0:
            return None
        larger, smaller = max(dist, corr), min(dist, corr)
        if smaller > 0 and larger / smaller <= 1.25:
            return None
        return "point distribution" if dist > corr else "correspondence error"

    def report(self) -> str:
        lines = [f"error budget: {self.matcher} on {self.shape[0]}x{self.shape[1]}"]
        if self.failed:
            lines.append(f"  FAILED: {self.failed}")
            return "\n".join(lines)
        lines += [str(s) for s in self.stages]

        shares = self.shares

        def px(value: float | None) -> str:
            return "n/a" if value is None else f"{value:.3f} px"

        lines.append(
            f"  shares: distribution {px(shares['distribution_px'])}, "
            f"correspondence {px(shares['correspondence_px'])} (in quadrature)"
        )
        dominant = self.dominant
        if dominant is None:
            lines.append(
                "  dominant stage: NOT RESOLVED -- distribution and correspondence "
                "shares are within 25% of each other (or a stage is missing)"
            )
        else:
            lines.append(f"  dominant stage: {dominant}")
        return "\n".join(lines)


def attribute_error(
    source: np.ndarray,
    reference: np.ndarray,
    truth: np.ndarray,
    matcher_name: str = "sift",
    model: str = "homography",
    threshold_px: float = 3.0,
    use_ecc: bool = True,
) -> ErrorBudget:
    """Run one pair through the pipeline, measuring error at every stage."""
    from lunar_reg.align.estimate import _MIN_POINTS, estimate_transform
    from lunar_reg.align.refine import refine_full
    from lunar_reg.eval.conditioning import fit_lsq
    from lunar_reg.match.classical import build_classical

    budget = ErrorBudget(matcher=matcher_name, shape=source.shape[:2])

    try:
        result = build_classical(matcher_name).match(source, reference)
    except Exception as exc:  # noqa: BLE001 - a matcher failing is a result here
        budget.failed = f"matcher raised: {type(exc).__name__}: {exc}"
        return budget

    if len(result) < 8:
        budget.failed = f"only {len(result)} correspondence(s); nothing to attribute"
        return budget

    # --- correspondence error, before any robust fitting -------------------
    predicted = _apply(truth, result.src_pts)
    raw_errors = np.linalg.norm(predicted - result.dst_pts, axis=1)
    budget.add(
        "matches: raw (pre-RANSAC)",
        float(np.sqrt(np.mean(raw_errors**2))),
        len(result),
        f"median {np.median(raw_errors):.2f} px",
    )

    try:
        transform, result = estimate_transform(result, model=model, threshold_px=threshold_px)
    except ValueError as exc:
        budget.failed = f"estimation failed: {exc}"
        return budget

    mask = result.inlier_mask
    if mask is None or mask.sum() < 4:
        budget.failed = f"RANSAC kept {0 if mask is None else int(mask.sum())} inlier(s)"
        return budget

    inlier_errors = raw_errors[mask]
    budget.add(
        "matches: RANSAC inliers",
        float(np.sqrt(np.mean(inlier_errors**2))),
        int(mask.sum()),
        f"ratio {mask.mean():.2f}; RANSAC discarded {100 * (1 - mask.mean()):.0f}% of matches",
    )

    # --- oracle: same points, true targets ---------------------------------
    # Isolates what the point *distribution* alone costs, fitted with the same
    # model the pipeline uses so the comparison with the RANSAC fit is fair.
    src_in = result.src_pts[mask]
    true_dst = _apply(truth, src_in)
    oracle = fit_lsq(src_in, true_dst, model) if len(src_in) >= _MIN_POINTS[model] else None
    budget.add(
        "transform: distribution only",
        transform_rms_px(oracle, truth, source.shape[:2]) if oracle is not None else None,
        int(mask.sum()),
        f"oracle fit: {model} least squares",
    )

    budget.add(
        "transform: RANSAC fit",
        transform_rms_px(transform.matrix, truth, source.shape[:2]),
        transform.n_inliers,
        "the pipeline's actual output before refinement",
    )

    # --- refinement --------------------------------------------------------
    refined, result, detail = refine_full(
        result,
        source=source,
        reference=reference,
        model=model,
        threshold_px=threshold_px,
        use_ecc=use_ecc,
    )
    note = "+".join(detail.get("stages", [])) or "no stage ran"
    if detail.get("ecc_cc") is not None:
        note += f", cc={detail['ecc_cc']:.3f}"
    elif detail.get("ecc_status"):
        note += f", ecc {detail['ecc_status']}"
    budget.add(
        "transform: after refinement",
        transform_rms_px(refined.matrix, truth, source.shape[:2]),
        refined.n_inliers,
        note,
    )
    return budget


def preprocessing_sweep(
    source: np.ndarray,
    reference: np.ndarray,
    truth: np.ndarray,
    matcher_name: str = "sift",
    configs: dict[str, dict] | None = None,
) -> dict[str, ErrorBudget]:
    """Attribute error under several preprocessing chains.

    Preprocessing is the one stage that cannot be measured in isolation -- it
    changes the images the matcher sees, so its contribution is only visible as
    a difference between whole-pipeline runs. Hence a sweep rather than a row in
    the budget.

    Steps are restricted to radiometric ones. A geometric step would move the
    pixels the truth homography is defined against, and comparing the result to
    an unchanged ``truth`` would silently measure the resampling instead of the
    matcher.
    """
    from lunar_reg.preprocess.radiometric import (
        apply_clahe,
        match_histogram,
        normalize_intensity,
        to_uint8,
    )
    from lunar_reg.preprocess.shadow import normalize_shadows

    def _identity(image, _other):
        return image

    def _clahe(image, _other):
        return apply_clahe(image)

    def _normalize(image, _other):
        # normalize_intensity is zero-mean/unit-variance: stretch it, never * 255.
        return to_uint8(normalize_intensity(image))

    def _shadow(image, _other):
        return to_uint8(normalize_shadows(image))

    def _hist(image, other):
        return match_histogram(image, other)

    def _shadow_clahe(image, other):
        return apply_clahe(_shadow(image, other))

    chains = configs or {
        "none": _identity,
        "clahe": _clahe,
        "normalize": _normalize,
        "shadow(gamma)": _shadow,
        "histogram-match": _hist,
        "shadow+clahe": _shadow_clahe,
    }

    budgets: dict[str, ErrorBudget] = {}
    for name, fn in chains.items():
        try:
            prepared_src = fn(source, reference)
            prepared_ref = fn(reference, source)
        except Exception as exc:  # noqa: BLE001
            budget = ErrorBudget(matcher=matcher_name, shape=source.shape[:2])
            budget.failed = f"preprocessing raised: {type(exc).__name__}: {exc}"
            budgets[name] = budget
            continue
        budgets[name] = attribute_error(
            prepared_src, prepared_ref, truth, matcher_name=matcher_name
        )
    return budgets


def format_sweep(budgets: dict[str, ErrorBudget]) -> str:
    """Compact table across preprocessing chains."""
    lines = [
        f"{'preprocessing':<18} {'raw':>8} {'inliers':>8} {'distrib':>8} "
        f"{'ransac':>8} {'refined':>8} {'n_in':>6}",
        "-" * 72,
    ]
    for name, budget in budgets.items():
        if budget.failed:
            lines.append(f"{name:<18} FAILED: {budget.failed[:48]}")
            continue

        def cell(stage: str, b: ErrorBudget = budget) -> str:
            value = b.get(stage)
            return "     --" if value is None else f"{value:8.3f}"

        n_in = budget.stages[1].n_points if len(budget.stages) > 1 else None
        lines.append(
            f"{name:<18} {cell('matches: raw (pre-RANSAC)')} "
            f"{cell('matches: RANSAC inliers')} {cell('transform: distribution only')} "
            f"{cell('transform: RANSAC fit')} {cell('transform: after refinement')} "
            f"{n_in if n_in is not None else '--':>6}"
        )
    return "\n".join(lines)


__all__ = [
    "ErrorBudget",
    "StageError",
    "attribute_error",
    "format_sweep",
    "preprocessing_sweep",
    "transform_rms_px",
]
