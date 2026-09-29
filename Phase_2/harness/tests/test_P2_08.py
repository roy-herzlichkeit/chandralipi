"""P2.08 — native refinement status rules (Phase_2/LLD/native.md §P2.08). Protected (G05)."""

from __future__ import annotations

import numpy as np


def test_status_members():
    from lunar_reg.align.native import NativeRefinement, NativeStatus

    assert {m.value for m in NativeStatus} == {"ok", "too_few_matches", "estimation_failed",
                                               "drift_exceeded", "tile_failures"}
    names = [f.name for f in __import__("dataclasses").fields(NativeRefinement)]
    assert names == ["status", "transform", "n_matches", "n_inliers", "drift_coarse_px", "tiles",
                     "detail"]


def test_blank_is_too_few_matches():
    from lunar_reg.align.native import NativeStatus, refine_native_arrays

    out = refine_native_arrays(np.zeros((512, 512), np.uint8), np.zeros((128, 128), np.uint8),
                               np.diag([0.25, 0.25, 1.0]), source_native_gsd_m=0.25,
                               reference_native_gsd_m=1.0, tile_px=128)
    assert out.status is NativeStatus.TOO_FEW_MATCHES and out.transform is None
