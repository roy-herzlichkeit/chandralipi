"""Cross-matcher agreement (CONTRACTS.md C14, Phase_1/LLD/agreement.md §3)."""

from __future__ import annotations

import logging

import numpy as np
import pytest

from lunar_reg.eval.agreement import (
    AgreementResult,
    agreement_for_stored,
    cross_matcher_agreement,
)
from lunar_reg.results import PairResult


def _shift(dx: float, dy: float = 0.0) -> np.ndarray:
    return np.array([[1.0, 0.0, dx], [0.0, 1.0, dy], [0.0, 0.0, 1.0]])


def test_identical_transforms_zero_and_pass():
    a = cross_matcher_agreement({"sift": _shift(3, 2), "akaze": _shift(3, 2)}, (100, 120))
    assert isinstance(a, AgreementResult)
    assert a.max_disagreement_px == pytest.approx(0.0)
    assert a.passes and a.n_matchers == 2
    assert a.matchers == ("akaze", "sift")
    assert set(a.pairwise_px) == {"akaze|sift"}
    assert a.gsd_m is None and a.max_disagreement_m is None


def test_offset_0p6_passes():
    a = cross_matcher_agreement({"a": _shift(0), "b": _shift(0.6)}, (100, 100))
    assert a.max_disagreement_px == pytest.approx(0.6)
    assert a.passes


def test_offset_1p5_fails():
    a = cross_matcher_agreement({"a": _shift(0), "b": _shift(1.5)}, (100, 100))
    assert a.max_disagreement_px == pytest.approx(1.5)
    assert not a.passes


def test_single_transform_nan_and_fails():
    a = cross_matcher_agreement({"a": _shift(0)}, (100, 100))
    assert np.isnan(a.max_disagreement_px)
    assert not a.passes and a.n_matchers == 1 and a.pairwise_px == {}


def test_affine_vs_homography_of_same_affine():
    m = np.array([[1.01, 0.02, 4.0], [-0.03, 0.99, -2.0], [0.0, 0.0, 1.0]])
    a = cross_matcher_agreement({"h": m, "a": m[:2]}, (80, 60))
    assert a.max_disagreement_px == pytest.approx(0.0, abs=1e-9)
    assert a.passes


def test_gsd_gives_metres():
    a = cross_matcher_agreement({"a": _shift(0), "b": _shift(0.7)}, (50, 50), gsd_m=4.0)
    assert a.gsd_m == 4.0
    assert a.max_disagreement_m == pytest.approx(a.max_disagreement_px * 4.0)


def test_max_over_probes_and_pairs():
    # A 1 % scale about the origin moves the far corner (w-1, h-1) the most.
    scale = np.diag([1.01, 1.01, 1.0])
    a = cross_matcher_agreement({"a": _shift(0), "b": scale, "c": _shift(0.2)}, (101, 201))
    expected = np.hypot(2.0, 1.0)  # (200, 100) * 0.01
    assert a.pairwise_px["a|b"] == pytest.approx(expected)
    assert a.max_disagreement_px == pytest.approx(max(a.pairwise_px.values()))
    assert set(a.pairwise_px) == {"a|b", "a|c", "b|c"}


def test_singular_and_nonfinite_skipped(caplog):
    bad_nan = _shift(0)
    bad_nan[0, 2] = np.nan
    with caplog.at_level(logging.WARNING, logger="lunar_reg.eval.agreement"):
        a = cross_matcher_agreement(
            {"a": _shift(0), "b": _shift(0.1), "sing": np.zeros((3, 3)), "nan": bad_nan},
            (20, 20),
        )
    assert a.n_matchers == 2 and a.matchers == ("a", "b")
    assert "sing" in caplog.text and "nan" in caplog.text


def test_bad_shape_raises():
    with pytest.raises(ValueError):
        cross_matcher_agreement({"a": np.eye(2)}, (10, 10))


def _pr(matcher, dx, *, source_id="s", pre=True, scale=None, gsd=4.0):
    pts = np.zeros((4, 2))
    h = _shift(dx)
    extra = {"gsd_m": gsd}
    if scale is not None:
        extra["source_scale"] = scale
    return PairResult(
        f"p_{matcher}",
        source_id,
        "r",
        "A",
        "B",
        matcher,
        pts,
        pts,
        None,
        h,
        source_image=np.zeros((50, 60), np.uint8),
        pre_ecc_transform=h if pre else None,
        extra=extra,
    )


def test_stored_skips_v1_and_uses_gsd():
    a = agreement_for_stored([_pr("sift", 0.0), _pr("akaze", 0.5), _pr("orb", 9.0, pre=False)])
    assert a.n_matchers == 2 and "orb" not in a.matchers
    assert a.max_disagreement_px == pytest.approx(0.5)
    assert a.max_disagreement_m == pytest.approx(2.0)


def test_stored_uses_source_scale_for_shape():
    # Thumbnail 50x60 at scale 0.5 -> full shape 100x120; a 1 % scale moves (119, 99).
    s = np.diag([1.01, 1.01, 1.0])
    r1 = _pr("a", 0.0, scale=0.5)
    r2 = _pr("b", 0.0, scale=0.5)
    r2.pre_ecc_transform = s
    a = agreement_for_stored([r1, r2])
    assert a.max_disagreement_px == pytest.approx(np.hypot(1.19, 0.99))


def test_stored_mixed_pairs_rejected():
    with pytest.raises(ValueError):
        agreement_for_stored([_pr("sift", 0.0), _pr("akaze", 0.0, source_id="other")])


def test_stored_empty_or_all_v1():
    a = agreement_for_stored([_pr("orb", 0.0, pre=False)])
    assert a.n_matchers == 0 and np.isnan(a.max_disagreement_px) and not a.passes


def test_probe_mapping_to_non_finite_point_skipped(caplog):
    # Non-singular (det = -1) but the origin probe has w = 0 -> NaN after division.
    at_infinity = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, 1.0, 0.0]])
    with caplog.at_level(logging.WARNING, logger="lunar_reg.eval.agreement"):
        a = cross_matcher_agreement(
            {"a": _shift(0), "b": _shift(0.1), "inf": at_infinity}, (20, 20)
        )
    assert a.matchers == ("a", "b") and a.n_matchers == 2
    assert "inf" in caplog.text and "non-finite point" in caplog.text


def test_stored_duplicate_matcher_rejected():
    # Q-P1.12-1: names are matcher names, so two usable results of one matcher
    # (site-runner variants, e.g. `_pp-clahe_shadow`) raise rather than one
    # silently replacing the other.
    plain = _pr("sift", 0.0)
    variant = _pr("sift", 0.3)
    variant.pair_id = "p_sift_pp-clahe_shadow"
    with pytest.raises(ValueError, match="'sift' appears twice") as err:
        agreement_for_stored([plain, variant, _pr("akaze", 0.0)])
    assert "p_sift" in str(err.value) and "p_sift_pp-clahe_shadow" in str(err.value)


def test_stored_duplicate_matcher_only_counts_usable_results():
    # A v1 duplicate (no pre_ecc_transform) is skipped before the name check.
    a = agreement_for_stored([_pr("sift", 0.0), _pr("sift", 5.0, pre=False), _pr("akaze", 0.2)])
    assert a.matchers == ("akaze", "sift")
    assert a.max_disagreement_px == pytest.approx(0.2)


def test_stored_without_source_image_rejected():
    r1 = _pr("sift", 0.0)
    r2 = _pr("akaze", 0.0)
    r1.source_image = None
    r2.source_image = None
    with pytest.raises(ValueError, match="source_image"):
        agreement_for_stored([r1, r2])
