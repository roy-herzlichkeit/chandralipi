"""P0.08 — ECC fidelity, no mutation, gate, nodata mask (Phase_0/LLD/ecc.md). Protected (G05)."""

from __future__ import annotations

import numpy as np
import pytest
from _h0 import REPO, textured

PROBES = np.array([[40.0, 40.0], [200.0, 40.0], [40.0, 200.0], [200.0, 200.0], [128.0, 128.0]])


def _scene(matrix):
    import cv2

    src = textured((256, 256))
    if matrix.shape == (2, 3):
        ref = cv2.warpAffine(src, matrix, (256, 256), flags=cv2.INTER_CUBIC)
    else:
        ref = cv2.warpPerspective(src, matrix, (256, 256), flags=cv2.INTER_CUBIC)
    return src, ref


def _err(transform, truth):
    from lunar_reg.align.estimate import Transform

    t = Transform(truth, "homography" if truth.shape == (3, 3) else "affine", 1, 1)
    return float(np.abs(transform.apply(PROBES) - t.apply(PROBES)).max())


def test_homography_regression():
    from lunar_reg.align.estimate import Transform
    from lunar_reg.align.refine import EccStatus, ecc_refine

    H = np.array([[1.01, 0.02, 4.0], [-0.01, 0.995, -2.0], [1e-5, -1e-5, 1.0]])
    src, ref = _scene(H)
    start = H.copy()
    start[0, 2] += 0.6
    out = ecc_refine(Transform(start, "homography", 40, 40), src, ref)
    assert out.status is EccStatus.APPLIED and out.motion == "homography"
    assert out.transform.matrix.shape == (3, 3)
    assert _err(out.transform, H) < 0.1
    assert np.isfinite(out.cc) and out.shift_px is not None


def test_partial_affine_skipped():
    from lunar_reg.align.estimate import Transform
    from lunar_reg.align.refine import EccStatus, ecc_refine

    M = np.array([[1.0, 0.0, 3.0], [0.0, 1.0, 1.0]])
    src, ref = _scene(M)
    t = Transform(M.copy(), "partial_affine", 10, 10)
    out = ecc_refine(t, src, ref)
    assert out.status is EccStatus.SKIPPED_NO_SIMILARITY_MOTION
    assert np.array_equal(out.transform.matrix, M) and np.isnan(out.cc)


@pytest.mark.parametrize("dtype", [np.uint8, np.float32])
def test_inputs_not_mutated(dtype):
    from lunar_reg.align.estimate import Transform
    from lunar_reg.align.refine import ecc_refine

    A = np.array([[1.0, 0.01, 2.0], [0.0, 1.0, 1.0]])
    src, ref = _scene(A)
    src, ref = src.astype(dtype), ref.astype(dtype)
    before = src.tobytes(), ref.tobytes()
    ecc_refine(Transform(A.copy(), "affine", 10, 10), src, ref, prefilter="local_contrast")
    assert (src.tobytes(), ref.tobytes()) == before


def test_displacement_gate(monkeypatch):
    import cv2

    from lunar_reg.align.estimate import Transform
    from lunar_reg.align.refine import EccStatus, ecc_refine

    H = np.eye(3)
    src, ref = _scene(H)

    def jump(template, image, warp, motion, criteria, mask, blur):
        w = np.array(warp, dtype=np.float32).copy()
        w[0, 2] += 10.0
        return 0.99, w

    monkeypatch.setattr(cv2, "findTransformECC", jump)
    out = ecc_refine(Transform(H.copy(), "homography", 10, 10), src, ref, max_shift_px=3.0)
    assert out.status is EccStatus.REJECTED_DISPLACEMENT
    assert np.array_equal(out.transform.matrix, H)
    assert out.shift_px == pytest.approx(10.0, abs=0.5) and np.isnan(out.cc)


def test_not_converged(monkeypatch):
    import cv2

    from lunar_reg.align.estimate import Transform
    from lunar_reg.align.refine import EccStatus, ecc_refine

    src, ref = _scene(np.eye(3))

    def boom(*args, **kwargs):
        raise cv2.error("ECC did not converge")

    monkeypatch.setattr(cv2, "findTransformECC", boom)
    out = ecc_refine(Transform(np.eye(3), "homography", 10, 10), src, ref)
    assert out.status is EccStatus.NOT_CONVERGED and np.isnan(out.cc)


def test_nodata_mask():
    from lunar_reg.align.estimate import Transform
    from lunar_reg.align.refine import EccStatus, ecc_refine

    A = np.array([[1.0, 0.0, 3.0], [0.0, 1.0, -2.0]])
    src, ref = _scene(A)
    src = src.copy()
    src[:, :40] = 0
    start = A.copy()
    start[:, 2] += (0.5, 0.3)
    out = ecc_refine(Transform(start, "affine", 10, 10), src, ref, nodata=0)
    assert out.status is EccStatus.APPLIED
    assert _err(out.transform, A) < 0.2


def test_explicit_masks_use_with_mask(monkeypatch):
    """Review RC14 / G39: both validity masks reach cv2.findTransformECCWithMask."""
    import cv2

    from lunar_reg.align.estimate import Transform
    from lunar_reg.align.refine import EccStatus, ecc_refine

    A = np.array([[1.0, 0.0, 3.0], [0.0, 1.0, -2.0]])
    src, ref = _scene(A)
    ref_valid = np.ones(ref.shape, bool)
    ref_valid[:, 200:] = False
    seen = {}
    real = cv2.findTransformECCWithMask

    def spy(template, image, tmask, imask, warp, *args, **kwargs):
        seen["tmask"] = np.array(tmask)
        return real(template, image, tmask, imask, warp, *args, **kwargs)

    monkeypatch.setattr(cv2, "findTransformECCWithMask", spy)
    start = A.copy()
    start[:, 2] += (0.4, 0.2)
    out = ecc_refine(Transform(start, "affine", 10, 10), src, ref,
                     source_valid=np.ones(src.shape, bool), reference_valid=ref_valid)
    assert "tmask" in seen, "findTransformECCWithMask was not used"
    assert (seen["tmask"][:, 210:] == 0).all() and (seen["tmask"][:, :150] > 0).all()
    assert out.status is EccStatus.APPLIED


def test_wrapper_and_docstring():
    from lunar_reg.align.estimate import Transform
    from lunar_reg.align.refine import refine_transform_ecc

    A = np.array([[1.0, 0.0, 3.0], [0.0, 1.0, -2.0]])
    src, ref = _scene(A)
    t, cc = refine_transform_ecc(Transform(A.copy(), "affine", 10, 10), src, ref)
    assert t.matrix.shape == (2, 3) and np.isfinite(cc)
    text = (REPO / "src/lunar_reg/align/refine.py").read_text()
    assert "why it defaults on" not in text
    from lunar_reg.align import refine

    assert refine.ECC_PREFILTER_SIGMA_SOURCE.value == "inferred"
