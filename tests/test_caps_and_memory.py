"""P2.07 -- classical feature caps, RIFT2 memory guard, uint8 stretch memory.

Phase_2/LLD/tiling.md §P2.07 (AUDIT A081, A129, A082).
"""

from __future__ import annotations

import tracemalloc

import numpy as np
import pytest

from lunar_reg.match.classical import POSTHOC_CAP_DETECTORS, ClassicalMatcher
from lunar_reg.match.rift2 import matcher as rift2_matcher
from lunar_reg.match.rift2.matcher import RIFT2Matcher, default_max_tile_px
from lunar_reg.preprocess import radiometric
from lunar_reg.preprocess.radiometric import to_uint8
from lunar_reg.provenance import ValueSource


def _terrain(shape=(512, 512), seed=3) -> np.ndarray:
    from lunar_reg.eval.scenes import add_craters, fractal_terrain, hillshade

    h = add_craters(fractal_terrain(shape, seed=seed), n=45, seed=seed)
    return np.maximum(hillshade(h, azimuth_deg=315, elevation_deg=35), 1).astype(np.uint8)


# --- A081: max_features for detectors without a native cap ---------------------------


@pytest.mark.parametrize("name", POSTHOC_CAP_DETECTORS)
def test_posthoc_detectors_respect_max_features(name):
    img = _terrain()
    uncapped, _ = ClassicalMatcher(name, max_features=1_000_000).detect(img)
    assert len(uncapped) > 100, "scene too plain to exercise the cap"
    kps, des = ClassicalMatcher(name, max_features=100).detect(img)
    assert len(kps) == 100 and len(des) == 100


def test_akaze_cap_bounds_match_sources_and_records_meta():
    img = _terrain()
    m = ClassicalMatcher("akaze", max_features=100)
    res = m.match(img, img)
    assert 0 < len(res) <= 100
    assert len({tuple(p) for p in res.src_pts}) <= 100
    assert res.meta["max_features_applied"] is True
    # The detector's own count survives the cap, and the truncation is flagged.
    detected, _ = ClassicalMatcher("akaze", max_features=1_000_000).detect(img)
    assert res.meta["n_keypoints_src_detected"] == len(detected) > 100
    assert res.meta["n_keypoints_ref_detected"] == len(detected)
    assert res.meta["max_features_truncated_src"] is True
    assert res.meta["max_features_truncated_ref"] is True
    assert res.meta["n_keypoints_src_raw"] == 100  # count entering the G42 cap


def test_untruncated_detection_records_false():
    img = _terrain((256, 256))
    res = ClassicalMatcher("akaze", max_features=1_000_000).match(img, img)
    assert res.meta["max_features_truncated_src"] is False
    assert res.meta["n_keypoints_src_detected"] == res.meta["n_keypoints_src_raw"]


def test_cap_keeps_strongest_with_stable_ties():
    import cv2

    m = ClassicalMatcher("akaze", max_features=3)
    responses = [0.5, 0.9, 0.9, 0.1, 0.7]
    kps = [cv2.KeyPoint(float(i), 0.0, 1.0, -1, r) for i, r in enumerate(responses)]
    des = np.arange(5, dtype=np.uint8)[:, None]
    kept, kept_des = m._cap_features(kps, des)
    # Strongest three: 0.9 (idx 1), 0.9 (idx 2), 0.7 (idx 4); original order kept.
    assert [k.pt[0] for k in kept] == [1.0, 2.0, 4.0]
    assert kept_des.ravel().tolist() == [1, 2, 4]


def test_native_cap_detectors_record_false():
    img = _terrain((256, 256))
    res = ClassicalMatcher("sift", max_features=50).match(img, img)
    assert res.meta["max_features_applied"] is False
    assert res.meta["max_features_truncated_src"] is False
    assert res.meta["n_keypoints_src_detected"] == res.meta["n_keypoints_src_raw"] <= 50


# --- A129: RIFT2 host-RAM guard -------------------------------------------------------


def test_rift2_explicit_cap_refuses_larger_input():
    m = RIFT2Matcher(max_tile_px=128)
    assert m.max_tile_px == 128
    small = np.ones((128, 128), np.uint8)
    big = np.ones((256, 256), np.uint8)
    with pytest.raises(ValueError, match="128"):
        m.match(big, small)
    with pytest.raises(ValueError, match="reference"):
        m.match(small, big)
    with pytest.raises(ValueError, match="128"):
        m.detect_and_describe(big)


def test_rift2_rejects_nonpositive_cap():
    with pytest.raises(ValueError):
        RIFT2Matcher(max_tile_px=0)


def test_rift2_default_cap_from_meminfo(monkeypatch):
    from lunar_reg import device

    avail = 10 * 1024**3
    monkeypatch.setattr(
        device,
        "_read_proc_meminfo",
        lambda: f"MemTotal: {16 * 1024**2} kB\nMemAvailable: {avail // 1024} kB\n",
    )
    expected = int(np.floor(np.sqrt(0.25 * avail / 300))) // 64 * 64
    cap, source = default_max_tile_px()
    assert (cap, source) == (expected, ValueSource.INFERRED)
    m = RIFT2Matcher()
    assert m.max_tile_px == expected and m.max_tile_px_source is ValueSource.INFERRED
    assert rift2_matcher.BYTES_PER_PX_SOURCE is ValueSource.INFERRED


def test_rift2_unknown_memory_refuses_every_input(monkeypatch):
    from lunar_reg import device

    def boom():
        raise OSError("no /proc")

    monkeypatch.setattr(device, "_read_proc_meminfo", boom)
    m = RIFT2Matcher()
    assert m.max_tile_px == 0 and m.max_tile_px_source is ValueSource.UNKNOWN
    with pytest.raises(ValueError, match="max_tile_px explicitly"):
        m.match(np.ones((8, 8), np.uint8), np.ones((8, 8), np.uint8))


def test_rift2_result_meta_carries_cap():
    img = _terrain((128, 128))
    res = RIFT2Matcher(max_tile_px=128).match(img, img)
    assert res.meta["max_tile_px"] == 128


def test_tiled_matcher_sizes_tiles_from_rift2_cap():
    from lunar_reg.match.tiled import TiledMatcher

    tm = TiledMatcher(RIFT2Matcher(max_tile_px=512))
    assert tm.tile_px == 512 - 2 * tm.ref_margin_px


# --- A082: to_uint8 lo_hi, subsampling, memory ----------------------------------------


def test_to_uint8_lo_hi_unmasked():
    a = np.array([[5.0, 10.0, 15.0, 20.0, 30.0]], np.float32)
    out = to_uint8(a, lo_hi=(10, 20))
    assert out.tolist() == [[0, 0, 127, 255, 255]]


def test_to_uint8_lo_hi_masked_keeps_zero_for_nodata():
    a = np.array([[5.0, 10.0, 15.0, 20.0, 30.0]], np.float32)
    valid = np.array([[True, True, True, True, False]])
    out = to_uint8(a, valid=valid, lo_hi=(10, 20))
    assert out[0, 1] == 1 and out[0, 3] == 255 and out[0, 4] == 0
    assert out[0, 0] == 1  # below lo clips to the lowest valid value, not nodata


def test_to_uint8_lo_hi_degenerate_is_zero():
    assert not to_uint8(np.arange(10, dtype=np.float32)[None], lo_hi=(5, 5)).any()


def test_to_uint8_lo_hi_consistent_across_tiles():
    a = np.random.default_rng(1).uniform(0, 1000, (64, 128)).astype(np.float32)
    lo_hi = tuple(np.percentile(a, (1.0, 99.0)))
    whole = to_uint8(a, lo_hi=lo_hi)
    halves = np.hstack([to_uint8(a[:, :64], lo_hi=lo_hi), to_uint8(a[:, 64:], lo_hi=lo_hi)])
    assert np.array_equal(whole, halves)


def test_sample_step_rule():
    assert radiometric._stretch_sample_step(40_000_000) == 1
    assert radiometric._stretch_sample_step(49_000_000) == 2
    assert radiometric._stretch_sample_step(160_000_001) == 3


def test_explicit_sample_step_close_to_full():
    a = np.random.default_rng(2).uniform(0, 1000, (512, 512)).astype(np.float32)
    full = to_uint8(a).astype(int)
    sub = to_uint8(a, sample_step=4).astype(int)
    assert np.abs(full - sub).max() <= 3
    with pytest.raises(ValueError):
        to_uint8(a, sample_step=0)


def test_to_uint8_row_blocks_match_single_block(monkeypatch):
    a = np.random.default_rng(3).uniform(0, 4000, (300, 50)).astype(np.uint16)
    v = np.random.default_rng(4).random(a.shape) > 0.2
    ref, ref_v = to_uint8(a), to_uint8(a, valid=v)
    monkeypatch.setattr(radiometric, "STRETCH_ROW_BLOCK", 7)
    assert np.array_equal(to_uint8(a), ref)
    assert np.array_equal(to_uint8(a, valid=v), ref_v)


def test_to_uint8_large_image_no_float64_copy():
    a = np.random.default_rng(0).uniform(0, 1000, (7000, 7000)).astype(np.float32)
    tracemalloc.start()
    out = to_uint8(a)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert peak < 2 * a.nbytes
    assert out.dtype == np.uint8 and out.min() == 0 and out.max() == 255


def test_masked_strided_sample_off_grid_falls_back_to_all_valid(caplog):
    a = np.zeros((8, 8), np.float32)
    v = np.zeros((8, 8), bool)
    for (r, c), x in zip(((1, 1), (3, 5), (5, 3)), (5.0, 9.0, 7.0), strict=True):
        a[r, c], v[r, c] = x, True
    full = to_uint8(a, valid=v)
    with caplog.at_level("WARNING", logger="lunar_reg.preprocess.radiometric"):
        sub = to_uint8(a, valid=v, sample_step=2)
    assert np.array_equal(sub, full)
    assert (sub[v] >= 1).all() and not sub[~v].any()
    assert "strided sample" in caplog.text


def test_unmasked_strided_sample_off_grid_falls_back_to_all_finite(caplog):
    b = np.full((8, 8), np.nan, np.float32)
    b[1, :] = np.arange(8)
    with caplog.at_level("WARNING", logger="lunar_reg.preprocess.radiometric"):
        sub = to_uint8(b, sample_step=2)
    assert np.array_equal(sub, to_uint8(b))
    assert sub[1].max() == 255
    assert "strided sample" in caplog.text
