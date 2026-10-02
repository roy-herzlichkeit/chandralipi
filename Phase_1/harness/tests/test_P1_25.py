"""P1.25 — keypoint cap for BFMatcher (Phase_1/LLD/asift_cap.md). Protected (G05)."""

from __future__ import annotations

import numpy as np
import pytest


class _FakeDetector:
    """Returns n keypoints with distinct responses and random SIFT-like descriptors."""

    def __init__(self, n: int, seed: int):
        self.n, self.seed = n, seed

    def detectAndCompute(self, image, mask):  # noqa: N802 (OpenCV name)
        import cv2

        rng = np.random.default_rng(self.seed)
        xy = rng.uniform(0, 255, (self.n, 2))
        resp = rng.permutation(self.n).astype(np.float32) + 1.0
        kps = [cv2.KeyPoint(float(x), float(y), 3.0, -1, float(r))
               for (x, y), r in zip(xy, resp, strict=True)]
        return kps, rng.random((self.n, 128), dtype=np.float32)


def test_constants_and_provenance():
    from lunar_reg.match import classical
    from lunar_reg.provenance import ValueSource

    assert classical.BF_TRAIN_LIMIT == 262_143
    assert classical.BF_TRAIN_LIMIT_SOURCE is ValueSource.MEASURED
    assert classical.ASIFT_MAX_TOTAL_KEYPOINTS == 50_000
    assert classical.ASIFT_MAX_TOTAL_KEYPOINTS_SOURCE is ValueSource.INFERRED


def test_defaults_and_validation():
    from lunar_reg.match.classical import BF_TRAIN_LIMIT, ClassicalMatcher

    assert ClassicalMatcher("asift").max_total_keypoints == 50_000
    assert ClassicalMatcher("sift").max_total_keypoints == BF_TRAIN_LIMIT
    for bad in (BF_TRAIN_LIMIT + 1, 1):
        with pytest.raises(ValueError):
            ClassicalMatcher("sift", max_total_keypoints=bad)


def test_oversized_keypoint_sets_are_capped_not_crashed():
    """Q-P1.18-3: more than 262 143 train descriptors used to raise inside knnMatch."""
    from lunar_reg.match.classical import ClassicalMatcher

    m = ClassicalMatcher("sift", max_total_keypoints=1000)
    fakes = iter([_FakeDetector(270_000, 1), _FakeDetector(270_000, 2)])
    m.detect = lambda image: next(fakes).detectAndCompute(image, None)
    out = m.match(np.zeros((256, 256), np.uint8), np.zeros((256, 256), np.uint8))
    meta = out.meta
    assert meta["keypoints_capped_src"] is True and meta["keypoints_capped_ref"] is True
    assert meta["n_keypoints_src_raw"] == 270_000 and meta["n_keypoints_ref_raw"] == 270_000
    assert meta["max_total_keypoints"] == 1000


def test_cap_keeps_strongest_deterministically():
    from lunar_reg.match.classical import ClassicalMatcher

    m = ClassicalMatcher("sift", max_total_keypoints=100)
    kps, des = _FakeDetector(5000, 3).detectAndCompute(None, None)
    a = m._cap(kps, des)
    b = m._cap(kps, des)
    assert a[2] == 5000 and a[3] is True and len(a[0]) == 100 and a[1].shape == (100, 128)
    assert [k.pt for k in a[0]] == [k.pt for k in b[0]]
    kept = sorted(k.response for k in a[0])
    assert kept[0] > sorted(k.response for k in kps)[-101]
    pos = {k.pt: i for i, k in enumerate(kps)}
    idx = [pos[k.pt] for k in a[0]]
    assert idx == sorted(idx), "original keypoint order must be preserved"
