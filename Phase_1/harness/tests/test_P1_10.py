"""P1.10 — presets inside register_pair + ablation rule (Phase_1/LLD/preprocess_presets.md). Protected (G05)."""

from __future__ import annotations

import numpy as np
import pytest
from _h1 import illumination


def test_all_zero_input_not_ok():
    from lunar_reg.preprocess.presets import apply_preset

    z = np.zeros((64, 64), np.uint8)
    out = apply_preset("ohrc_nac", z, z)
    assert out.ok is False and out.source is None and out.detail


def test_register_pair_records_preset():
    from lunar_reg.pipeline import PipelineConfig, RunStatus, register_pair

    src, ref, _, _ = illumination(seed=1)
    out = register_pair(src, ref, "pp", PipelineConfig(matcher="sift", preprocess="clahe_shadow",
                                                       n_bootstrap=0))
    assert out.status is RunStatus.OK, out.detail
    assert out.result.extra["preprocess"] == "clahe_shadow"
    assert "preprocess_placeholders" in out.result.extra
    assert np.array_equal(out.result.source_image, src)  # thumbnails keep the input image


def test_preprocess_failure_classified(monkeypatch):
    from lunar_reg.pipeline import PipelineConfig, RunStatus, register_pair
    from lunar_reg.preprocess import presets

    def failing(name, source, reference, **kw):
        return presets.PresetOutcome(False, None, None, "clahe: degenerate_output", [], [])

    monkeypatch.setattr(presets, "apply_preset", failing)
    src, ref, _, _ = illumination(seed=2)
    out = register_pair(src, ref, "pf", PipelineConfig(matcher="sift", preprocess="ohrc_nac"))
    assert out.status is RunStatus.PREPROCESS_FAILED and out.extra["stage"] == "preprocess"


def _abl(anchor, synthetic):
    return {"anchor": [dict(preset=p, matcher=m, status=s, n_inliers=n, u_score=u)
                       for p, m, s, n, u in anchor],
            "synthetic": [dict(preset=p, matcher="sift", azimuth_delta_deg=0, seed=0, status="ok",
                               truth_rms_px=t) for p, t in synthetic]}


def test_choose_default_clear_anchor_winner():
    from lunar_reg.preprocess.presets import choose_default_preset

    abl = _abl([("none", "sift", "ok", 25, 0.8), ("ohrc_nac", "sift", "ok", 40, 0.9),
                ("ohrc_nac", "akaze", "ok", 30, 0.75), ("clahe_shadow", "sift", "ok", 10, 0.9)],
               [("none", 0.1), ("ohrc_nac", 0.5), ("clahe_shadow", 0.05)])
    winner, reason = choose_default_preset(abl)
    assert winner == "ohrc_nac" and "ohrc_nac" in reason


def test_choose_default_tie_broken_by_synthetic():
    from lunar_reg.preprocess.presets import choose_default_preset

    abl = _abl([("none", "sift", "ok", 25, 0.8), ("clahe_shadow", "sift", "ok", 30, 0.8),
                ("ohrc_nac", "sift", "too_few_matches", 0, 0.0)],
               [("none", 0.3), ("none", 0.5), ("clahe_shadow", 0.2), ("ohrc_nac", 0.01)])
    assert choose_default_preset(abl)[0] == "clahe_shadow"


def test_choose_default_full_tie_is_none():
    from lunar_reg.preprocess.presets import choose_default_preset

    abl = _abl([("none", "sift", "ok", 5, 0.1), ("ohrc_nac", "sift", "ok", 5, 0.1),
                ("clahe_shadow", "sift", "ok", 5, 0.1)], [])
    assert choose_default_preset(abl)[0] == "none"
