"""P1B.04 — RIFT2 fixes (Phase_1B/LLD/rift2.md). Protected (G05)."""

from __future__ import annotations

import re

import numpy as np
from _h1b import REPO


def test_claims_removed():
    for path in (REPO / "src/lunar_reg/match/rift2").glob("*.py"):
        text = path.read_text()
        for m in re.finditer(r"rotation[- ]invariant", text, re.I):
            before = text[max(0, m.start() - 4):m.start()]
            assert before.lower().endswith("not "), f"{path.name}: claim left at {m.start()}"


def test_no_duplicates():
    from lunar_reg.eval.scenes import illumination_pair
    from lunar_reg.match.rift2.matcher import RIFT2Matcher

    src, ref, _, _ = illumination_pair(shape=(192, 192), seed=1, source_sun=(300, 30),
                                       reference_sun=(300, 30))
    m = RIFT2Matcher(max_keypoints=300)
    pts, _desc = m.detect_and_describe(src)
    # dominant-index doubling may repeat a point with a second descriptor; distinct points
    # (after deduplicating the corner/edge union) must respect the cap (A125)
    distinct = {tuple(np.round(p, 6)) for p in np.asarray(pts).reshape(-1, 2)}
    assert 0 < len(distinct) <= 300
    res = m.match(src, ref)
    if len(res):
        keys = [tuple(p) for p in np.round(res.src_pts, 6)]
        assert len(keys) == len(set(keys))
