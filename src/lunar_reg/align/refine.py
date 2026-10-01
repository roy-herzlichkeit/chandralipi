"""Sub-pixel refinement of the geometric transform.

Sub-pixel accuracy is the problem statement's headline requirement, so this
module is where the claim is actually earned. Two refinements work and one
popular one does not; all three findings are measured, not assumed.

What works
----------
**Refit on inliers at a tighter threshold** (:func:`reestimate_on_inliers`).
The first RANSAC pass runs permissively to reject gross outliers; a second fit
on the clean set at a tight threshold is what delivers the final residual.

**ECC intensity refinement** (:func:`refine_transform_ecc`). Optimises the
transform directly against image intensities, so it is not limited by keypoint
localisation at all. Measured on a synthetic homography with sensor noise, it
improved probe error against the true transform from 0.0457 to **0.0177 px**, a
2.6x gain over the feature-only result.

What does NOT work, despite being the obvious thing to reach for
----------------------------------------------------------------
**Do not run ``cornerSubPix`` on SIFT/ASIFT/AKAZE/KAZE keypoints.** Measured:
applying it made probe error against the true homography *four times worse*
(0.0146 -> 0.0577 px).

The reason is that those detectors already localise to sub-pixel precision --
SIFT interpolates the DoG extremum, AKAZE its nonlinear-scale-space response.
Verified on this project's synthetic scene, the fraction of keypoints with
non-integer coordinates is:

===========  ==========================
detector     non-integer coordinates
===========  ==========================
SIFT         100%
ASIFT        100%
AKAZE        100%
KAZE         100%
BRISK        95%
ORB          78%
FAST         **0%**
===========  ==========================

``cornerSubPix`` re-localises a point onto the nearest *corner*, which is a
different feature definition. For blob-like features -- and craters are blobs --
it drags correct sub-pixel positions off-target. It is the right tool only for
integer-output corner detectors such as FAST or Harris, which is what
:data:`DETECTORS_ALREADY_SUBPIXEL` guards against.
"""

from __future__ import annotations

import dataclasses
import logging
import math
from dataclasses import dataclass
from enum import Enum

import numpy as np

from lunar_reg.align.estimate import Transform, estimate_transform
from lunar_reg.match.base import MatchResult
from lunar_reg.provenance import Sourced, ValueSource

logger = logging.getLogger(__name__)

#: Half-size of the correlation window used by :func:`refine_corners`.
DEFAULT_WINDOW = 5

#: Detectors whose keypoints are already sub-pixel. Running ``cornerSubPix`` on
#: these degrades accuracy -- see the module docstring for the measurement.
DETECTORS_ALREADY_SUBPIXEL = frozenset({"sift", "asift", "akaze", "kaze", "brisk", "orb"})


def refine_corners(image: np.ndarray, pts: np.ndarray, window: int = DEFAULT_WINDOW) -> np.ndarray:
    """Refine integer-valued corner locations to sub-pixel precision.

    Only appropriate for detectors whose raw output is integer-valued (FAST,
    Harris, Shi-Tomasi, goodFeaturesToTrack). For SIFT-family keypoints this
    *reduces* accuracy -- see the module docstring. Points that fail to converge
    are returned unchanged rather than dropped, so the array stays aligned with
    its partner.
    """
    import cv2

    if len(pts) == 0:
        return pts
    if image.dtype != np.uint8:
        from lunar_reg.preprocess.radiometric import to_uint8

        image = to_uint8(image)

    corners = np.asarray(pts, dtype=np.float32).reshape(-1, 1, 2)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 40, 0.001)
    refined = cv2.cornerSubPix(image, corners, (window, window), (-1, -1), criteria)
    return refined.reshape(-1, 2).astype(np.float64)


def refine_matches(
    result: MatchResult,
    source: np.ndarray,
    reference: np.ndarray,
    window: int = DEFAULT_WINDOW,
    force: bool = False,
) -> MatchResult:
    """Sub-pixel refine both sides of every correspondence with ``cornerSubPix``.

    **Refuses by default** when the matches came from a detector that already
    produces sub-pixel keypoints, because doing it anyway measurably degrades
    accuracy. Pass ``force=True`` to override deliberately.

    Prefer :func:`refine_transform_ecc`, which refines the transform itself and
    is not limited by keypoint localisation.

    Only meaningful when the coordinates share a frame with the arrays passed
    in -- refine per tile, before lifting to parent coordinates.
    """
    detector = str(result.meta.get("detector", "")).lower()
    if detector in DETECTORS_ALREADY_SUBPIXEL and not force:
        logger.info(
            "skipping cornerSubPix: %r keypoints are already sub-pixel, and refining "
            "them measurably degrades accuracy (4x worse on the synthetic benchmark). "
            "Use refine_transform_ecc instead, or pass force=True.",
            detector,
        )
        return result

    return MatchResult(
        src_pts=refine_corners(source, result.src_pts, window),
        dst_pts=refine_corners(reference, result.dst_pts, window),
        scores=result.scores,
        matcher=result.matcher,
        inlier_mask=result.inlier_mask,
        meta={**result.meta, "subpixel": f"cornerSubPix/{window}"},
    )


def reestimate_on_inliers(
    result: MatchResult, model: str = "homography", threshold_px: float = 1.0, seed: int = 0
):
    """Re-fit the transform on inliers alone at a tighter threshold.

    The first robust fit rejects gross outliers at a permissive threshold; this
    second pass, on a clean point set, is what delivers the sub-pixel residual.
    Reporting RMSE from the first fit understates achievable accuracy.

    ``result`` is not modified: the refit's inlier mask lands on a new
    :class:`MatchResult`, which is what is returned.
    """
    inliers = result.inliers()
    if inliers is result:  # no mask yet: inliers() hands back the same object
        inliers = dataclasses.replace(result)
    logger.info("re-estimating on %d inliers at %.1f px", len(inliers), threshold_px)
    return estimate_transform(inliers, model=model, threshold_px=threshold_px, seed=seed)


#: Gaussian sigma for the local-contrast prefilter, in pixels. Chosen to sit
#: well above detector noise and well below crater scale, so it removes the
#: broad illumination gradient without flattening the landforms ECC aligns to.
#: PLACEHOLDER to tune -- 8 px was the only value swept.
ECC_PREFILTER_SIGMA: float = 8.0
ECC_PREFILTER_SIGMA_SOURCE = ValueSource.INFERRED

ECC_PREFILTERS = ("auto", "local_contrast", "none")

#: Raw-intensity NCC above which ``prefilter="auto"`` treats two images as
#: same-illumination. MEASURED on synthetic scenes: same illumination lands at
#: 0.980-0.998, a 15 degree azimuth change at 0.954-0.960, a 30 degree change at
#: 0.813-0.852.
#:
#: KNOWN DEFECT, which is why "auto" is not the default. NCC falls for two
#: unrelated reasons -- illumination difference and sensor noise -- and the right
#: response is opposite in each case. The suite's ``noisy_pair`` fixture is
#: same-illumination with sigma=8 additive noise and scores 0.9166, so "auto"
#: prefilters it and lands at 0.0498 px where plain intensity reaches 0.0175 px.
#: Deciding from the images alone cannot separate the two causes; the sun angles
#: can, which is what :func:`choose_ecc_prefilter` uses.
ECC_SAME_ILLUMINATION_NCC: float = 0.97
#: Measured on synthetic scenes only (see above), not on real pairs.
ECC_SAME_ILLUMINATION_NCC_SOURCE = ValueSource.MEASURED

#: Largest probe displacement ECC may introduce relative to the feature fit
#: before its result is rejected as a jump to a wrong correlation peak.
ECC_MAX_SHIFT_PX = Sourced(3.0, ValueSource.INFERRED, "equals the default RANSAC threshold")


class EccStatus(str, Enum):
    APPLIED = "applied"
    SKIPPED_NO_SIMILARITY_MOTION = "skipped_no_similarity_motion"  # partial_affine (G35)
    SKIPPED_SINGULAR = "skipped_singular"
    SKIPPED_DISABLED = "skipped_disabled"  # use_ecc False or images missing
    NOT_CONVERGED = "not_converged"
    REJECTED_DISPLACEMENT = "rejected_displacement"

    @property
    def is_failure(self) -> bool:
        return self in (EccStatus.NOT_CONVERGED, EccStatus.REJECTED_DISPLACEMENT)


@dataclass
class EccOutcome:
    transform: Transform  # refined when APPLIED, else the input transform unchanged
    status: EccStatus
    cc: float  # nan unless APPLIED
    motion: str | None  # "homography" | "affine" | None
    shift_px: float | None  # max probe displacement between input and ECC result
    detail: str = ""


def choose_ecc_prefilter(
    source_sun: tuple[float, float] | None,
    reference_sun: tuple[float, float] | None,
    azimuth_threshold_deg: float = 10.0,
) -> str:
    """Pick an ECC prefilter from sun geometry, which is the reliable signal.

    ``source_sun`` and ``reference_sun`` are ``(azimuth_deg, elevation_deg)``.
    Azimuth difference is what drives the failure: measured on synthetic scenes,
    ECC on raw intensity holds to 0.012 px at 0 degrees, 0.070 px at 15 and
    0.299 px at 30, while the prefilter holds near 0.04-0.06 px throughout.
    Elevation is not used -- shadow fraction tracked elevation in the sweep, but
    accuracy tracked azimuth.

    Returns ``"none"`` when the geometry is unknown, which preserves the
    behaviour of a pipeline that never populated these fields. Note the sun
    fields in :mod:`lunar_reg.ingest.fieldmap` are UNVERIFIED, so a real
    manifest may supply nothing here until the field map is checked against a
    product.

    ``azimuth_threshold_deg`` is a PLACEHOLDER: the sweep only sampled 0, 15 and
    30 degrees, so the crossover is bracketed between 0 and 15, not located.
    """
    if source_sun is None or reference_sun is None:
        return "none"
    difference = abs(float(source_sun[0]) - float(reference_sun[0])) % 360.0
    difference = min(difference, 360.0 - difference)
    return "local_contrast" if difference >= azimuth_threshold_deg else "none"


def _aligned_ncc(transform_matrix: np.ndarray, source: np.ndarray, reference: np.ndarray) -> float:
    """Normalised cross-correlation over the region the transform maps into view."""
    import cv2

    rows, cols = reference.shape[:2]
    warped = cv2.warpPerspective(
        np.asarray(source, dtype=np.float32),
        np.asarray(transform_matrix, dtype=np.float64),
        (cols, rows),
    )
    mask = warped > 0
    if mask.sum() < 64:
        return float("nan")
    a = warped[mask].astype(np.float64)
    b = np.asarray(reference, dtype=np.float64)[mask]
    a -= a.mean()
    b -= b.mean()
    denominator = math.sqrt(float((a * a).sum()) * float((b * b).sum()))
    if denominator <= 0:
        return float("nan")
    return float((a * b).sum() / denominator)


def local_contrast_normalize(image: np.ndarray, sigma: float = ECC_PREFILTER_SIGMA) -> np.ndarray:
    """Divide out the local mean and standard deviation of an image.

    ECC is already invariant to a *global* affine intensity change, which is why
    it is used here at all. What it is not invariant to is the spatially varying
    change a different sun angle produces: one image's slopes brighten where the
    other's darken, and the correlation peak shifts away from true geometric
    alignment. Normalising each pixel against its own neighbourhood removes the
    low-frequency part of that difference and leaves the structure both images
    share.
    """
    import cv2

    f = np.asarray(image, dtype=np.float32)
    mean = cv2.GaussianBlur(f, (0, 0), sigma)
    variance = cv2.GaussianBlur(f * f, (0, 0), sigma) - mean * mean
    std = np.sqrt(np.maximum(variance, 1e-6))
    return np.clip(128.0 + 40.0 * (f - mean) / std, 0, 255).astype(np.uint8)


def ecc_refine(
    transform: Transform,
    source: np.ndarray,
    reference: np.ndarray,
    *,
    max_iterations: int = 200,
    epsilon: float = 1e-7,
    gaussian_blur: int = 5,
    prefilter: str = "none",
    nodata: float | None = None,
    max_shift_px: float = ECC_MAX_SHIFT_PX.value,
    source_valid: np.ndarray | None = None,
    reference_valid: np.ndarray | None = None,
) -> EccOutcome:
    """Refine a transform against image intensities (Enhanced Correlation Coefficient).

    Not limited by keypoint localisation, so it improves on a feature-only fit:
    measured 0.0457 -> 0.0177 px probe error against a known homography.

    Direction convention -- this is the whole difficulty
    ---------------------------------------------------
    ``cv2.findTransformECC``'s argument roles are easy to get backwards, and
    three of the four plausible combinations give wrong answers, two of them
    catastrophically (probe error ~48 px). Worse, **the returned correlation
    coefficient does not distinguish them** -- a 48 px-wrong result reported
    ``cc = 0.98657``, higher than a correct one. So cc cannot be used to detect
    a convention mistake.

    The combination verified correct here, against a known ground-truth
    homography, is: template = *reference*, input = *source*, initial warp =
    ``inv(src_to_ref)``, and the returned matrix inverted. That is what this
    function does; do not rearrange it without re-running the check.

    The prefilter, and why it is off by default
    -------------------------------------------
    MEASURED on synthetic illumination pairs (lunar_reg.eval.scenes), 6 seeds x
    2 matchers, error against a known homography in reference pixels:

        azimuth diff   intensity (median/p90)   local_contrast (median/p90)
             0 deg        0.012 / 0.014            0.034 / 0.045
            15 deg        0.070 / 0.118            0.043 / 0.046
            30 deg        0.299 / 0.538            0.062 / 0.084

    ``local_contrast`` won every single run once the sun angles differed, and
    lost when they did not -- by enough, on a same-illumination pair with sensor
    noise, to leave ECC no better than the feature-only fit it started from.

    So the default stays ``"none"`` and the choice is the caller's, made from
    sun geometry via :func:`choose_ecc_prefilter`. The image-only ``"auto"``
    mode exists but is not recommended: see ``ECC_SAME_ILLUMINATION_NCC`` for
    the case it gets wrong and why image statistics cannot settle this.

    Note the correlation coefficient does **not** rank the two: at 30 degrees
    ``local_contrast`` scored cc 0.813 against intensity's 0.857 while being four
    times more accurate. That is the same trap as the direction convention above
    -- cc measures how well ECC met its own objective, not how close the result
    is to truth.

    These figures are synthetic. The scenes reproduce illumination-driven
    contrast inversion but not lunar photometry, detector noise, or pushbroom
    geometry; re-measure on real pairs before quoting them.

    The fit's own motion model is kept: a homography is refined with
    ``MOTION_HOMOGRAPHY`` and stays 3x3, an affine with ``MOTION_AFFINE`` and
    stays 2x3. ``partial_affine`` has no ECC equivalent (OpenCV's similarity
    motion is not exposed for ECC) and is returned unchanged. Input arrays are
    never modified. Pixels outside ``source_valid``/``reference_valid`` (or equal
    to ``nodata``) are excluded through ``cv2.findTransformECCWithMask``. A
    result that moves any of a 5x5 grid of source probes by more than
    ``max_shift_px`` from the input transform is rejected: ECC converging to a
    different correlation peak is a jump, not a refinement.

    Returns an :class:`EccOutcome`. On anything but ``APPLIED`` the input
    transform comes back with ``cc = nan`` -- ECC diverges on low-texture pairs,
    and silently returning a diverged warp would be worse than not refining.
    """
    import cv2

    if prefilter not in ECC_PREFILTERS:
        raise ValueError(f"prefilter must be one of {ECC_PREFILTERS}, got {prefilter!r}")

    def unchanged(status: EccStatus, motion: str | None, detail: str, shift=None) -> EccOutcome:
        return EccOutcome(transform, status, float("nan"), motion, shift, detail)

    if transform.model == "partial_affine":
        return unchanged(
            EccStatus.SKIPPED_NO_SIMILARITY_MOTION,
            None,
            "partial_affine has no ECC motion model; transform kept",
        )
    motion_name = "affine" if transform.matrix.shape == (2, 3) else "homography"
    motion = cv2.MOTION_AFFINE if motion_name == "affine" else cv2.MOTION_HOMOGRAPHY
    full = (
        np.vstack([transform.matrix, [0.0, 0.0, 1.0]])
        if transform.matrix.shape == (2, 3)
        else np.asarray(transform.matrix, dtype=np.float64)
    )

    if prefilter == "auto":
        ncc = _aligned_ncc(full, source, reference)
        prefilter = (
            "none"
            if (math.isfinite(ncc) and ncc >= ECC_SAME_ILLUMINATION_NCC)
            else "local_contrast"
        )
        logger.debug("ECC prefilter chosen automatically: %s (aligned NCC %.4f)", prefilter, ncc)

    # Validity masks come from the caller's images, before any prefilter.
    input_mask = _validity_mask(source, source_valid, nodata, gaussian_blur)
    template_mask = _validity_mask(reference, reference_valid, nodata, gaussian_blur)

    # Work on copies: the caller's arrays are never written (no in-place /= 255).
    if prefilter == "local_contrast":
        src = local_contrast_normalize(source).astype(np.float32)
        ref = local_contrast_normalize(reference).astype(np.float32)
    else:
        src = np.array(source, dtype=np.float32, copy=True)
        ref = np.array(reference, dtype=np.float32, copy=True)
    for arr in (src, ref):
        if arr.max() > 1.0:
            arr /= 255.0

    try:
        inverse = np.linalg.inv(full)
    except np.linalg.LinAlgError:
        logger.warning("transform is singular; skipping ECC refinement")
        return unchanged(EccStatus.SKIPPED_SINGULAR, motion_name, "input transform is singular")
    if motion_name == "homography":
        initial = (inverse / inverse[2, 2]).astype(np.float32)
    else:
        initial = inverse[:2].astype(np.float32)

    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, max_iterations, epsilon)
    try:
        if input_mask is None and template_mask is None:
            cc, warp = cv2.findTransformECC(
                ref, src, initial.copy(), motion, criteria, None, gaussian_blur
            )
        else:
            full_mask = np.full(ref.shape[:2], 255, np.uint8)
            cc, warp = cv2.findTransformECCWithMask(
                ref,
                src,
                template_mask if template_mask is not None else full_mask,
                input_mask if input_mask is not None else np.full(src.shape[:2], 255, np.uint8),
                initial.copy(),
                motion,
                criteria,
                gaussian_blur,
            )
    except cv2.error as exc:
        first = (str(exc).strip().splitlines() or ["cv2.error"])[0]
        logger.warning("ECC did not converge (%s); keeping the feature-based transform", first)
        return unchanged(EccStatus.NOT_CONVERGED, motion_name, first)
    if not math.isfinite(float(cc)):
        return unchanged(EccStatus.NOT_CONVERGED, motion_name, f"non-finite cc {cc}")

    warp3 = np.asarray(warp, dtype=np.float64)
    if warp3.shape == (2, 3):
        warp3 = np.vstack([warp3, [0.0, 0.0, 1.0]])
    try:
        refined = np.linalg.inv(warp3)
    except np.linalg.LinAlgError:
        return unchanged(EccStatus.NOT_CONVERGED, motion_name, "ECC returned a singular warp")
    refined = refined / refined[2, 2] if motion_name == "homography" else refined[:2]
    candidate = Transform(
        matrix=refined,
        model=transform.model,
        n_inliers=transform.n_inliers,
        n_total=transform.n_total,
        estimator=transform.estimator,
        seed=transform.seed,
    )

    h, w = np.asarray(source).shape[:2]
    gx, gy = np.meshgrid(np.linspace(0, w - 1, 5), np.linspace(0, h - 1, 5))
    probes = np.column_stack([gx.ravel(), gy.ravel()])
    shift = float(np.linalg.norm(candidate.apply(probes) - transform.apply(probes), axis=1).max())
    if shift > max_shift_px:
        detail = f"displacement {shift:.3f} px > gate {max_shift_px} px"
        logger.warning("ECC result rejected: %s", detail)
        return unchanged(EccStatus.REJECTED_DISPLACEMENT, motion_name, detail, shift)

    return EccOutcome(candidate, EccStatus.APPLIED, float(cc), motion_name, shift)


def _validity_mask(
    image: np.ndarray, valid: np.ndarray | None, nodata: float | None, gaussian_blur: int
) -> np.ndarray | None:
    """uint8 0/255 ECC mask, eroded by ``gaussian_blur + 2``; ``None`` when nothing is masked.

    An explicit ``valid`` wins; otherwise ``image != nodata`` when ``nodata`` is
    set (NaN nodata means "not NaN").
    """
    import cv2

    if valid is not None:
        keep = np.asarray(valid, dtype=bool)
    elif nodata is not None:
        arr = np.asarray(image)
        keep = (
            ~np.isnan(arr)
            if (isinstance(nodata, float) and math.isnan(nodata))
            else (arr != nodata)
        )
    else:
        return None
    mask = keep.astype(np.uint8) * 255
    side = gaussian_blur + 2
    return cv2.erode(mask, np.ones((side, side), np.uint8))


def refine_transform_ecc(
    transform: Transform,
    source: np.ndarray,
    reference: np.ndarray,
    max_iterations: int = 200,
    epsilon: float = 1e-7,
    gaussian_blur: int = 5,
    prefilter: str = "none",
    nodata: float | None = None,
    max_shift_px: float = ECC_MAX_SHIFT_PX.value,
    source_valid: np.ndarray | None = None,
    reference_valid: np.ndarray | None = None,
) -> tuple[Transform, float]:
    """Thin wrapper over :func:`ecc_refine`: ``(outcome.transform, outcome.cc)``."""
    outcome = ecc_refine(
        transform,
        source,
        reference,
        max_iterations=max_iterations,
        epsilon=epsilon,
        gaussian_blur=gaussian_blur,
        prefilter=prefilter,
        nodata=nodata,
        max_shift_px=max_shift_px,
        source_valid=source_valid,
        reference_valid=reference_valid,
    )
    return outcome.transform, outcome.cc


def refine_full(
    result: MatchResult,
    source: np.ndarray | None = None,
    reference: np.ndarray | None = None,
    model: str = "homography",
    threshold_px: float = 1.0,
    use_ecc: bool = True,
    ecc_kwargs: dict | None = None,
    seed: int = 0,
) -> tuple[Transform, MatchResult, dict]:
    """The recommended refinement chain: refit on inliers, then ECC.

    Deliberately does **not** call ``cornerSubPix`` -- see the module docstring.

    ``ecc_kwargs`` is forwarded to :func:`ecc_refine` -- in practice
    ``{"prefilter": ...}``, which for a cross-illumination pair is the single
    most consequential setting in this chain; ``nodata``, ``max_shift_px``,
    ``source_valid`` and ``reference_valid`` also pass through.

    Returns ``(transform, result, detail)``. ``detail`` always carries
    ``stages``, ``inliers_after_refit``, ``pre_ecc_matrix``, ``ecc_status``
    (an :class:`EccStatus` value), ``ecc_motion``, ``ecc_cc`` and
    ``ecc_shift_px`` (CONTRACTS C07). The input ``result`` is not modified, and
    the returned matrix has the shape of ``model``.
    """
    detail: dict = {"stages": []}

    transform, result = reestimate_on_inliers(
        result, model=model, threshold_px=threshold_px, seed=seed
    )
    detail["stages"].append("reestimate_on_inliers")
    detail["inliers_after_refit"] = transform.n_inliers
    detail["pre_ecc_matrix"] = transform.matrix.copy()
    detail["ecc_status"] = EccStatus.SKIPPED_DISABLED.value
    detail["ecc_motion"] = None
    detail["ecc_cc"] = None
    detail["ecc_shift_px"] = None

    if use_ecc and source is not None and reference is not None:
        outcome = ecc_refine(transform, source, reference, **(ecc_kwargs or {}))
        detail["ecc_status"] = outcome.status.value
        detail["ecc_motion"] = outcome.motion
        detail["ecc_shift_px"] = outcome.shift_px
        if outcome.status is EccStatus.APPLIED:
            transform = outcome.transform
            detail["stages"].append("ecc")
            detail["ecc_cc"] = outcome.cc

    return transform, result, detail
