"""P2.06 — tiling extras (Phase_2/LLD/tiling.md §P2.06). Protected (G05)."""

from __future__ import annotations

import numpy as np
import pytest
from _h2 import cuda_available, terrain


def test_offset_prior_equivalence():
    from lunar_reg.match.classical import ClassicalMatcher
    from lunar_reg.match.tiled import TiledMatcher

    img = terrain((512, 512))
    ref = np.zeros((560, 560), np.uint8)
    ref[20:532, 30:542] = img
    tm = TiledMatcher(ClassicalMatcher("sift"), tile_px=256, progress=False)
    a = tm.match_arrays(img, ref, offset_prior=(20, 30))
    b = tm.match_arrays(img, ref, prior=np.array([[1.0, 0, 30], [0, 1.0, 20], [0, 0, 1.0]]))
    assert len(a) == len(b) and len(a) > 20
    assert np.median(np.abs(a.dst_pts - a.src_pts - (30, 20))) < 0.5


def test_nodata_tiles_skipped():
    from lunar_reg.match.classical import ClassicalMatcher
    from lunar_reg.match.tiled import TiledMatcher

    img = terrain((512, 512))
    src = img.copy()
    src[:, 256:] = 0
    tm = TiledMatcher(ClassicalMatcher("sift"), tile_px=256, overlap=0.0, progress=False)
    tm.match_arrays(src, img)
    assert tm.last_diagnostics.counts.get("skipped_nodata") == 2


def test_oom_tile():
    import torch

    from lunar_reg.match.tiled import TiledMatcher

    class OOM:
        name = "oom"

        def match(self, s, r):
            raise torch.OutOfMemoryError("CUDA out of memory")

    tm = TiledMatcher(OOM(), tile_px=256, overlap=0.0, progress=False)
    tm.match_arrays(terrain((256, 512)), terrain((256, 512)))
    assert tm.last_diagnostics.counts == {"oom": 2}


@pytest.mark.gpu
@pytest.mark.weights
def test_lightglue_scores_passed_through():
    if not cuda_available():
        pytest.skip("CUDA not available")
    from lunar_reg.match.learned import LightGlueMatcher

    img = terrain((256, 256))
    res = LightGlueMatcher(device="cuda", max_keypoints=256).match(img, img)
    assert res.scores is not None and len(res.scores) == len(res)


def test_loftr_reference_guard():
    from lunar_reg.match.learned import LoFTRMatcher

    m = LoFTRMatcher(device="cpu")
    big = np.zeros((m.max_tile_px + 64, 64), np.uint8)
    with pytest.raises(ValueError):
        m.match(np.zeros((64, 64), np.uint8), big)
