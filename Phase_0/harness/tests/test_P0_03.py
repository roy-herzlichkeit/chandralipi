"""P0.03 — one shadow_mask, one scale-ratio limit (Phase_0/LLD/dedupe_and_removals.md). Protected (G05)."""

from __future__ import annotations

import re

import numpy as np
from _h0 import REPO


def test_single_shadow_mask():
    import lunar_reg.preprocess as pre
    import lunar_reg.preprocess.radiometric as radiometric
    from lunar_reg.preprocess.shadow import shadow_mask

    assert "shadow_mask" not in vars(radiometric) or radiometric.shadow_mask is shadow_mask
    assert not re.search(r"^def shadow_mask", (REPO / "src/lunar_reg/preprocess/radiometric.py")
                         .read_text(), re.M)
    assert pre.shadow_mask is shadow_mask


def test_suppress_shadows_behaviour():
    from lunar_reg.preprocess.radiometric import suppress_shadows

    img = np.arange(100, dtype=np.float32).reshape(10, 10)
    out = suppress_shadows(img, percentile=10.0)
    assert out.shape == img.shape and out.dtype == np.float32
    dark = img <= np.percentile(img, 10.0)
    assert np.all(out[dark] == np.median(img[~dark]))
    assert np.array_equal(out[~dark], img[~dark])


def test_scale_ratio_single_source():
    import lunar_reg.constants as constants
    from lunar_reg.ingest import pseudo_gt

    assert not hasattr(constants, "scale_ratio")
    assert pseudo_gt.MAX_DIRECT_SCALE_RATIO == constants.MAX_SAFE_SCALE_RATIO == 8.0
    text = (REPO / "src/lunar_reg/ingest/pseudo_gt.py").read_text()
    assert not re.search(r"^MAX_DIRECT_SCALE_RATIO\s*(:\s*float)?\s*=\s*8", text, re.M)
    assert pseudo_gt.scale_ratio("OHRC", "TMC2") is not None
