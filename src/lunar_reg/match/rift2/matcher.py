"""RIFT2 detection and matching, wired to this project's Matcher interface.

Clean-room implementation from RIFT (arXiv:1804.09493) and RIFT2
(arXiv:2303.00319). No unlicensed source was consulted -- see
:mod:`lunar_reg.match.rift2.phase` for why that matters here.

Detection follows RIFT section III-A: corners from local maxima of the phase
congruency **minimum** moment, edges from FAST on the **maximum** moment. The
paper's reasoning for using both is that corners are highly repeatable but few,
while edges are plentiful but less repeatable, and matching needs both accuracy
and count.
"""

from __future__ import annotations

import logging

import numpy as np

from lunar_reg.match.base import MatchResult
from lunar_reg.match.rift2.descriptor import N_GRIDS, PATCH_SIZE, describe_keypoints
from lunar_reg.match.rift2.mim import DOMINANT_RATIO, build_mim
from lunar_reg.match.rift2.phase import N_ORIENTATIONS, N_SCALES, compute_phase_congruency

logger = logging.getLogger(__name__)

#: Total keypoints kept per image. Paper-stated: RIFT2 Table I, "Keypoint
#: number: 5000".
MAX_KEYPOINTS = 5000

#: FAST threshold. The paper states 0.001 on its normalised moment map; OpenCV's
#: FAST takes an integer threshold on 8-bit input, so the moment map is scaled
#: to 0-255 and this is the corresponding integer. Documented as a conversion,
#: not as a paper value.
FAST_THRESHOLD_UINT8 = 1

#: Lowe ratio for descriptor matching. NOT stated in either paper -- the papers
#: use nearest-neighbour with an outlier filter. This is our choice.
DEFAULT_RATIO = 0.9


def _to_uint8(array: np.ndarray) -> np.ndarray:
    """Scale a moment map to 8-bit for OpenCV's detectors."""
    finite = array[np.isfinite(array)]
    if finite.size == 0:
        return np.zeros(array.shape, dtype=np.uint8)
    lo, hi = float(finite.min()), float(finite.max())
    if hi <= lo:
        return np.zeros(array.shape, dtype=np.uint8)
    return (((array - lo) / (hi - lo)) * 255.0).clip(0, 255).astype(np.uint8)


def detect_corners(min_moment: np.ndarray, max_points: int, nms_radius: int = 3) -> np.ndarray:
    """Corner keypoints from local maxima of the PC minimum moment.

    The minimum moment is a cornerness measure (RIFT equation 16), so this is
    local-maximum detection plus non-maximum suppression, exactly as the paper
    describes.
    """
    import cv2

    scaled = _to_uint8(min_moment)
    size = 2 * nms_radius + 1
    dilated = cv2.dilate(scaled, np.ones((size, size), np.uint8))
    # A pixel survives if it equals the local max and is not background.
    peaks = (scaled == dilated) & (scaled > 0)
    ys, xs = np.nonzero(peaks)
    if len(xs) == 0:
        return np.empty((0, 2))

    strengths = scaled[ys, xs]
    order = np.argsort(strengths)[::-1][:max_points]
    return np.column_stack([xs[order], ys[order]]).astype(float)


def detect_edges(max_moment: np.ndarray, max_points: int) -> np.ndarray:
    """Edge keypoints via FAST on the PC maximum moment.

    The maximum moment is an edge map (RIFT equation 15). The paper notes FAST
    is chosen here purely for speed and that other detectors would serve.
    """
    import cv2

    scaled = _to_uint8(max_moment)
    detector = cv2.FastFeatureDetector_create(threshold=FAST_THRESHOLD_UINT8)
    keypoints = detector.detect(scaled, None)
    if not keypoints:
        return np.empty((0, 2))

    keypoints = sorted(keypoints, key=lambda k: k.response, reverse=True)[:max_points]
    return np.array([k.pt for k in keypoints], dtype=float)


class RIFT2Matcher:
    """Radiation-variation Insensitive Feature Transform, version 2.

    Detects on phase congruency and describes with a rotation-invariant recoded
    Maximum Index Map, which makes it robust to the nonlinear radiation
    differences between sensors -- the OHRC-to-IIRS case this project needs.

    Satisfies :class:`lunar_reg.match.base.Matcher`, so it drops into
    :class:`~lunar_reg.match.tiled.TiledMatcher` and the benchmark table
    alongside SIFT/ASIFT/AKAZE. CPU-only, so unaffected by the VRAM budget.

    Validation status
    -----------------
    Implemented from the papers' equations, with these checks passing: the
    dominant-index recoding reproduces the worked histogram example in the RIFT2
    paper exactly; the descriptor is invariant to affine intensity change and to
    contrast inversion; and matching recovers a known homography. It has **not**
    been compared against the authors' MATLAB output, because that code is
    unlicensed -- so treat published RIFT2 numbers as unreproduced here.
    """

    def __init__(
        self,
        n_scales: int = N_SCALES,
        n_orientations: int = N_ORIENTATIONS,
        patch_size: int = PATCH_SIZE,
        n_grids: int = N_GRIDS,
        max_keypoints: int = MAX_KEYPOINTS,
        ratio: float = DEFAULT_RATIO,
        dominant_ratio: float = DOMINANT_RATIO,
        use_edges: bool = True,
        use_corners: bool = True,
    ) -> None:
        if not (use_edges or use_corners):
            raise ValueError("at least one of use_edges / use_corners must be True")
        self.n_scales = n_scales
        self.n_orientations = n_orientations
        self.patch_size = patch_size
        self.n_grids = n_grids
        self.max_keypoints = max_keypoints
        self.ratio = ratio
        self.dominant_ratio = dominant_ratio
        self.use_edges = use_edges
        self.use_corners = use_corners
        self.name = "rift2"

    def detect_and_describe(self, image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Keypoints and RIFT descriptors for one image.

        The log-Gabor convolutions are computed once and shared between
        detection and description, as the paper notes -- which is why the MIM is
        nearly free once phase congruency has been computed.
        """
        from lunar_reg.preprocess.radiometric import to_uint8

        arr = image if image.dtype == np.uint8 else to_uint8(image)
        phase = compute_phase_congruency(arr.astype(np.float64), self.n_scales, self.n_orientations)
        mim = build_mim(phase.amplitude_by_orientation)

        budget = self.max_keypoints // (2 if (self.use_edges and self.use_corners) else 1)
        parts = []
        if self.use_corners:
            parts.append(detect_corners(phase.min_moment, budget))
        if self.use_edges:
            parts.append(detect_edges(phase.max_moment, budget))

        keypoints = np.vstack([p for p in parts if len(p)]) if any(len(p) for p in parts) else None
        if keypoints is None:
            return np.empty((0, 2)), np.empty((0, self.descriptor_size), np.float32)

        return describe_keypoints(
            mim,
            keypoints,
            self.n_orientations,
            self.patch_size,
            self.n_grids,
            self.dominant_ratio,
        )

    @property
    def descriptor_size(self) -> int:
        return self.n_grids * self.n_grids * self.n_orientations

    def _empty(self, reason: str, n_src: int, n_ref: int) -> MatchResult:
        """An empty result that says why it is empty."""
        empty = MatchResult.empty(self.name)
        empty.meta = {
            "detector": "rift2",
            "ratio": self.ratio,
            "n_scales": self.n_scales,
            "n_orientations": self.n_orientations,
            "empty_reason": reason,
            "n_keypoints_src": int(n_src),
            "n_keypoints_ref": int(n_ref),
        }
        return empty

    def match(self, source: np.ndarray, reference: np.ndarray) -> MatchResult:
        import cv2

        src_pts, src_desc = self.detect_and_describe(source)
        ref_pts, ref_desc = self.detect_and_describe(reference)

        if len(src_desc) < 2 or len(ref_desc) < 2:
            logger.debug(
                "%s: too few descriptors (%d, %d)", self.name, len(src_desc), len(ref_desc)
            )
            return self._empty("too_few_keypoints", len(src_desc), len(ref_desc))

        matcher = cv2.BFMatcher(cv2.NORM_L2)
        pairs = matcher.knnMatch(src_desc, ref_desc, k=2)

        src, dst, scores = [], [], []
        for pair in pairs:
            if len(pair) < 2:
                continue
            best, second = pair
            if best.distance < self.ratio * second.distance:
                src.append(src_pts[best.queryIdx])
                dst.append(ref_pts[best.trainIdx])
                scores.append(1.0 - best.distance / max(second.distance, 1e-9))

        if not src:
            return self._empty("no_ratio_survivors", len(src_desc), len(ref_desc))

        logger.debug(
            "%s: %d matches from %d/%d descriptors",
            self.name,
            len(src),
            len(src_desc),
            len(ref_desc),
        )
        return MatchResult(
            src_pts=np.array(src),
            dst_pts=np.array(dst),
            scores=np.array(scores),
            matcher=self.name,
            meta={
                "detector": "rift2",
                "n_scales": self.n_scales,
                "n_orientations": self.n_orientations,
                "n_descriptors": (len(src_desc), len(ref_desc)),
            },
        )
