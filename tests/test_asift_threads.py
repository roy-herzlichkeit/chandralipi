"""ASIFT detection runs with at most ASIFT_DETECT_THREADS OpenCV threads (Q-P1.20-0, G18)."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from lunar_reg.match.classical import (
    ASIFT_DETECT_THREADS,
    ASIFT_DETECT_THREADS_SOURCE,
    ClassicalMatcher,
)
from lunar_reg.provenance import ValueSource


class _Recorder:
    """Detector stand-in that records the OpenCV thread count it ran under."""

    def __init__(self, fail: bool = False):
        self.seen: list[int] = []
        self.fail = fail

    def detectAndCompute(self, image, mask):  # noqa: N802 (OpenCV name)
        self.seen.append(cv2.getNumThreads())
        if self.fail:
            raise cv2.error("boom")
        return [], None


@pytest.fixture
def threads():
    before = cv2.getNumThreads()
    cv2.setNumThreads(16)
    yield
    cv2.setNumThreads(before)


def _image():
    g = np.random.default_rng(0).normal(0, 1, (160, 160)).astype(np.float32)
    g = cv2.GaussianBlur(g, (0, 0), 2.0)
    return ((g - g.min()) / (g.max() - g.min()) * 254 + 1).astype(np.uint8)


def test_constant_and_provenance():
    assert ASIFT_DETECT_THREADS == 4
    assert ASIFT_DETECT_THREADS_SOURCE is ValueSource.MEASURED


def test_asift_detection_is_capped_and_restored(threads):
    m = ClassicalMatcher("asift")
    m._detector = rec = _Recorder()
    m.detect(_image())
    assert rec.seen == [ASIFT_DETECT_THREADS]
    assert cv2.getNumThreads() == 16


def test_restored_when_detection_raises(threads):
    m = ClassicalMatcher("asift")
    m._detector = _Recorder(fail=True)
    with pytest.raises(cv2.error):
        m.detect(_image())
    assert cv2.getNumThreads() == 16


def test_a_lower_setting_is_kept(threads):
    cv2.setNumThreads(2)
    m = ClassicalMatcher("asift")
    m._detector = rec = _Recorder()
    m.detect(_image())
    assert rec.seen == [2] and cv2.getNumThreads() == 2


@pytest.mark.parametrize("name", ["sift", "akaze"])
def test_other_detectors_are_not_capped(threads, name):
    m = ClassicalMatcher(name)
    m._detector = rec = _Recorder()
    m.detect(_image())
    assert rec.seen == [16]


def test_asift_results_identical_to_uncapped_detection(threads):
    img = _image()
    kp_ref, des_ref = cv2.AffineFeature_create(cv2.SIFT_create(nfeatures=8192)).detectAndCompute(
        img, None
    )
    kp, des = ClassicalMatcher("asift").detect(img)
    assert len(kp) == len(kp_ref) > 0
    assert [k.pt for k in kp] == [k.pt for k in kp_ref]
    assert np.array_equal(des, des_ref)
