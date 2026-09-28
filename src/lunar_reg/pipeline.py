"""End-to-end registration of one pair, from images to a stored result.

The stages already existed separately -- preprocess, match, estimate, refine,
evaluate. What was missing was the thing that runs them in order, in one place,
and writes down what happened. Without it every experiment was a bespoke script
and nothing could be browsed afterwards.

Design
------
Failure is a *result*, not an exception. A pair that yields no correspondences,
or that RANSAC cannot fit, returns a :class:`RunOutcome` carrying the reason.
Batch runs therefore never abort partway, and the reason is retained so a run
over many pairs can report what fell out and why -- a count alone is not enough
to tell a data problem from a bug.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

import numpy as np

logger = logging.getLogger(__name__)


class RunStatus(str, Enum):
    """Why a pair did or did not register."""

    OK = "ok"
    #: The matcher returned too few correspondences to fit anything.
    TOO_FEW_MATCHES = "too_few_matches"
    #: Enough correspondences, but the robust fit did not converge.
    ESTIMATION_FAILED = "estimation_failed"
    #: RANSAC kept too few inliers for the result to mean anything.
    TOO_FEW_INLIERS = "too_few_inliers"
    #: The matcher itself raised.
    MATCHER_ERROR = "matcher_error"

    @property
    def is_failure(self) -> bool:
        return self is not RunStatus.OK


@dataclass
class RunOutcome:
    """One pair's outcome: a result, or a classified reason there is none."""

    pair_id: str
    status: RunStatus
    result: object | None = None
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status is RunStatus.OK


@dataclass
class PipelineConfig:
    """Knobs for one run. Defaults are the recommended chain."""

    matcher: str = "akaze"
    model: str = "homography"
    ransac_threshold_px: float = 3.0
    use_ecc: bool = True
    #: ``"none"``, ``"local_contrast"`` or ``"auto"``. When sun angles are
    #: supplied to :func:`register_pair` they choose this instead.
    ecc_prefilter: str = "none"
    min_matches: int = 8
    min_inliers: int = 8
    #: Bootstrap resamples for the conditioning metric; 0 disables it.
    n_bootstrap: int = 40
    gsd_m: float | None = None
    extra: dict = field(default_factory=dict)


#: Matcher names routed to the learned (torch) implementations rather than OpenCV.
LEARNED_MATCHERS: tuple[str, ...] = ("lightglue", "disk", "loftr")


def _build_matcher(name: str):
    """Classical matchers by default; LightGlue/LoFTR when named explicitly.

    Learned matchers import torch lazily, so classical-only runs stay light.
    """
    if name.lower().startswith(LEARNED_MATCHERS):
        from lunar_reg.match.learned import build_matcher

        return build_matcher(name)
    from lunar_reg.match.classical import build_classical

    return build_classical(name)


def register_pair(
    source: np.ndarray,
    reference: np.ndarray,
    pair_id: str,
    config: PipelineConfig | None = None,
    source_id: str = "",
    reference_id: str = "",
    source_sensor: str = "",
    reference_sensor: str = "",
    source_sun: tuple[float, float] | None = None,
    reference_sun: tuple[float, float] | None = None,
    synthetic: bool = False,
    notes: str = "",
) -> RunOutcome:
    """Register one pair and package everything it produced.

    ``source_sun`` / ``reference_sun`` are ``(azimuth_deg, elevation_deg)``. When
    both are given they select the ECC prefilter via
    :func:`~lunar_reg.align.refine.choose_ecc_prefilter`, which is the reliable
    signal for that choice -- see the measurements in that module.
    """
    from lunar_reg.align.estimate import estimate_transform
    from lunar_reg.align.refine import choose_ecc_prefilter, refine_full
    from lunar_reg.eval.conditioning import bootstrap_conditioning
    from lunar_reg.eval.metrics import compute_metrics
    from lunar_reg.eval.uniformity import compute_uniformity
    from lunar_reg.results import PairResult

    config = config or PipelineConfig()

    try:
        matches = _build_matcher(config.matcher).match(source, reference)
    except Exception as exc:  # noqa: BLE001 - a matcher failing is an outcome
        return RunOutcome(
            pair_id, RunStatus.MATCHER_ERROR, detail=f"{type(exc).__name__}: {exc}"
        )

    if len(matches) < config.min_matches:
        return RunOutcome(
            pair_id, RunStatus.TOO_FEW_MATCHES,
            detail=f"{config.matcher} returned {len(matches)} correspondence(s), "
                   f"below the minimum of {config.min_matches}",
        )

    try:
        transform, matches = estimate_transform(
            matches, model=config.model, threshold_px=config.ransac_threshold_px
        )
    except ValueError as exc:
        return RunOutcome(pair_id, RunStatus.ESTIMATION_FAILED, detail=str(exc))

    if transform.n_inliers < config.min_inliers:
        return RunOutcome(
            pair_id, RunStatus.TOO_FEW_INLIERS,
            detail=f"RANSAC kept {transform.n_inliers} of {len(matches)} matches",
        )

    prefilter = config.ecc_prefilter
    if source_sun is not None and reference_sun is not None:
        prefilter = choose_ecc_prefilter(source_sun, reference_sun)

    transform, matches, detail = refine_full(
        matches, source=source, reference=reference, model=config.model,
        threshold_px=config.ransac_threshold_px, use_ecc=config.use_ecc,
        ecc_kwargs={"prefilter": prefilter},
    )

    metrics = compute_metrics(matches, transform, gsd_m=config.gsd_m)
    uniformity = compute_uniformity(matches.inliers().src_pts, source.shape[:2])

    conditioning = {}
    if config.n_bootstrap:
        inliers = matches.inliers()
        conditioning = bootstrap_conditioning(
            inliers.src_pts, inliers.dst_pts, source.shape[:2],
            model=config.model, n_bootstrap=config.n_bootstrap,
        ).as_dict()

    result = PairResult(
        pair_id=pair_id,
        source_id=source_id or pair_id,
        reference_id=reference_id or pair_id,
        source_sensor=source_sensor,
        reference_sensor=reference_sensor,
        matcher=config.matcher,
        src_pts=matches.src_pts,
        dst_pts=matches.dst_pts,
        inlier_mask=matches.inlier_mask,
        transform=transform.matrix,
        metrics=metrics.as_dict(),
        uniformity=uniformity.as_dict(),
        conditioning=conditioning,
        source_image=source,
        reference_image=reference,
        synthetic=synthetic,
        notes=notes,
        extra={
            **config.extra,
            "ecc_prefilter": prefilter,
            "refine_stages": "+".join(detail.get("stages", [])),
            "ecc_cc": detail.get("ecc_cc"),
            "source_sun_azimuth": None if source_sun is None else source_sun[0],
            "source_sun_elevation": None if source_sun is None else source_sun[1],
            "reference_sun_azimuth": None if reference_sun is None else reference_sun[0],
            "reference_sun_elevation": None if reference_sun is None else reference_sun[1],
        },
    )
    return RunOutcome(pair_id, RunStatus.OK, result=result)


@dataclass
class BatchReport:
    """What a batch run produced, including what it could not."""

    outcomes: list = field(default_factory=list)

    @property
    def results(self) -> list:
        return [o.result for o in self.outcomes if o.ok]

    @property
    def failures(self) -> list:
        return [o for o in self.outcomes if not o.ok]

    def report(self) -> str:
        """Counts per outcome plus one concrete sample of each failure.

        Printed on every run, not only when something goes wrong: a count says
        how widespread a problem is, a sample says what it looks like, and
        diagnosing it usually needs both.
        """
        lines = [f"pipeline: {len(self.results)} of {len(self.outcomes)} pair(s) registered"]
        counts: dict[str, list] = {}
        for outcome in self.failures:
            counts.setdefault(outcome.status.value, []).append(outcome)
        for status, group in sorted(counts.items()):
            sample = group[0]
            lines.append(f"  {status}: {len(group)}  e.g. {sample.pair_id}: {sample.detail}")
        if not counts:
            lines.append("  no failures")
        return "\n".join(lines)


def run_batch(pairs, config: PipelineConfig | None = None, root=None) -> BatchReport:
    """Register many pairs and optionally persist them.

    ``pairs`` is an iterable of dicts accepted as keyword arguments by
    :func:`register_pair`.
    """
    from lunar_reg.results import save_results

    report = BatchReport()
    for spec in pairs:
        outcome = register_pair(config=config, **spec)
        report.outcomes.append(outcome)
        if not outcome.ok:
            logger.warning("%s: %s (%s)", outcome.pair_id, outcome.status.value, outcome.detail)

    if root is not None and report.results:
        save_results(report.results, root)
    return report


__all__ = [
    "BatchReport",
    "PipelineConfig",
    "RunOutcome",
    "RunStatus",
    "register_pair",
    "run_batch",
]
