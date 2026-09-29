"""Phase 1B contract tests: C21 (G16). Protected (G05)."""

from __future__ import annotations

import dataclasses

import numpy as np
from _h1b import dtm, matches_under

H = np.array([[1.01, 0.02, 12.0], [-0.015, 0.99, -7.0], [1e-5, -2e-5, 1.0]])


def test_C21_render_uint8():
    from lunar_reg.eval.render import render_shaded_relief

    d = dtm()
    d[0, :5] = np.nan
    img = render_shaded_relief(d, 3.0, 120.0, 20.0)
    assert img.dtype == np.uint8 and img.shape == d.shape
    assert (img[0, :5] == 0).all() and (img[5:, 5:] >= 1).all()
    flat = render_shaded_relief(np.zeros((32, 32)), 3.0, 45.0, 30.0, cast_shadows=False, ambient=0.04)
    expect = 1 + 254 * (0.04 + 0.96 * np.sin(np.radians(30.0)))
    assert abs(float(flat.mean()) - expect) <= 1.0


def test_C21_members():
    from lunar_reg.consensus import ConsensusResult, ConsensusStatus

    assert {m.value for m in ConsensusStatus} == {"ok", "too_few_matchers", "disagreement",
                                                  "estimation_failed"}
    assert [f.name for f in dataclasses.fields(ConsensusResult)] == [
        "status", "transform", "per_matcher", "pooled", "agreement", "contributing", "detail"]


def test_C21_consensus_agree():
    from lunar_reg.consensus import ConsensusStatus, pooled_consensus

    res = {name: matches_under(H, seed=i) for i, name in enumerate(("sift", "akaze", "orb"))}
    out = pooled_consensus(res, (400, 400))
    assert out.status is ConsensusStatus.OK and out.contributing == ["akaze", "orb", "sift"]
    probes = np.array([[0.0, 0.0], [399.0, 0.0], [0.0, 399.0], [399.0, 399.0]])
    truth = np.c_[probes, np.ones(4)] @ H.T
    got = out.transform.apply(probes)
    assert np.abs(got - truth[:, :2] / truth[:, 2:]).max() < 0.2


def test_C21_consensus_disagree():
    from lunar_reg.consensus import ConsensusStatus, pooled_consensus

    res = {"a": matches_under(H, seed=1), "b": matches_under(H, seed=2, offset=(5.0, 0.0)),
           "c": matches_under(H, seed=3, offset=(0.0, -5.0))}
    out = pooled_consensus(res, (400, 400))
    assert out.status is ConsensusStatus.DISAGREEMENT and out.transform is None
    one = pooled_consensus({"a": matches_under(H)}, (400, 400))
    assert one.status is ConsensusStatus.TOO_FEW_MATCHERS
    two_of_three = {"a": matches_under(H, seed=1), "b": matches_under(H, seed=2),
                    "c": matches_under(H, seed=3, offset=(5.0, 0.0))}
    out = pooled_consensus(two_of_three, (400, 400))
    assert out.status is ConsensusStatus.OK and out.contributing == ["a", "b"]
