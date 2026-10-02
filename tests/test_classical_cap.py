"""Keypoint cap before BFMatcher (Phase_1/LLD/asift_cap.md §2, DECISIONS G42)."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from lunar_reg.match.classical import (
    ASIFT_MAX_TOTAL_KEYPOINTS,
    BF_TRAIN_LIMIT,
    ClassicalMatcher,
)

CAP_META = (
    "max_total_keypoints",
    "n_keypoints_src_raw",
    "n_keypoints_ref_raw",
    "keypoints_capped_src",
    "keypoints_capped_ref",
)


def _fake_features(n: int, seed: int):
    """``n`` keypoints with distinct responses and random SIFT-like float descriptors."""
    rng = np.random.default_rng(seed)
    xy = rng.uniform(0, 255, (n, 2))
    response = rng.permutation(n).astype(np.float32) + 1.0
    keypoints = [
        cv2.KeyPoint(float(x), float(y), 3.0, -1, float(r))
        for (x, y), r in zip(xy, response, strict=True)
    ]
    return keypoints, rng.random((n, 128), dtype=np.float32)


def _textured(seed: int = 7) -> np.ndarray:
    g = np.random.default_rng(seed).normal(0, 1, (256, 256)).astype(np.float32)
    g = cv2.GaussianBlur(g, (0, 0), 2.0)
    return ((g - g.min()) / (g.max() - g.min()) * 255).astype(np.uint8)


def test_oversized_keypoint_sets_are_capped_and_matched():
    """More than BF_TRAIN_LIMIT train rows used to raise inside knnMatch (Q-P1.18-3)."""
    m = ClassicalMatcher("sift", max_total_keypoints=1000)
    feats = iter([_fake_features(270_000, 1), _fake_features(270_000, 2)])
    m.detect = lambda image: next(feats)
    out = m.match(np.zeros((8, 8), np.uint8), np.zeros((8, 8), np.uint8))
    meta = out.meta
    assert meta["keypoints_capped_src"] is True and meta["keypoints_capped_ref"] is True
    assert meta["n_keypoints_src_raw"] == 270_000 and meta["n_keypoints_ref_raw"] == 270_000
    assert meta["max_total_keypoints"] == 1000
    if "n_keypoints" in meta:
        assert meta["n_keypoints"] == (1000, 1000)


def test_cap_is_deterministic_keeps_strongest_and_preserves_order():
    m = ClassicalMatcher("sift", max_total_keypoints=100)
    kps, des = _fake_features(5000, 3)
    a = m._cap(kps, des)
    b = m._cap(kps, des)
    kept, kept_des, raw, capped = a
    assert raw == 5000 and capped is True and len(kept) == 100 and kept_des.shape == (100, 128)
    assert [k.pt for k in kept] == [k.pt for k in b[0]]
    assert np.array_equal(kept_des, b[1])
    top = sorted((k.response for k in kps), reverse=True)[:100]
    assert sorted(k.response for k in kept) == sorted(top)
    index = {k.pt: i for i, k in enumerate(kps)}
    order = [index[k.pt] for k in kept]
    assert order == sorted(order)
    # descriptors stay paired with their keypoints
    assert np.array_equal(kept_des, des[order])


def test_cap_below_limit_returns_inputs_unchanged():
    m = ClassicalMatcher("sift", max_total_keypoints=100)
    kps, des = _fake_features(50, 4)
    kept, kept_des, raw, capped = m._cap(kps, des)
    assert raw == 50 and capped is False and kept_des is des
    assert [k.pt for k in kept] == [k.pt for k in kps]


def test_defaults():
    assert ClassicalMatcher("asift").max_total_keypoints == ASIFT_MAX_TOTAL_KEYPOINTS == 50_000
    for name in ("sift", "akaze", "orb"):
        assert ClassicalMatcher(name).max_total_keypoints == BF_TRAIN_LIMIT
    assert ClassicalMatcher("asift", max_total_keypoints=2000).max_total_keypoints == 2000


@pytest.mark.parametrize("bad", [BF_TRAIN_LIMIT + 1, 1, 0])
def test_validation(bad):
    with pytest.raises(ValueError, match="max_total_keypoints"):
        ClassicalMatcher("sift", max_total_keypoints=bad)


def test_matches_unchanged_below_the_cap():
    src = _textured()
    ref = np.roll(src, (3, 5), axis=(0, 1))
    default = ClassicalMatcher("sift").match(src, ref)
    explicit = ClassicalMatcher("sift", max_total_keypoints=None).match(src, ref)
    assert len(default) > 20
    assert np.array_equal(default.src_pts, explicit.src_pts)
    assert np.array_equal(default.dst_pts, explicit.dst_pts)
    for key in CAP_META:
        assert key in default.meta, key
    assert default.meta["keypoints_capped_src"] is False
    assert default.meta["keypoints_capped_ref"] is False


def test_empty_results_carry_cap_meta():
    blank = np.zeros((64, 64), np.uint8)
    out = ClassicalMatcher("sift").match(blank, blank)
    assert len(out) == 0 and out.meta["empty_reason"] == "too_few_keypoints"
    for key in CAP_META:
        assert key in out.meta, key
