"""Training-free matchers behind one interface.

Covers three of the four classical baselines Makharia et al. evaluate -- SIFT,
ASIFT and AKAZE -- plus ORB, KAZE and BRISK, which come free with the same
OpenCV machinery and make useful extra comparison rows.

RIFT2, the fourth baseline, is implemented in :mod:`lunar_reg.match.rift2` as a
clean-room build from the papers -- it is a much larger algorithm than the
OpenCV-backed detectors here, and it is the only one of the four that survives
contrast inversion.

OpenCV version dependency
-------------------------
This project pins ``opencv-python<5``. OpenCV 5 removed AKAZE, KAZE and BRISK
from the main module, and ``opencv-contrib-python`` 5.0.0 does **not** restore
them -- verified, not assumed. Since AKAZE is one of the paper's baselines, the
pin is load-bearing. :func:`available_detectors` probes at runtime regardless,
so a mismatched environment reports the truth instead of failing obscurely.

All of these run on CPU, so none is affected by the 8 GB VRAM budget. That makes
this module the fallback when a tile is too large for a learned matcher.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from lunar_reg.match.base import MatchResult
from lunar_reg.provenance import ValueSource

logger = logging.getLogger(__name__)

#: Lowe's ratio. Tighter than the usual 0.8 because cross-modal pairs produce
#: many plausible-but-wrong second-nearest neighbours.
DEFAULT_RATIO = 0.75

#: Detectors this project knows how to build. Availability still depends on the
#: installed OpenCV -- always check :func:`available_detectors`.
DETECTORS = ("sift", "asift", "akaze", "kaze", "orb", "brisk")

#: The four classical baselines in Makharia et al. RIFT2 is available as the
#: clean-room implementation in `lunar_reg.match.rift2`.
PAPER_BASELINES = ("sift", "asift", "akaze", "rift2")

#: Largest train-descriptor count ``cv2.BFMatcher.knnMatch`` accepts: opencv 4.14.0
#: succeeds with 262 143 rows and asserts ``trainDescCollection[iIdx].rows <
#: IMGIDX_ONE`` at 262 144 (Phase_1/LLD/asift_cap.md, measured by the architect).
BF_TRAIN_LIMIT = 262_143
BF_TRAIN_LIMIT_SOURCE = ValueSource.MEASURED

#: ASIFT's total-keypoint cap per image: a chosen bound, about 5 s per match
#: direction (Phase_1/LLD/asift_cap.md, G42).
ASIFT_MAX_TOTAL_KEYPOINTS = 50_000
ASIFT_MAX_TOTAL_KEYPOINTS_SOURCE = ValueSource.INFERRED

#: OpenCV threads during ASIFT detection. ``cv2.AffineFeature`` runs SIFT over its
#: affine views in parallel and its peak RAM grows with the thread count: on a
#: 1834x1857 crop 1167 MB at 1 thread, 3670 MB at 4, 5595 MB at 8 (opencv 4.14.0,
#: data/processed/probes/asift_memory_20261002.txt); the default 24 threads froze the
#: 15 GiB host (Phase_1/QUESTIONS.md Q-P1.20-0, G18: host RAM <= 12 GB). Output is
#: identical at any thread count, so the cap changes only memory and time.
ASIFT_DETECT_THREADS = 4
ASIFT_DETECT_THREADS_SOURCE = ValueSource.MEASURED


@dataclass(frozen=True)
class DetectorInfo:
    """What a detector produces, which decides how its descriptors are compared."""

    name: str
    binary_descriptor: bool
    note: str = ""
    #: Default cap on total keypoints per image (None: only BF_TRAIN_LIMIT applies).
    max_total_keypoints: int | None = None

    @property
    def norm(self) -> int:
        """The OpenCV distance norm this detector's descriptors require.

        Binary descriptors (AKAZE/ORB/BRISK) need Hamming; float descriptors
        (SIFT/ASIFT/KAZE) need L2. Using L2 on binary descriptors does not error
        -- it silently returns poor matches, which is the failure mode this
        exists to prevent.
        """
        import cv2

        return cv2.NORM_HAMMING if self.binary_descriptor else cv2.NORM_L2


DETECTOR_INFO: dict[str, DetectorInfo] = {
    "sift": DetectorInfo("sift", False, "128-d float; the reference baseline."),
    "asift": DetectorInfo(
        "asift",
        False,
        "SIFT re-run over simulated affine warps (Yu & Morel). Far more robust to "
        "viewpoint change, several times slower, and yields many more keypoints. "
        "Total keypoints capped (strongest by response) because BFMatcher rejects "
        ">= 262 144 train rows (P1.25).",
        max_total_keypoints=ASIFT_MAX_TOTAL_KEYPOINTS,
    ),
    "akaze": DetectorInfo(
        "akaze",
        True,
        "61-byte binary M-LDB descriptor on a nonlinear scale space; edges survive "
        "smoothing better than in SIFT's Gaussian pyramid.",
    ),
    "kaze": DetectorInfo("kaze", False, "AKAZE's float-descriptor predecessor."),
    "orb": DetectorInfo("orb", True, "Fast binary baseline; weakest under scale change."),
    "brisk": DetectorInfo("brisk", True, "Binary; scale/rotation invariant."),
}


def _try_build(name: str, max_features: int = 128):
    """Attempt to construct a detector; return ``None`` if this build lacks it.

    Deliberately separate from :func:`build_detector`: that function's error
    message enumerates the alternatives, and calling back into it would recurse.
    """
    import cv2

    try:
        if name == "sift":
            return cv2.SIFT_create(nfeatures=max_features)
        if name == "asift":
            return cv2.AffineFeature_create(cv2.SIFT_create(nfeatures=max_features))
        if name == "orb":
            return cv2.ORB_create(nfeatures=max_features)
        factory = getattr(cv2, f"{name.upper()}_create", None)
        return None if factory is None else factory()
    except Exception:  # noqa: BLE001 - unavailable is an expected outcome here
        return None


def available_detectors() -> tuple[str, ...]:
    """Detectors the installed OpenCV build can actually construct."""
    return tuple(n for n in DETECTORS if _try_build(n) is not None)


def build_detector(name: str, max_features: int):
    """Construct a detector, or raise with an actionable message."""
    import cv2

    detector = _try_build(name, max_features)
    if detector is None:
        raise RuntimeError(
            f"detector {name!r} is not available in OpenCV {cv2.__version__}. "
            f"AKAZE, KAZE and BRISK left the main module in OpenCV 5, and "
            f"opencv-contrib-python 5.x does not restore them -- pin "
            f"'opencv-python>=4.9,<5' instead. "
            f"Available in this build: {', '.join(available_detectors())}."
        )
    return detector


class ClassicalMatcher:
    """Detect, describe, and ratio-test match with any supported OpenCV detector.

    Satisfies :class:`lunar_reg.match.base.Matcher`, so it is interchangeable
    with the learned matchers and with :class:`~lunar_reg.match.tiled.TiledMatcher`.
    """

    def __init__(
        self,
        detector: str = "sift",
        ratio: float = DEFAULT_RATIO,
        max_features: int = 8192,
        cross_check: bool = True,
        max_total_keypoints: int | None = None,
    ) -> None:
        self.detector_name = detector.lower()
        if self.detector_name not in DETECTORS:
            raise ValueError(f"unknown detector {detector!r}; expected one of {DETECTORS}")
        if max_total_keypoints is not None and not 2 <= max_total_keypoints <= BF_TRAIN_LIMIT:
            raise ValueError(
                f"max_total_keypoints must be in 2..{BF_TRAIN_LIMIT} (BFMatcher train limit), "
                f"got {max_total_keypoints}"
            )
        self.ratio = ratio
        self.max_features = max_features
        self.cross_check = cross_check
        self.name = f"classical/{self.detector_name}"
        self.info = DETECTOR_INFO[self.detector_name]
        self.max_total_keypoints = min(
            max_total_keypoints or self.info.max_total_keypoints or BF_TRAIN_LIMIT,
            BF_TRAIN_LIMIT,
        )
        self._detector = None

    def _get_detector(self):
        if self._detector is None:
            self._detector = build_detector(self.detector_name, self.max_features)
        return self._detector

    def detect(self, image: np.ndarray):
        """Keypoints and descriptors for one image."""
        from lunar_reg.preprocess.radiometric import to_uint8

        arr = image if image.dtype == np.uint8 else to_uint8(image)
        detector = self._get_detector()
        if self.detector_name != "asift":
            return detector.detectAndCompute(arr, None)
        import cv2

        previous = cv2.getNumThreads()
        cv2.setNumThreads(max(1, min(previous, ASIFT_DETECT_THREADS)))
        try:
            return detector.detectAndCompute(arr, None)
        finally:
            cv2.setNumThreads(previous)

    def _cap(self, keypoints, descriptors) -> tuple[list, np.ndarray | None, int, bool]:
        """Keep at most ``max_total_keypoints``, the strongest by response (G42).

        Returns ``(keypoints, descriptors, raw_count, capped)``. The kept ones
        stay in their original relative order, so the result is deterministic.
        """
        keypoints = list(keypoints or [])
        raw = len(keypoints)
        cap = self.max_total_keypoints
        if raw <= cap:
            return keypoints, descriptors, raw, False
        response = np.array([k.response for k in keypoints], dtype=np.float64)
        order = np.sort(np.argsort(-response, kind="stable")[:cap])
        kept_des = None if descriptors is None else np.asarray(descriptors)[order]
        return [keypoints[i] for i in order], kept_des, raw, True

    def _meta(self, **extra) -> dict:
        """Parameters every returned result carries, empty or not."""
        return {
            "detector": self.detector_name,
            "ratio": self.ratio,
            "max_features": self.max_features,
            "cross_check": self.cross_check,
            "max_total_keypoints": self.max_total_keypoints,
            **extra,
        }

    def match(self, source: np.ndarray, reference: np.ndarray) -> MatchResult:
        import cv2

        kp1, des1, raw1, capped1 = self._cap(*self.detect(source))
        kp2, des2, raw2, capped2 = self._cap(*self.detect(reference))
        cap_meta = {
            "n_keypoints_src_raw": raw1,
            "n_keypoints_ref_raw": raw2,
            "keypoints_capped_src": capped1,
            "keypoints_capped_ref": capped2,
        }
        if capped1 or capped2:
            logger.info(
                "%s: keypoints capped at %d (raw %d, %d)",
                self.name, self.max_total_keypoints, raw1, raw2,
            )  # fmt: skip

        if des1 is None or des2 is None or len(kp1) < 2 or len(kp2) < 2:
            logger.debug(
                "%s: too few keypoints (%d, %d)", self.name, len(kp1 or []), len(kp2 or [])
            )
            empty = MatchResult.empty(self.name)
            empty.meta = self._meta(
                empty_reason="too_few_keypoints",
                n_keypoints_src=len(kp1 or []),
                n_keypoints_ref=len(kp2 or []),
                **cap_meta,
            )
            return empty

        matcher = cv2.BFMatcher(self.info.norm)
        forward = self._ratio_test(matcher, des1, des2)

        if self.cross_check:
            # Symmetry test: keep only pairs that select each other. Cheap, and
            # it removes the many-to-one matches the ratio test alone allows,
            # which otherwise cluster on repetitive crater texture.
            backward = {(b, a) for a, b, _ in self._ratio_test(matcher, des2, des1)}
            forward = [m for m in forward if (m[0], m[1]) in backward]

        if not forward:
            empty = MatchResult.empty(self.name)
            empty.meta = self._meta(
                n_keypoints=(len(kp1), len(kp2)),
                empty_reason="no_ratio_survivors",
                n_keypoints_src=len(kp1),
                n_keypoints_ref=len(kp2),
                **cap_meta,
            )
            return empty

        src = np.array([kp1[i].pt for i, _, _ in forward])
        dst = np.array([kp2[j].pt for _, j, _ in forward])
        scores = np.array([s for _, _, s in forward])

        logger.debug("%s: %d matches from %d/%d keypoints", self.name, len(src), len(kp1), len(kp2))
        return MatchResult(
            src_pts=src,
            dst_pts=dst,
            scores=scores,
            matcher=self.name,
            meta=self._meta(n_keypoints=(len(kp1), len(kp2)), **cap_meta),
        )

    def _ratio_test(self, matcher, query, train) -> list[tuple[int, int, float]]:
        """Lowe ratio test, returning ``(query_idx, train_idx, score)`` triples."""
        out: list[tuple[int, int, float]] = []
        for pair in matcher.knnMatch(query, train, k=2):
            if len(pair) < 2:
                continue
            best, second = pair
            if best.distance < self.ratio * second.distance:
                # Score in [0, 1); higher means the best match won by more.
                score = 1.0 - best.distance / max(second.distance, 1e-9)
                out.append((best.queryIdx, best.trainIdx, score))
        return out


# RIFT2 now lives in its own package -- it is a substantially larger algorithm
# than the OpenCV-backed detectors above (log-Gabor bank, phase congruency,
# Maximum Index Map). Re-exported here so callers can treat all the paper's
# classical baselines uniformly.
from lunar_reg.match.rift2 import RIFT2Matcher  # noqa: E402


def build_classical(name: str, **kwargs):
    """Construct any of the paper's classical matchers by name."""
    key = name.lower()
    if key == "rift2":
        return RIFT2Matcher(**kwargs)
    return ClassicalMatcher(detector=key, **kwargs)


def paper_baseline_status() -> dict[str, str]:
    """Which of the paper's four classical baselines this project can actually run."""
    have = set(available_detectors())
    return {
        name: (
            "available (clean-room implementation)"
            if name == "rift2"
            else "available"
            if name in have
            else "unavailable in this OpenCV build"
        )
        for name in PAPER_BASELINES
    }
