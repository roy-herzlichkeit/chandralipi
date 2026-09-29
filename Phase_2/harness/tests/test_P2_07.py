"""P2.07 — caps and memory guards (Phase_2/LLD/tiling.md §P2.07). Protected (G05)."""

from __future__ import annotations

import numpy as np
import pytest
from _h2 import terrain


def test_akaze_cap():
    from lunar_reg.match.classical import ClassicalMatcher

    m = ClassicalMatcher("akaze", max_features=100)
    img = terrain((512, 512))
    kps = m.detect(img)
    kp_list = kps[0] if isinstance(kps, tuple) else kps
    assert len(kp_list) <= 100


def test_rift2_cap():
    from lunar_reg.match.rift2.matcher import RIFT2Matcher

    m = RIFT2Matcher(max_tile_px=128)
    assert m.max_tile_px == 128
    with pytest.raises(ValueError, match="128"):
        m.match(np.ones((256, 256), np.uint8), np.ones((256, 256), np.uint8))


def test_to_uint8_lo_hi():
    from lunar_reg.preprocess.radiometric import to_uint8

    a = np.array([[5.0, 10.0, 15.0, 20.0, 30.0]], np.float32)
    out = to_uint8(a, lo_hi=(10.0, 20.0))
    assert out[0, 1] == 0 and out[0, 3] == 255 and out[0, 4] == 255


def test_to_uint8_memory():
    import tracemalloc

    from lunar_reg.preprocess.radiometric import to_uint8

    a = np.random.default_rng(0).uniform(0, 1000, (7000, 7000)).astype(np.float32)
    tracemalloc.start()
    to_uint8(a)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert peak < 2 * a.nbytes
