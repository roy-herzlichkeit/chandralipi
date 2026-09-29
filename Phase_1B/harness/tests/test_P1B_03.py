"""P1B.03 — register_consensus (Phase_1B/LLD/consensus.md §2). Protected (G05)."""

from __future__ import annotations

import numpy as np


def test_register_consensus_stubs(monkeypatch):
    import lunar_reg.match as match
    from lunar_reg.consensus import register_consensus
    from lunar_reg.eval.scenes import illumination_pair
    from lunar_reg.match.classical import ClassicalMatcher
    from lunar_reg.pipeline import PipelineConfig

    src, ref, _, _ = illumination_pair(shape=(320, 320), seed=3, source_sun=(300, 30),
                                       reference_sun=(300, 30))
    real = {n: ClassicalMatcher(n) for n in ("sift", "akaze")}
    monkeypatch.setattr(match, "build_matcher", lambda name, **kw: real[name])
    out = register_consensus(src, ref, "cons", ("sift", "akaze"), PipelineConfig(n_bootstrap=0))
    assert out.ok, out.detail
    assert out.result.matcher.startswith("consensus(")
    assert out.result.extra["consensus_status"] == "ok"
    assert set(out.result.extra["consensus_contributing"].split("+")) <= {"sift", "akaze"} or \
        isinstance(out.result.extra["consensus_contributing"], str)
    assert np.isfinite(out.result.metrics["rmse_px"])
