"""ECC keeps the motion model, never mutates inputs, gates jumps and honours validity masks."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from lunar_reg.align.estimate import Transform
from lunar_reg.align.refine import EccStatus, ecc_refine, refine_full
from lunar_reg.match.base import MatchResult

PROBES = np.array([[40.0, 40.0], [200.0, 40.0], [40.0, 200.0], [200.0, 200.0], [128.0, 128.0]])
AFFINE = np.array([[1.02, 0.03, 5.0], [-0.02, 0.99, -3.0]])
HOMOGRAPHY = np.array([[1.01, 0.02, 4.0], [-0.01, 0.995, -2.0], [1e-5, -1e-5, 1.0]])


def _texture(shape=(256, 256), seed=7) -> np.ndarray:
    noise = np.random.default_rng(seed).normal(0, 1, shape).astype(np.float32)
    blurred = cv2.GaussianBlur(noise, (0, 0), 2.0)
    scaled = (blurred - blurred.min()) / (blurred.max() - blurred.min())
    return (scaled * 255).astype(np.uint8)


def _scene(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    src = _texture()
    if matrix.shape == (2, 3):
        ref = cv2.warpAffine(src, matrix, (256, 256), flags=cv2.INTER_CUBIC)
    else:
        ref = cv2.warpPerspective(src, matrix, (256, 256), flags=cv2.INTER_CUBIC)
    return src, ref


def _probe_error(transform: Transform, truth: np.ndarray) -> float:
    model = "homography" if truth.shape == (3, 3) else "affine"
    want = Transform(truth, model, 1, 1).apply(PROBES)
    return float(np.abs(transform.apply(PROBES) - want).max())


def test_affine_in_affine_out():
    src, ref = _scene(AFFINE)
    start = AFFINE.copy()
    start[:, 2] += (0.6, -0.4)
    out = ecc_refine(Transform(start, "affine", 50, 50, estimator="RANSAC", seed=4), src, ref)
    assert out.status is EccStatus.APPLIED
    assert out.motion == "affine"
    assert out.transform.model == "affine" and out.transform.matrix.shape == (2, 3)
    assert out.transform.estimator == "RANSAC" and out.transform.seed == 4
    assert _probe_error(out.transform, AFFINE) < 0.1
    assert np.isfinite(out.cc) and out.shift_px is not None


def test_homography_regression():
    src, ref = _scene(HOMOGRAPHY)
    start = HOMOGRAPHY.copy()
    start[0, 2] += 0.6
    out = ecc_refine(Transform(start, "homography", 40, 40), src, ref)
    assert out.status is EccStatus.APPLIED and out.motion == "homography"
    assert out.transform.matrix.shape == (3, 3)
    assert _probe_error(out.transform, HOMOGRAPHY) < 0.1


def test_partial_affine_is_skipped_unchanged():
    similarity = np.array([[1.0, 0.0, 3.0], [0.0, 1.0, 1.0]])
    src, ref = _scene(similarity)
    transform = Transform(similarity.copy(), "partial_affine", 10, 10)
    out = ecc_refine(transform, src, ref)
    assert out.status is EccStatus.SKIPPED_NO_SIMILARITY_MOTION
    assert out.transform is transform
    assert np.array_equal(out.transform.matrix, similarity)
    assert np.isnan(out.cc) and out.motion is None


@pytest.mark.parametrize("dtype", [np.uint8, np.float32])
@pytest.mark.parametrize("prefilter", ["none", "local_contrast", "auto"])
def test_inputs_are_not_mutated(dtype, prefilter):
    src, ref = _scene(AFFINE)
    src, ref = src.astype(dtype), ref.astype(dtype)
    before = src.tobytes(), ref.tobytes()
    ecc_refine(Transform(AFFINE.copy(), "affine", 10, 10), src, ref, prefilter=prefilter)
    assert (src.tobytes(), ref.tobytes()) == before


def test_displacement_gate_rejects_a_jump(monkeypatch):
    src, ref = _scene(np.eye(3))

    def jump(template, image, warp, motion, criteria, mask, blur):
        moved = np.array(warp, dtype=np.float32).copy()
        moved[0, 2] += 10.0
        return 0.99, moved

    monkeypatch.setattr(cv2, "findTransformECC", jump)
    transform = Transform(np.eye(3), "homography", 10, 10)
    out = ecc_refine(transform, src, ref, max_shift_px=3.0)
    assert out.status is EccStatus.REJECTED_DISPLACEMENT
    assert out.transform is transform
    assert out.shift_px == pytest.approx(10.0, abs=0.5)
    assert np.isnan(out.cc)
    assert "gate" in out.detail


def test_not_converged_keeps_input(monkeypatch):
    src, ref = _scene(np.eye(3))

    def fail(*args, **kwargs):
        raise cv2.error("did not converge")

    monkeypatch.setattr(cv2, "findTransformECC", fail)
    transform = Transform(np.eye(3), "homography", 10, 10)
    out = ecc_refine(transform, src, ref)
    assert out.status is EccStatus.NOT_CONVERGED and out.transform is transform
    assert np.isnan(out.cc) and out.detail


def test_singular_transform_is_skipped():
    src, ref = _scene(np.eye(3))
    transform = Transform(np.zeros((3, 3)), "homography", 10, 10)
    out = ecc_refine(transform, src, ref)
    assert out.status is EccStatus.SKIPPED_SINGULAR and out.transform is transform


def test_nodata_border_is_masked():
    translation = np.array([[1.0, 0.0, 3.0], [0.0, 1.0, -2.0]])
    src, ref = _scene(translation)
    src = src.copy()
    src[:, :40] = 0
    start = translation.copy()
    start[:, 2] += (0.5, 0.3)
    out = ecc_refine(Transform(start, "affine", 10, 10), src, ref, nodata=0)
    assert out.status is EccStatus.APPLIED
    assert _probe_error(out.transform, translation) < 0.2


def test_explicit_masks_reach_find_transform_ecc_with_mask(monkeypatch):
    translation = np.array([[1.0, 0.0, 3.0], [0.0, 1.0, -2.0]])
    src, ref = _scene(translation)
    reference_valid = np.ones(ref.shape, bool)
    reference_valid[:, 200:] = False
    seen: dict = {}
    real = cv2.findTransformECCWithMask

    def spy(template, image, template_mask, input_mask, warp, *args):
        seen["template_mask"] = np.array(template_mask)
        seen["input_mask"] = np.array(input_mask)
        return real(template, image, template_mask, input_mask, warp, *args)

    def forbidden(*args, **kwargs):
        raise AssertionError("findTransformECC must not be used when masks are given")

    monkeypatch.setattr(cv2, "findTransformECCWithMask", spy)
    monkeypatch.setattr(cv2, "findTransformECC", forbidden)
    start = translation.copy()
    start[:, 2] += (0.4, 0.2)
    out = ecc_refine(
        Transform(start, "affine", 10, 10),
        src,
        ref,
        source_valid=np.ones(src.shape, bool),
        reference_valid=reference_valid,
    )
    assert out.status is EccStatus.APPLIED
    assert (seen["template_mask"][:, 205:] == 0).all()
    assert (seen["template_mask"][:, :150] == 255).all()
    assert seen["input_mask"].dtype == np.uint8


def test_refine_full_detail_keys_and_no_mutation():
    src, ref = _scene(AFFINE)
    pts = np.random.default_rng(1).uniform(20, 230, (60, 2))
    dst = np.c_[pts, np.ones(60)] @ AFFINE.T
    matches = MatchResult(pts, dst)  # no inlier mask yet
    transform, refit, detail = refine_full(matches, src, ref, model="affine", seed=0)

    for key in (
        "stages",
        "inliers_after_refit",
        "pre_ecc_matrix",
        "ecc_status",
        "ecc_motion",
        "ecc_cc",
        "ecc_shift_px",
    ):
        assert key in detail, key
    assert "ecc_skipped" not in detail
    assert detail["ecc_status"] == EccStatus.APPLIED.value
    assert detail["stages"] == ["reestimate_on_inliers", "ecc"]
    assert detail["pre_ecc_matrix"].shape == (2, 3)
    assert transform.matrix.shape == (2, 3)
    assert matches.inlier_mask is None, "refine_full must not write the caller's result"
    assert refit is not matches

    _, _, off = refine_full(matches, None, None, model="affine")
    assert off["ecc_status"] == EccStatus.SKIPPED_DISABLED.value
    assert off["ecc_cc"] is None and off["ecc_shift_px"] is None
