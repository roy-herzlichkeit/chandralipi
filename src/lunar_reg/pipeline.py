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
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

import numpy as np

from lunar_reg.provenance import ValueSource

if TYPE_CHECKING:
    from lunar_reg.results import PairResult, StoreReport

logger = logging.getLogger(__name__)


class RunStatus(str, Enum):
    """Why a pair did or did not register."""

    OK = "ok"
    #: The matcher returned too few correspondences to fit anything.
    TOO_FEW_MATCHES = "too_few_matches"
    #: Enough correspondences, but the robust fit did not converge.
    ESTIMATION_FAILED = "estimation_failed"
    #: RANSAC (or the refit after it) kept too few inliers to mean anything.
    TOO_FEW_INLIERS = "too_few_inliers"
    #: The matcher itself raised.
    MATCHER_ERROR = "matcher_error"
    #: The refit or ECC stage raised.
    REFINEMENT_FAILED = "refinement_failed"
    #: Metrics, uniformity or conditioning raised.
    EVAL_FAILED = "eval_failed"
    #: Preprocessing raised (first produced by P1.10).
    PREPROCESS_FAILED = "preprocess_failed"
    #: Out of device memory (first produced by P2.05).
    OOM = "oom"

    @property
    def is_failure(self) -> bool:
        return self is not RunStatus.OK


@dataclass
class RunOutcome:
    """One pair's outcome: a result, or a classified reason there is none.

    ``extra`` always carries ``source_id``, ``reference_id``, ``source_sensor``,
    ``reference_sensor``, ``matcher``, ``model``, ``stage`` and every key of
    ``PipelineConfig.extra``; failures after matching add ``n_raw_matches``,
    failures after RANSAC add ``n_ransac_inliers`` (CONTRACTS C02).
    """

    pair_id: str
    status: RunStatus
    result: PairResult | None = None
    detail: str = ""
    extra: dict = field(default_factory=dict)

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
    #: Threshold of the second fit on the first fit's inliers (refine_full).
    refit_threshold_px: float = 1.0
    #: Seeds OpenCV's RNG for both robust fits (CONTRACTS C06).
    seed: int = 0
    #: ECC displacement gate (CONTRACTS C07, ``ECC_MAX_SHIFT_PX``).
    ecc_max_shift_px: float = 3.0
    #: Value marking invalid pixels in both images; masked out of ECC.
    nodata: float | None = None
    #: Preprocessing preset run before matching, one of
    #: :data:`lunar_reg.preprocess.presets.PRESET_NAMES` (CONTRACTS C12). The
    #: default changes only from the P1.18 ablation (P1.19, DECISIONS G09).
    # Default from data/processed/ablation/ablation.json via choose_default_preset (P1.19):
    # "anchor passes none=2 ohrc_nac=4 clahe_shadow=4; anchor tie between ohrc_nac,
    # clahe_shadow; median synthetic truth_rms_px ohrc_nac=0.137 clahe_shadow=0.1373;
    # ohrc_nac wins on synthetic"
    preprocess: str = "ohrc_nac"
    #: ``"cpu"``, ``"cuda"`` or ``"cuda:<n>"`` for the learned (torch) matchers;
    #: None = :func:`lunar_reg.device.get_device`. Classical (OpenCV) matchers
    #: always run, and are recorded, on ``"cpu"`` (P2.05).
    device: str | None = None
    #: One of :data:`PRECISIONS`. ``"auto"`` = fp16 for LoFTR on CUDA, fp32
    #: elsewhere; LightGlue ignores it (DISK fp16 / LightGlue fp32 on CUDA).
    precision: str = "auto"

    def __post_init__(self) -> None:
        from lunar_reg.preprocess.presets import PRESET_NAMES

        if self.preprocess not in PRESET_NAMES:
            raise ValueError(f"unknown preset {self.preprocess!r}; choose one of {PRESET_NAMES}")
        if self.precision not in PRECISIONS:
            raise ValueError(f"unknown precision {self.precision!r}; choose one of {PRECISIONS}")


#: Accepted :attr:`PipelineConfig.precision` values (CONTRACTS C03).
PRECISIONS: tuple[str, ...] = ("auto", "fp16", "fp32")

#: Canonical matcher names that run on torch and therefore take a device.
_TORCH_MATCHERS: tuple[str, ...] = ("loftr", "lightglue", "superglue")

#: Provenance of the timing and peak-VRAM numbers recorded by :func:`register_pair`.
TIMING_SOURCE = ValueSource.MEASURED
PEAK_VRAM_SOURCE = ValueSource.MEASURED


#: Matcher names routed to the learned (torch) implementations rather than OpenCV.
LEARNED_MATCHERS: tuple[str, ...] = ("lightglue", "disk", "loftr")


def _canonical_matcher(name: str) -> str:
    """The :data:`lunar_reg.match.MATCHER_NAMES` spelling of ``name`` (aliases resolved)."""
    from lunar_reg.match import ALIASES

    key = name.lower()
    return ALIASES.get(key, key)


def _resolve_device(config: PipelineConfig) -> str:
    """The device the matcher runs on.

    * torch matchers (:data:`_TORCH_MATCHERS`): ``config.device``, or
      :func:`~lunar_reg.device.get_device` when None;
    * classical (OpenCV) matchers: ``"cpu"`` whatever ``config.device`` says --
      OpenCV ignores it, and asking ``get_device`` would import torch;
    * a name :func:`lunar_reg.match.build_matcher` does not know (only test
      stubs reach the matcher with one): ``config.device``, else ``"cpu"``, so
      a stubbed CPU test never opens a CUDA context.
    """
    from lunar_reg.match import MATCHER_NAMES

    key = _canonical_matcher(config.matcher)
    if key in _TORCH_MATCHERS:
        if config.device is not None:
            return config.device
        from lunar_reg.device import get_device

        return get_device()
    if key in MATCHER_NAMES:
        return "cpu"
    return config.device or "cpu"


def _resolve_precision(config: PipelineConfig, device: str) -> str:
    """The precision the matcher will run at, mirroring :mod:`lunar_reg.match.learned`.

    LoFTR: fp16 on CUDA unless ``"fp32"`` is asked for; fp32 elsewhere.
    LightGlue ignores ``config.precision``: DISK runs under fp16 autocast and
    LightGlue in fp32 on CUDA, everything in fp32 on CPU. Every other matcher
    is recorded as fp32.
    """
    key = _canonical_matcher(config.matcher)
    on_cuda = device.startswith("cuda")
    if key == "loftr":
        return "fp16" if on_cuda and config.precision != "fp32" else "fp32"
    if key == "lightglue":
        return "fp16-disk+fp32-lightglue" if on_cuda else "fp32"
    return "fp32"


def _build_matcher(name: str, *, device: str | None = None, precision: str | None = None):
    """Any matcher by name, through the one registry :func:`lunar_reg.match.build_matcher`.

    Kept as a module-level function so tests can monkeypatch it. Learned
    matchers import torch lazily, so classical-only runs stay light. ``device``
    is passed through (classical matchers ignore it); ``precision`` reaches
    LoFTR only.
    """
    from lunar_reg.match import build_matcher

    kwargs = {}
    if precision is not None and _canonical_matcher(name) == "loftr":
        kwargs["precision"] = precision
    return build_matcher(name, device=device, **kwargs)


def _oom_types() -> tuple[type[BaseException], ...]:
    """``(torch.OutOfMemoryError,)`` when torch is loaded, else ``()``.

    Evaluated when an exception reaches the ``except`` clause, so torch is never
    imported for this: a run that never loaded torch cannot raise its OOM.
    """
    torch = sys.modules.get("torch")
    oom = getattr(torch, "OutOfMemoryError", None) if torch is not None else None
    return (oom,) if oom is not None else ()


def _empty_cuda_cache() -> None:
    """Return the allocator's cached blocks to the driver (after an OOM only)."""
    torch = sys.modules.get("torch")
    if torch is not None:
        torch.cuda.empty_cache()


def _first_line(exc: BaseException) -> str:
    text = str(exc).strip()
    return text.splitlines()[0] if text else type(exc).__name__


def _degenerate_input(sides, nodata) -> str | None:
    """``"<side>: <why>"`` for the first side whose valid pixels carry no information.

    ``sides`` is ``((name, image, valid_mask_or_None), ...)``. Validity follows the
    presets (given mask, else ``image != nodata``, finite pixels only). Raises
    ``ValueError`` for a mask whose shape differs from its image.
    """
    from lunar_reg.preprocess.presets import _valid_mask

    for name, image, valid in sides:
        arr = np.asarray(image)
        values = arr[_valid_mask(arr, valid, nodata)]
        if values.size == 0:
            return f"{name}: no valid pixel"
        if values.min() == values.max():
            return f"{name}: all valid pixels equal ({values.flat[0]!r})"
    return None


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"


def _scalar_meta(meta: dict) -> dict:
    """``matcher_<k>`` for every scalar matcher meta value (str, int, float, bool)."""
    return {f"matcher_{k}": v for k, v in meta.items() if isinstance(v, (str, int, float, bool))}


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
    source_valid: np.ndarray | None = None,
    reference_valid: np.ndarray | None = None,
) -> RunOutcome:
    """Register one pair and package everything it produced.

    Stages: preprocess preset (``config.preprocess``, skipped for ``"none"``)
    -> match -> ``min_matches`` -> robust fit (``seed``) -> ``min_inliers``
    -> :func:`~lunar_reg.align.refine.refine_full` at ``refit_threshold_px`` ->
    ``min_inliers`` again ("after refit") -> metrics, uniformity, conditioning.
    Every failure after the call starts is a classified :class:`RunOutcome`;
    this function does not raise for a bad pair.

    Counts follow DECISIONS G34: the stored points are the raw matcher output,
    ``inlier_mask`` marks the final (refit) inliers over that raw set, and the
    metrics report raw, first-pass and final counts.

    ``source_sun`` / ``reference_sun`` are ``(azimuth_deg, elevation_deg)``. When
    both are given they select the ECC prefilter via
    :func:`~lunar_reg.align.refine.choose_ecc_prefilter`, which is the reliable
    signal for that choice -- see the measurements in that module.
    ``source_valid`` / ``reference_valid`` are boolean validity masks (True =
    valid pixel) passed to ECC, as is ``config.nodata``.

    With a preset other than ``"none"`` the preprocessed images feed matching,
    the fits, ECC and uniformity, while ``PairResult.source_image`` /
    ``reference_image`` keep the input images. Presets encode nodata as 0, so
    ECC then gets ``nodata=0`` whenever a mask or ``config.nodata`` was given
    or a float input has non-finite pixels.
    A preset that fails is ``RunStatus.PREPROCESS_FAILED`` at stage
    ``"preprocess"`` (Phase_1/LLD/preprocess_presets.md §2).
    An input that itself carries no information (no valid pixel, or all valid
    pixels equal) is not a preset failure: the preset is skipped for both images,
    the inputs go to matching unchanged, and ``extra["preprocess_skipped"]``
    records why (human decision on Q-P1.19-3, option b). A preset that turns an
    informative input into a degenerate output is still PREPROCESS_FAILED.

    Every outcome's ``extra`` (and an OK result's ``PairResult.extra``) records
    ``device`` and ``precision`` (P2.05), ``seconds_total`` around the whole
    call and, once matching ran, ``seconds_match`` around the matcher call
    (``timing_source`` = measured). On a CUDA device ``peak_vram_bytes`` is
    ``torch.cuda.max_memory_allocated`` after resetting the peak before
    matching (``peak_vram_source`` = measured). ``torch.OutOfMemoryError`` from
    the matcher is ``RunStatus.OOM`` at stage ``"match"`` (detail = the first
    line of the message), followed by ``torch.cuda.empty_cache()``.
    """
    t_start = time.perf_counter()
    # Imported here, not at module level, so tests can monkeypatch the stages.
    from lunar_reg.align.estimate import estimate_transform
    from lunar_reg.align.refine import choose_ecc_prefilter, refine_full
    from lunar_reg.eval.conditioning import bootstrap_conditioning
    from lunar_reg.eval.metrics import compute_metrics
    from lunar_reg.eval.uniformity import compute_uniformity
    from lunar_reg.match.base import MatchResult
    from lunar_reg.results import PairResult

    config = config or PipelineConfig()
    device = _resolve_device(config)
    precision = _resolve_precision(config, device)
    base = {
        "source_id": source_id,
        "reference_id": reference_id,
        "source_sensor": source_sensor,
        "reference_sensor": reference_sensor,
        "matcher": config.matcher,
        "model": config.model,
        "preprocess": config.preprocess,
        **config.extra,
        "device": device,
        "precision": precision,
    }
    counts: dict[str, int] = {}
    #: seconds_match, peak_vram_bytes and their sources, once matching ran.
    measured: dict = {}

    def elapsed() -> dict:
        return {
            "seconds_total": time.perf_counter() - t_start,
            "timing_source": TIMING_SOURCE.value,
        }

    def fail(status: RunStatus, stage: str, detail: str) -> RunOutcome:
        return RunOutcome(
            pair_id,
            status,
            detail=detail,
            extra={**base, "stage": stage, **counts, **measured, **elapsed()},
        )

    # 0. preprocess preset; the inputs are kept for PairResult (thumbnails)
    inputs = (source, reference)
    ecc_nodata = config.nodata
    placeholders = ""
    if config.preprocess != "none":
        # Module attribute, not a name import, so tests can monkeypatch it.
        from lunar_reg.preprocess import presets

        try:
            why = _degenerate_input(
                (("source", source, source_valid), ("reference", reference, reference_valid)),
                config.nodata,
            )
        except Exception as exc:  # noqa: BLE001 - a bad mask/input is a preprocess outcome
            return fail(RunStatus.PREPROCESS_FAILED, "preprocess", _describe(exc))
        if why is not None:
            # Q-P1.19-3 (b): nothing for a preset to work on; let matching
            # classify the pair instead of reporting a preset failure.
            base["preprocess_skipped"] = f"degenerate_input: {why}"
            logger.info("%s: preset %r skipped (%s)", pair_id, config.preprocess, why)
    if config.preprocess != "none" and "preprocess_skipped" not in base:
        try:
            pre = presets.apply_preset(
                config.preprocess,
                source,
                reference,
                source_valid=source_valid,
                reference_valid=reference_valid,
                nodata=config.nodata,
            )
        except Exception as exc:  # noqa: BLE001 - a preset raising (bad mask, bad input) is an outcome
            return fail(RunStatus.PREPROCESS_FAILED, "preprocess", _describe(exc))
        if not pre.ok:
            return fail(RunStatus.PREPROCESS_FAILED, "preprocess", pre.detail)
        source, reference = pre.source, pre.reference
        placeholders = ",".join(sorted(pre.uses_placeholders))
        has_nonfinite = any(
            np.issubdtype(np.asarray(img).dtype, np.inexact)
            and not np.isfinite(np.asarray(img)).all()
            for img in inputs
        )
        if (
            source_valid is not None
            or reference_valid is not None
            or config.nodata is not None
            or has_nonfinite
        ):
            ecc_nodata = 0  # presets encode nodata (incl. NaN/inf input pixels) as 0

    # 1-2. match
    on_cuda = device.startswith("cuda")
    oom_detail: str | None = None
    try:
        matcher = _build_matcher(config.matcher, device=device, precision=precision)
        # LoFTR on a device string other than "cuda" downgrades to fp32 itself.
        base["precision"] = precision = getattr(matcher, "precision", precision)
        if on_cuda:
            import torch

            torch.cuda.reset_peak_memory_stats(device)
        t_match = time.perf_counter()
        raw = matcher.match(source, reference)
        measured["seconds_match"] = time.perf_counter() - t_match
        if on_cuda:
            measured["peak_vram_bytes"] = int(torch.cuda.max_memory_allocated(device))
            measured["peak_vram_source"] = PEAK_VRAM_SOURCE.value
    except _oom_types() as exc:  # before the generic clause: OOM subclasses RuntimeError
        oom_detail = _first_line(exc)
    except Exception as exc:  # noqa: BLE001 - a matcher failing is an outcome
        return fail(RunStatus.MATCHER_ERROR, "match", _describe(exc))
    if oom_detail is not None:
        # Outside the except clause: the traceback, and the tensors its frames
        # hold, are released by now, so the cache can actually be returned.
        _empty_cuda_cache()
        torch = sys.modules.get("torch")
        if on_cuda and torch is not None:
            # The peak up to the failed allocation (the failed request itself is not in it).
            measured["peak_vram_bytes"] = int(torch.cuda.max_memory_allocated(device))
            measured["peak_vram_source"] = PEAK_VRAM_SOURCE.value
        return fail(RunStatus.OOM, "match", oom_detail)
    counts["n_raw_matches"] = len(raw)
    licence = raw.meta.get("licence")
    if licence is not None:
        base["licence"] = licence  # G11: SuperGlue outcomes carry their licence
    if len(raw) < config.min_matches:
        detail = (
            f"{config.matcher} returned {len(raw)} correspondence(s), "
            f"below the minimum of {config.min_matches}"
        )
        reason = raw.meta.get("empty_reason")
        if reason:
            detail += f"; reason: {reason}"
        return fail(RunStatus.TOO_FEW_MATCHES, "match", detail)

    # 3-4. first robust fit, on a copy so ``raw`` keeps no mask
    first = MatchResult(raw.src_pts, raw.dst_pts, raw.scores, raw.matcher, None, dict(raw.meta))
    try:
        transform, first = estimate_transform(
            first, model=config.model, threshold_px=config.ransac_threshold_px, seed=config.seed
        )
    except ValueError as exc:
        return fail(RunStatus.ESTIMATION_FAILED, "estimate", str(exc))
    ransac_mask = np.asarray(first.inlier_mask, dtype=bool).copy()
    counts["n_ransac_inliers"] = int(ransac_mask.sum())
    if counts["n_ransac_inliers"] < config.min_inliers:
        return fail(
            RunStatus.TOO_FEW_INLIERS,
            "estimate",
            f"RANSAC kept {counts['n_ransac_inliers']} of {len(raw)} matches",
        )

    prefilter = config.ecc_prefilter
    if source_sun is not None and reference_sun is not None:
        prefilter = choose_ecc_prefilter(source_sun, reference_sun)

    # 5-6. refit on the first-pass inliers, then ECC
    try:
        transform, refit, detail = refine_full(
            first,
            source=source,
            reference=reference,
            model=config.model,
            threshold_px=config.refit_threshold_px,
            use_ecc=config.use_ecc,
            ecc_kwargs={
                "prefilter": prefilter,
                "nodata": ecc_nodata,
                "max_shift_px": config.ecc_max_shift_px,
                "source_valid": source_valid,
                "reference_valid": reference_valid,
            },
            seed=config.seed,
        )
        refit_inliers = (
            np.asarray(refit.inlier_mask, dtype=bool)
            if refit.inlier_mask is not None
            else np.ones(len(refit), dtype=bool)
        )
        # Lift the refit mask (over the first-pass inliers, in order) to the raw set.
        refit_mask = np.zeros(len(raw), dtype=bool)
        refit_mask[np.flatnonzero(ransac_mask)] = refit_inliers
    except Exception as exc:  # noqa: BLE001 - refit/ECC failing is an outcome
        return fail(RunStatus.REFINEMENT_FAILED, "refine", _describe(exc))
    counts["n_refit_inliers"] = int(refit_mask.sum())
    if counts["n_refit_inliers"] < config.min_inliers:
        return fail(
            RunStatus.TOO_FEW_INLIERS,
            "refine",
            f"after refit: {counts['n_refit_inliers']} of {counts['n_ransac_inliers']} "
            f"first-pass inliers at {config.refit_threshold_px} px",
        )

    # 7. evaluate and package
    try:
        final = MatchResult(raw.src_pts, raw.dst_pts, matcher=raw.matcher, inlier_mask=refit_mask)
        metrics = compute_metrics(final, transform, gsd_m=config.gsd_m, ransac_mask=ransac_mask)
        inliers = final.inliers()
        uniformity = compute_uniformity(inliers.src_pts, source.shape[:2])

        conditioning = {}
        if config.n_bootstrap:
            conditioning = bootstrap_conditioning(
                inliers.src_pts,
                inliers.dst_pts,
                source.shape[:2],
                model=config.model,
                n_bootstrap=config.n_bootstrap,
            ).as_dict()

        import cv2

        result = PairResult(
            pair_id=pair_id,
            source_id=source_id or pair_id,
            reference_id=reference_id or pair_id,
            source_sensor=source_sensor,
            reference_sensor=reference_sensor,
            matcher=config.matcher,
            src_pts=raw.src_pts,
            dst_pts=raw.dst_pts,
            inlier_mask=refit_mask,
            ransac_mask=ransac_mask,
            pre_ecc_transform=detail["pre_ecc_matrix"],
            transform=transform.matrix,
            metrics=metrics.as_dict(),
            uniformity=uniformity.as_dict(),
            conditioning=conditioning,
            source_image=inputs[0],
            reference_image=inputs[1],
            synthetic=synthetic,
            notes=notes,
            extra={
                **config.extra,
                "preprocess": config.preprocess,
                "preprocess_placeholders": placeholders,
                **(
                    {"preprocess_skipped": base["preprocess_skipped"]}
                    if "preprocess_skipped" in base
                    else {}
                ),
                "device": device,
                "precision": precision,
                **measured,
                "ecc_prefilter": prefilter,
                "refine_stages": "+".join(detail.get("stages", [])),
                "ecc_status": detail.get("ecc_status"),
                "ecc_motion": detail.get("ecc_motion"),
                "ecc_cc": detail.get("ecc_cc"),
                "ecc_shift_px": detail.get("ecc_shift_px"),
                "refit_threshold_px": config.refit_threshold_px,
                "ransac_threshold_px": config.ransac_threshold_px,
                "min_inliers": config.min_inliers,
                "model": config.model,
                "seed": config.seed,
                "cv2_version": cv2.__version__,
                "numpy_version": np.__version__,
                "source_sun_azimuth": None if source_sun is None else source_sun[0],
                "source_sun_elevation": None if source_sun is None else source_sun[1],
                "reference_sun_azimuth": None if reference_sun is None else reference_sun[0],
                "reference_sun_elevation": None if reference_sun is None else reference_sun[1],
                **_scalar_meta(raw.meta),
                **({} if licence is None else {"licence": licence}),
            },
        )
    except Exception as exc:  # noqa: BLE001 - an evaluation failure is an outcome
        return fail(RunStatus.EVAL_FAILED, "eval", _describe(exc))

    total = elapsed()
    result.extra.update(total)
    return RunOutcome(
        pair_id,
        RunStatus.OK,
        result=result,
        extra={**base, "stage": "done", **counts, **measured, **total},
    )


@dataclass
class BatchReport:
    """What a batch run produced, including what it could not."""

    outcomes: list = field(default_factory=list)
    #: What persisting the batch did to the store, when ``run_batch`` had a root.
    store: StoreReport | None = None

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
        if self.store is not None:
            lines.append(self.store.report())
        return "\n".join(lines)


def run_batch(pairs, config: PipelineConfig | None = None, root=None) -> BatchReport:
    """Register many pairs and optionally persist them.

    ``pairs`` is an iterable of dicts accepted as keyword arguments by
    :func:`register_pair`. With ``root``, OK results go to the store
    (:func:`~lunar_reg.results.save_results`) and failures are appended to
    ``failures.parquet`` (:func:`~lunar_reg.results.save_failures`).
    """
    from lunar_reg.results import save_failures, save_results

    report = BatchReport()
    for spec in pairs:
        outcome = register_pair(config=config, **spec)
        report.outcomes.append(outcome)
        if not outcome.ok:
            logger.warning("%s: %s (%s)", outcome.pair_id, outcome.status.value, outcome.detail)

    if root is not None:
        try:
            report.store = save_results(report.results, root)
        finally:
            # Failures are recorded even when saving the OK results raises
            # (e.g. FileExistsError on an existing pair id): they are not
            # recomputable without rerunning the batch.
            save_failures(report.failures, root)
    return report


__all__ = [
    "BatchReport",
    "PRECISIONS",
    "PipelineConfig",
    "RunOutcome",
    "RunStatus",
    "register_pair",
    "run_batch",
]
