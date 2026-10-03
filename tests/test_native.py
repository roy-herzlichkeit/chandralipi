"""Native-GSD refinement (CONTRACTS C19, Phase_2/LLD/native.md §P2.08, DECISIONS G10)."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from lunar_reg.align import native
from lunar_reg.align.native import (
    NativeDiagnostics,
    NativeStatus,
    lift_to_native,
    refine_native_arrays,
)
from lunar_reg.eval.scenes import fractal_terrain, hillshade
from lunar_reg.match import build_matcher
from lunar_reg.provenance import ValueSource

# native (0.25 m) px -> 1 m px, pixel-centre convention (CONTRACTS C11, factor 4).
R_NATIVE_TO_1M = np.array([[0.25, 0.0, -0.375], [0.0, 0.25, -0.375], [0.0, 0.0, 1.0]])
PROBES = np.array(
    [[200.0, 200.0], [1800.0, 200.0], [200.0, 1800.0], [1800.0, 1800.0], [1024, 1024]]
)


# Probe tolerance in reference px. The pixel-centre S gives about 0.01 px on this scene
# and a corner-convention S (no (f - 1)/2 term) about 0.4 px, so this bound catches
# a half-pixel-convention regression that the LLD's 0.5 px bound would let through.
PROBE_TOL_PX = 0.1


def _apply(h, pts):
    hom = np.c_[np.asarray(pts, float), np.ones(len(pts))] @ np.asarray(h, float).T
    return hom[:, :2] / hom[:, 2:3]


def _similarity(scale, angle_deg, tx, ty):
    a = np.radians(angle_deg)
    c, s = scale * np.cos(a), scale * np.sin(a)
    return np.array([[c, -s, tx], [s, c, ty], [0.0, 0.0, 1.0]])


@pytest.fixture(scope="module")
def scene():
    """A 2048² 0.25 m "native source" and a 600² 1 m reference related by a known homography."""
    shade = hillshade(fractal_terrain((2048, 2048), seed=11), azimuth_deg=315, elevation_deg=35)
    shade = shade.astype(np.float64)
    src = (1 + (shade - shade.min()) / (shade.max() - shade.min()) * 254).astype(np.uint8)
    at_1m = cv2.resize(src, (512, 512), interpolation=cv2.INTER_AREA)
    H = _similarity(1.0, 1.5, 40.0, 25.0)
    H[2, 0], H[2, 1] = 1e-5, -1e-5  # mild perspective: a true homography, not an affine
    ref = cv2.warpPerspective(at_1m, H, (600, 600), flags=cv2.INTER_LINEAR)
    return src, ref, H @ R_NATIVE_TO_1M


def _shifted(truth, dx_ref_px):
    prior = truth.copy()
    prior[0, :] += dx_ref_px * prior[2, :]  # adds dx_ref_px to x for every point
    return prior


# ------------------------------------------------------------------ lift_to_native


def test_lift_to_native_matches_explicit_composition():
    coarse = _similarity(1.02, -3.0, 12.5, -7.25)
    s2n = np.array([[16.0, 0.0, 107.5], [0.0, 16.0, 207.5], [0.0, 0.0, 1.0]])
    r2n = np.array([[4.0, 0.0, 31.5], [0.0, 4.0, 41.5], [0.0, 0.0, 1.0]])
    lifted = lift_to_native(coarse, s2n, r2n)
    pts = np.array([[0.0, 0.0], [123.0, 456.0], [4000.0, 1.5]])
    expect = _apply(r2n, _apply(coarse, _apply(np.linalg.inv(s2n), pts)))
    np.testing.assert_allclose(_apply(lifted, pts), expect, atol=1e-9)
    # A 2x3 coarse transform is promoted with [0, 0, 1].
    np.testing.assert_allclose(lift_to_native(coarse[:2], s2n, r2n), lifted, atol=1e-12)
    # Round trip: mapping back through the working grids recovers the coarse transform.
    back = np.linalg.inv(r2n) @ lifted @ s2n
    np.testing.assert_allclose(back, coarse, atol=1e-12)


def test_lift_to_native_rejects_bad_shape():
    with pytest.raises(ValueError, match="coarse"):
        lift_to_native(np.eye(2), np.eye(3), np.eye(3))


# ------------------------------------------------------------------ resampling


def test_native_to_resampled_is_pixel_centre():
    # C11 pixel-centre to_native for f = 4: [[4, 0, 1.5], [0, 4, 1.5], [0, 0, 1]].
    S = native._native_to_resampled((2048, 2048), (512, 512))
    expect = np.linalg.inv(np.array([[4.0, 0.0, 1.5], [0.0, 4.0, 1.5], [0.0, 0.0, 1.0]]))
    np.testing.assert_allclose(S, expect, atol=1e-12)
    # The centre of native block 0 (px 1.5) is resampled px 0; px -0.5 (the edge) is -0.5.
    np.testing.assert_allclose(_apply(S, [[1.5, 1.5], [-0.5, -0.5]]), [[0, 0], [-0.5, -0.5]])
    # Non-integer ratios use the actual size ratio on each axis.
    S2 = native._native_to_resampled((1000, 600), (333, 200))
    fx, fy = 1000 / 333, 3.0
    np.testing.assert_allclose(_apply(S2, [[(fx - 1) / 2, (fy - 1) / 2]]), [[0.0, 0.0]], atol=1e-12)


def test_resample_source_collar_is_not_valid():
    # Columns 6-7 are nodata: INTER_AREA blends them into the second 4x4 block (value
    # 100), which `> 0` would mark valid. Full-support validity marks it invalid and zeroes it.
    img = np.full((8, 8), 200, np.uint8)
    img[:, 6:] = 0
    src_r, valid_r = native._resample_source(img, (2, 2))
    assert valid_r.tolist() == [[True, False], [True, False]]
    assert src_r.tolist() == [[200, 0], [200, 0]]
    assert src_r.dtype == np.uint8
    # Float input: NaN is nodata and never spreads into a valid cell.
    f = np.full((8, 8), 5.0, np.float32)
    f[0, 7] = np.nan
    src_f, valid_f = native._resample_source(f, (2, 2))
    assert valid_f.tolist() == [[True, False], [True, True]]
    assert np.isfinite(src_f).all() and src_f[0, 1] == 0.0


def test_refine_passes_full_support_mask(scene, monkeypatch):
    src, ref, truth = scene
    src = src.copy()
    src[:, -6:] = 0  # a nodata collar that does not fall on a multiple of f = 4
    seen = {}

    class Spy(native.TiledMatcher):
        def match_arrays(self, source, reference, prior=None, source_valid=None, **kw):
            seen["source"], seen["valid"] = source, source_valid
            return super().match_arrays(source, reference, prior, source_valid, **kw)

    monkeypatch.setattr(native, "TiledMatcher", Spy)
    out = refine_native_arrays(
        src, ref, truth, source_native_gsd_m=0.25, reference_native_gsd_m=1.0, tile_px=256
    )
    assert out.status is NativeStatus.OK, out.report()
    valid = seen["valid"]
    assert valid is not None and valid.shape == seen["source"].shape == (512, 512)
    # Resampled column 510 covers native 2040-2043, of which 2042-2043 are nodata.
    assert valid[:, :510].all() and not valid[:, 510:].any()
    assert (seen["source"][:, 510:] == 0).all()


# ------------------------------------------------------------------ refinement


def test_synthetic_refine_ok(scene):
    src, ref, truth = scene
    prior = _shifted(truth, 2.0)  # 2 ref px at 1 m = 0.5 coarse (4 m) px
    out = refine_native_arrays(
        src, ref, prior, source_native_gsd_m=0.25, reference_native_gsd_m=1.0, tile_px=256
    )
    assert out.status is NativeStatus.OK, out.report()
    assert out.transform.shape == (3, 3)
    assert np.abs(_apply(out.transform, PROBES) - _apply(truth, PROBES)).max() < PROBE_TOL_PX
    assert out.drift_coarse_px < 1.0
    assert out.n_inliers >= 8 and out.n_matches >= out.n_inliers
    # G10: matching ran on the source resampled to 1 m (512²), not at 0.25 m (2048²):
    # 256 px tiles at stride 192 give 3 x 3 tiles over 512², 11 x 11 over 2048².
    assert len(out.tiles.outcomes) == 9
    assert out.tiles.n_failed == 0
    assert out.provenance["drift_coarse_px"] == ValueSource.COMPUTED.value
    assert "ok" in out.report()


def test_drift_rule_with_converging_prior(scene):
    src, ref, truth = scene
    prior = _shifted(truth, 12.0)  # 12 ref px = 3 coarse px
    out = refine_native_arrays(
        src,
        ref,
        prior,
        source_native_gsd_m=0.25,
        reference_native_gsd_m=1.0,
        tile_px=256,
        max_drift_coarse_px=1.0,
    )
    # The refinement converges to the truth, which is 3 coarse px from the prior.
    assert out.status is NativeStatus.DRIFT_EXCEEDED, out.report()
    assert out.transform is not None
    assert np.abs(_apply(out.transform, PROBES) - _apply(truth, PROBES)).max() < PROBE_TOL_PX
    assert out.drift_coarse_px == pytest.approx(3.0, abs=0.25)
    # A looser drift budget accepts the same solution.
    loose = refine_native_arrays(
        src,
        ref,
        prior,
        source_native_gsd_m=0.25,
        reference_native_gsd_m=1.0,
        tile_px=256,
        max_drift_coarse_px=4.0,
    )
    assert loose.status is NativeStatus.OK, loose.report()


def test_blank_input_is_too_few_matches():
    out = refine_native_arrays(
        np.zeros((512, 512), np.uint8),
        np.zeros((128, 128), np.uint8),
        np.diag([0.25, 0.25, 1.0]),
        source_native_gsd_m=0.25,
        reference_native_gsd_m=1.0,
        tile_px=128,
    )
    assert out.status is NativeStatus.TOO_FEW_MATCHES
    assert out.transform is None and out.drift_coarse_px is None
    assert out.tiles is not None and out.tiles.counts == {"skipped_nodata": 1}
    assert "too_few_matches" in out.report()
    # The detail names the cause in words: a data gap, not a matcher bug.
    assert "skipped_nodata=1 of 1" in out.detail and "data gap" in out.detail


def test_estimation_failure_is_classified(scene, monkeypatch):
    src, ref, truth = scene

    def boom(*args, **kwargs):
        raise ValueError("homography estimation failed to converge")

    monkeypatch.setattr(native, "estimate_transform", boom)
    out = refine_native_arrays(
        src, ref, truth, source_native_gsd_m=0.25, reference_native_gsd_m=1.0, tile_px=256
    )
    assert out.status is NativeStatus.ESTIMATION_FAILED
    assert out.transform is None and "converge" in out.detail
    assert out.n_matches >= 8


class _FailingFirst:
    """Wraps a real matcher and raises on its first ``n_fail`` calls."""

    def __init__(self, inner, n_fail):
        self.inner, self.n_fail, self.calls = inner, n_fail, 0
        self.name = "failing"

    def match(self, source, reference):
        self.calls += 1
        if self.calls <= self.n_fail:
            raise RuntimeError("synthetic matcher failure")
        return self.inner.match(source, reference)


def test_tile_failures_rule(scene, monkeypatch):
    src, ref, truth = scene
    monkeypatch.setattr(
        native, "build_matcher", lambda name: _FailingFirst(build_matcher(name), n_fail=5)
    )
    out = refine_native_arrays(
        src, ref, truth, source_native_gsd_m=0.25, reference_native_gsd_m=1.0, tile_px=256
    )
    assert out.tiles.n_failed == 5 and len(out.tiles.outcomes) == 9
    assert out.status is NativeStatus.TILE_FAILURES, out.report()
    assert out.transform is not None  # kept for inspection
    assert "5/9" in out.detail


class _AlwaysRaises:
    name = "always-raises"

    def __init__(self, exc):
        self.exc = exc

    def match(self, source, reference):
        raise self.exc


def test_all_tiles_matcher_error_is_tile_failures(scene, monkeypatch):
    src, ref, truth = scene
    monkeypatch.setattr(
        native, "build_matcher", lambda name: _AlwaysRaises(RuntimeError("synthetic bug"))
    )
    out = refine_native_arrays(
        src, ref, truth, source_native_gsd_m=0.25, reference_native_gsd_m=1.0, tile_px=256
    )
    # Not TOO_FEW_MATCHES: the matcher, not the data, is why there are no matches.
    assert out.status is NativeStatus.TILE_FAILURES, out.report()
    assert out.transform is None and out.n_matches == 0
    assert out.tiles.counts == {"matcher_error": 9}
    assert "matcher_error=9 of 9" in out.detail and "failed in the matcher" in out.detail
    diag = NativeDiagnostics()
    diag.record("pair-x", out)
    assert diag.counts == {"tile_failures": 1}
    assert "matcher_error=9" in diag.samples["tile_failures"]
    assert "FAILURE" in diag.report()


def test_all_tiles_oom_is_tile_failures(scene, monkeypatch):
    torch = pytest.importorskip("torch")
    src, ref, truth = scene
    monkeypatch.setattr(
        native,
        "build_matcher",
        lambda name: _AlwaysRaises(torch.OutOfMemoryError("CUDA out of memory (synthetic)")),
    )
    monkeypatch.setattr(torch.cuda, "empty_cache", lambda: None)
    out = refine_native_arrays(
        src, ref, truth, source_native_gsd_m=0.25, reference_native_gsd_m=1.0, tile_px=256
    )
    assert out.status is NativeStatus.TILE_FAILURES, out.report()
    assert out.transform is None
    assert out.tiles.counts == {"oom": 9} and "oom=9 of 9" in out.detail


def test_too_few_matches_with_some_failed_tiles_names_them(monkeypatch):
    # Textureless but valid data over 9 tiles, one of which fails: a minority, so the
    # status stays TOO_FEW_MATCHES, but the detail still names the failed tile.
    calls = {"n": 0}

    class FailOnce:
        name = "fail-once"

        def match(self, source, reference):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("synthetic bug")
            return build_matcher("sift").match(source, reference)

    monkeypatch.setattr(native, "build_matcher", lambda name: FailOnce())
    flat = np.full((1024, 1024), 128, np.uint8)  # valid but textureless: nothing to match
    out = refine_native_arrays(
        flat,
        flat[:256, :256],
        np.diag([0.25, 0.25, 1.0]),
        source_native_gsd_m=0.25,
        reference_native_gsd_m=1.0,
        tile_px=128,
    )
    assert out.tiles.counts == {"empty": 8, "matcher_error": 1}
    assert out.status is NativeStatus.TOO_FEW_MATCHES, out.report()
    assert "matcher_error=1 of 9" in out.detail
    assert "1 tile(s) failed in the matcher" in out.detail


def test_estimation_failure_after_tile_failures_is_tile_failures(scene, monkeypatch):
    src, ref, truth = scene
    monkeypatch.setattr(
        native, "build_matcher", lambda name: _FailingFirst(build_matcher(name), n_fail=5)
    )

    def boom(*args, **kwargs):
        raise ValueError("homography estimation failed to converge")

    monkeypatch.setattr(native, "estimate_transform", boom)
    out = refine_native_arrays(
        src, ref, truth, source_native_gsd_m=0.25, reference_native_gsd_m=1.0, tile_px=256
    )
    assert out.status is NativeStatus.TILE_FAILURES, out.report()
    assert out.transform is None and "5/9 tiles failed" in out.detail and "converge" in out.detail


def test_programmer_errors_raise():
    img = np.ones((64, 64), np.uint8)
    with pytest.raises(ValueError, match="coarser"):
        refine_native_arrays(
            img, img, np.eye(3), source_native_gsd_m=1.0, reference_native_gsd_m=0.25
        )
    with pytest.raises(ValueError, match="model"):
        refine_native_arrays(
            img,
            img,
            np.eye(3),
            source_native_gsd_m=0.25,
            reference_native_gsd_m=1.0,
            model="bogus",
        )
    with pytest.raises(ValueError, match="2-D"):
        refine_native_arrays(
            np.ones((8, 8, 3), np.uint8),
            img,
            np.eye(3),
            source_native_gsd_m=0.25,
            reference_native_gsd_m=1.0,
        )


def test_diagnostics_report_counts_and_samples():
    diag = NativeDiagnostics()
    ok = native.NativeRefinement(NativeStatus.OK, np.eye(3), 50, 40, 0.2, None, "")
    few = native.NativeRefinement(
        NativeStatus.TOO_FEW_MATCHES, None, 3, 0, None, None, "3 matches < 8"
    )
    diag.record("pair-a", ok)
    diag.record("pair-b", few)
    diag.record("pair-c", few)
    assert diag.counts == {"ok": 1, "too_few_matches": 2}
    assert diag.samples["too_few_matches"] == "pair-b: 3 matches < 8"
    text = diag.report()
    assert text.splitlines()[0] == "native refinements: 3 total, 1 ok, 2 failed"
    assert "too_few_matches: 2" in text
