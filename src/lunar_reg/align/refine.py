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

import logging
import math

import numpy as np

from lunar_reg.align.estimate import Transform, estimate_transform
from lunar_reg.match.base import MatchResult

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
    result: MatchResult, model: str = "homography", threshold_px: float = 1.0
):
    """Re-fit the transform on inliers alone at a tighter threshold.

    The first robust fit rejects gross outliers at a permissive threshold; this
    second pass, on a clean point set, is what delivers the sub-pixel residual.
    Reporting RMSE from the first fit understates achievable accuracy.
    """
    inliers = result.inliers()
    logger.info("re-estimating on %d inliers at %.1f px", len(inliers), threshold_px)
    return estimate_transform(inliers, model=model, threshold_px=threshold_px)


#: Gaussian sigma for the local-contrast prefilter, in pixels. Chosen to sit
#: well above detector noise and well below crater scale, so it removes the
#: broad illumination gradient without flattening the landforms ECC aligns to.
#: PLACEHOLDER to tune -- 8 px was the only value swept.
ECC_PREFILTER_SIGMA: float = 8.0

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
        np.asarray(source, dtype=np.float32), np.asarray(transform_matrix, dtype=np.float64),
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


def refine_transform_ecc(
    transform: Transform,
    source: np.ndarray,
    reference: np.ndarray,
    max_iterations: int = 200,
    epsilon: float = 1e-7,
    gaussian_blur: int = 5,
    prefilter: str = "none",
) -> tuple[Transform, float]:
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

    The prefilter, and why it defaults on
    -------------------------------------
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

    Returns ``(refined_transform, correlation_coefficient)``. On failure to
    converge the original transform is returned with ``cc = nan`` -- ECC
    diverges on low-texture pairs, and silently returning a diverged warp would
    be worse than not refining.
    """
    import cv2

    if transform.matrix.shape != (3, 3):
        full = np.vstack([transform.matrix, [0.0, 0.0, 1.0]])
    else:
        full = transform.matrix

    if prefilter not in ECC_PREFILTERS:
        raise ValueError(f"prefilter must be one of {ECC_PREFILTERS}, got {prefilter!r}")

    if prefilter == "auto":
        ncc = _aligned_ncc(full, source, reference)
        prefilter = (
            "none" if (math.isfinite(ncc) and ncc >= ECC_SAME_ILLUMINATION_NCC)
            else "local_contrast"
        )
        logger.debug("ECC prefilter chosen automatically: %s (aligned NCC %.4f)", prefilter, ncc)

    if prefilter == "local_contrast":
        source = local_contrast_normalize(source)
        reference = local_contrast_normalize(reference)

    src = np.asarray(source, dtype=np.float32)
    ref = np.asarray(reference, dtype=np.float32)
    for arr in (src, ref):
        if arr.max() > 1.0:
            arr /= 255.0

    try:
        initial = np.linalg.inv(full)
    except np.linalg.LinAlgError:
        logger.warning("transform is singular; skipping ECC refinement")
        return transform, float("nan")
    initial = (initial / initial[2, 2]).astype(np.float32)

    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, max_iterations, epsilon)
    try:
        cc, warp = cv2.findTransformECC(
            ref, src, initial.copy(), cv2.MOTION_HOMOGRAPHY, criteria, None, gaussian_blur
        )
    except cv2.error as exc:
        logger.warning("ECC did not converge (%s); keeping the feature-based transform", exc)
        return transform, float("nan")

    refined = np.linalg.inv(warp.astype(np.float64))
    refined = refined / refined[2, 2]
    return (
        Transform(
            matrix=refined,
            model=transform.model,
            n_inliers=transform.n_inliers,
            n_total=transform.n_total,
        ),
        float(cc),
    )


def refine_full(
    result: MatchResult,
    source: np.ndarray | None = None,
    reference: np.ndarray | None = None,
    model: str = "homography",
    threshold_px: float = 1.0,
    use_ecc: bool = True,
    ecc_kwargs: dict | None = None,
) -> tuple[Transform, MatchResult, dict]:
    """The recommended refinement chain: refit on inliers, then ECC.

    Deliberately does **not** call ``cornerSubPix`` -- see the module docstring.

    ``ecc_kwargs`` is forwarded to :func:`refine_transform_ecc` -- in practice
    ``{"prefilter": ...}``, which for a cross-illumination pair is the single
    most consequential setting in this chain.

    Returns ``(transform, result, detail)`` where ``detail`` records which
    stages ran and the ECC correlation coefficient if it did.
    """
    detail: dict = {"stages": []}

    transform, result = reestimate_on_inliers(result, model=model, threshold_px=threshold_px)
    detail["stages"].append("reestimate_on_inliers")
    detail["inliers_after_refit"] = transform.n_inliers

    if use_ecc and source is not None and reference is not None:
        refined, cc = refine_transform_ecc(transform, source, reference, **(ecc_kwargs or {}))
        if np.isfinite(cc):
            transform = refined
            detail["stages"].append("ecc")
            detail["ecc_cc"] = cc
        else:
            detail["ecc_skipped"] = "did not converge"

    return transform, result, detail
