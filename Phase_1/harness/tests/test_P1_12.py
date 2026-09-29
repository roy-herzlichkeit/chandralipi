"""P1.12 — agreement helper for stored results (Phase_1/LLD/agreement.md §2). Protected (G05)."""

from __future__ import annotations

import numpy as np
import pytest


def _pr(matcher, dx, source_id="s", pre=True):
    from lunar_reg.results import PairResult

    pts = np.zeros((4, 2))
    H = np.array([[1.0, 0, dx], [0, 1.0, 0], [0, 0, 1.0]])
    return PairResult(f"p_{matcher}", source_id, "r", "A", "B", matcher, pts, pts, None, H,
                      source_image=np.zeros((50, 60), np.uint8),
                      pre_ecc_transform=H if pre else None, extra={"gsd_m": 4.0})


def test_agreement_for_stored():
    from lunar_reg.eval.agreement import agreement_for_stored

    a = agreement_for_stored([_pr("sift", 0.0), _pr("akaze", 0.5), _pr("orb", 9.0, pre=False)])
    assert a.n_matchers == 2 and a.max_disagreement_px == pytest.approx(0.5)
    assert a.max_disagreement_m == pytest.approx(2.0) and a.passes


def test_agreement_mixed_sources_rejected():
    from lunar_reg.eval.agreement import agreement_for_stored

    with pytest.raises(ValueError):
        agreement_for_stored([_pr("sift", 0.0), _pr("akaze", 0.0, source_id="other")])


def test_singular_skipped():
    from lunar_reg.eval.agreement import cross_matcher_agreement

    a = cross_matcher_agreement({"a": np.eye(3), "b": np.eye(3), "bad": np.zeros((3, 3))},
                                (20, 20))
    assert a.n_matchers == 2 and "bad" not in a.matchers
