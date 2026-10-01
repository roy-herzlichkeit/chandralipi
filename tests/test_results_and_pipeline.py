"""Per-pair persistence, the end-to-end runner, and the shared figure renderers."""

from __future__ import annotations

import numpy as np
import pytest

from lunar_reg.eval.scenes import illumination_pair
from lunar_reg.pipeline import PipelineConfig, RunStatus, register_pair, run_batch
from lunar_reg.results import (
    SCHEMA_VERSION,
    PairResult,
    load_all_pairs,
    load_index,
    load_pair,
    reindex,
    save_results,
)
from lunar_reg.viz.figures import (
    anaglyph,
    blend,
    checkerboard,
    coverage_heatmap,
    side_by_side_matches,
    to_rgb,
    warp_source,
)


@pytest.fixture
def easy_pair():
    source, reference, truth, _ = illumination_pair(
        shape=(256, 256), seed=11,
        source_sun=(285.0, 45.0), reference_sun=(285.0, 45.0),
    )
    return source, reference, truth


def _result(**overrides) -> PairResult:
    rng = np.random.default_rng(3)
    src = rng.uniform(0, 255, (40, 2))
    base = {
        "pair_id": "p1", "source_id": "s1", "reference_id": "r1",
        "source_sensor": "OHRC", "reference_sensor": "LRO_NAC", "matcher": "sift",
        "src_pts": src, "dst_pts": src + 2.0,
        "inlier_mask": np.ones(40, dtype=bool), "transform": np.eye(3),
        "metrics": {"rmse_px": 0.42, "self_residual_subpixel": np.bool_(True)},
        "uniformity": {"score": 0.91}, "conditioning": {"p95_px": 0.3},
        "source_image": np.zeros((256, 256), np.uint8),
        "reference_image": np.zeros((256, 256), np.uint8),
    }
    base.update(overrides)
    return PairResult(**base)


# --- schema ---------------------------------------------------------------


def test_point_counts_must_agree():
    with pytest.raises(ValueError, match="differ"):
        _result(dst_pts=np.zeros((39, 2)))


def test_inlier_mask_length_is_checked():
    with pytest.raises(ValueError, match="inlier mask"):
        _result(inlier_mask=np.ones(7, dtype=bool))


def test_numpy_booleans_survive_into_the_index():
    """``np.bool_`` is not a subclass of ``bool``.

    A plain isinstance filter drops every metric flag from the index silently,
    and json.dumps raises on it. Both are fixed by coercion, and this pins it.
    """
    row = _result().index_row()
    assert row["m_self_residual_subpixel"] is True
    assert isinstance(row["m_self_residual_subpixel"], bool)


def test_index_row_prefixes_prevent_collisions():
    """``rmse_px`` and conditioning's ``p95_px`` must not overwrite each other."""
    row = _result(
        metrics={"p95_px": 1.0}, conditioning={"p95_px": 9.0}
    ).index_row()
    assert row["m_p95_px"] == 1.0
    assert row["c_p95_px"] == 9.0


def test_round_trip_preserves_points_exactly(tmp_path):
    """Sub-pixel coordinates must survive storage bit for bit."""
    original = _result()
    save_results([original], tmp_path)
    loaded = load_pair("p1", tmp_path)
    np.testing.assert_array_equal(loaded.src_pts, original.src_pts)
    np.testing.assert_array_equal(loaded.dst_pts, original.dst_pts)
    assert loaded.src_pts.dtype == np.float64


def test_round_trip_preserves_metadata(tmp_path):
    save_results([_result(synthetic=True, notes="generated")], tmp_path)
    loaded = load_pair("p1", tmp_path)
    assert loaded.synthetic is True
    assert loaded.notes == "generated"
    assert loaded.matcher == "sift"
    assert loaded.metrics["rmse_px"] == pytest.approx(0.42)


def test_thumbnail_scale_is_stored_so_points_can_be_placed(tmp_path):
    """A viewer that ignored the scale would draw every point in the wrong place."""
    big = np.zeros((2048, 2048), np.uint8)
    save_results([_result(source_image=big, reference_image=big)], tmp_path)
    loaded = load_pair("p1", tmp_path)
    assert loaded.source_image.shape[0] < 2048
    assert loaded.extra["source_scale"] == pytest.approx(
        loaded.source_image.shape[0] / 2048, rel=0.01
    )


def test_index_is_written_and_readable(tmp_path):
    save_results([_result(pair_id="a"), _result(pair_id="b")], tmp_path)
    frame = load_index(tmp_path)
    assert len(frame) == 2
    assert set(frame["pair_id"]) == {"a", "b"}
    assert (frame["schema_version"] == SCHEMA_VERSION).all()


def test_load_index_on_an_empty_directory_is_not_an_error(tmp_path):
    assert len(load_index(tmp_path)) == 0


def test_second_save_results_does_not_drop_the_first_batch(tmp_path):
    """The footgun: a build writing its own batch used to clobber the index and
    hide every pair written by an earlier build (the .npz survived, unindexed)."""
    save_results([_result(pair_id="real_lightglue", synthetic=False)], tmp_path)
    save_results(
        [_result(pair_id="synth_a", synthetic=True),
         _result(pair_id="synth_b", synthetic=True)],
        tmp_path,
    )
    frame = load_index(tmp_path)
    assert set(frame["pair_id"]) == {"real_lightglue", "synth_a", "synth_b"}


def test_reindex_rebuilds_from_disk_ignoring_a_stale_index(tmp_path):
    save_results([_result(pair_id="a"), _result(pair_id="b")], tmp_path)
    # Simulate a stale index that lost a pair whose .npz is still present.
    save_results([_result(pair_id="a")], tmp_path, reindex_all=False, overwrite=True)
    assert set(load_index(tmp_path)["pair_id"]) == {"a"}

    frame = reindex(tmp_path).frame
    assert set(frame["pair_id"]) == {"a", "b"}

    results, failures = load_all_pairs(tmp_path)
    assert failures == []
    assert {r.pair_id for r in results} == {"a", "b"}


def test_load_all_pairs_reports_a_bad_file_rather_than_raising(tmp_path):
    save_results([_result(pair_id="good")], tmp_path)
    (tmp_path / "pairs" / "corrupt.npz").write_bytes(b"not an npz")
    results, failures = load_all_pairs(tmp_path)
    assert {r.pair_id for r in results} == {"good"}
    assert [pid for pid, _ in failures] == ["corrupt"]


def test_missing_pair_raises_with_the_path(tmp_path):
    with pytest.raises(FileNotFoundError, match="nope"):
        load_pair("nope", tmp_path)


# --- pipeline -------------------------------------------------------------


def test_register_pair_produces_a_storable_result(easy_pair):
    source, reference, _ = easy_pair
    outcome = register_pair(
        source, reference, "demo", config=PipelineConfig(matcher="akaze", n_bootstrap=10),
        source_sensor="OHRC", reference_sensor="LRO_NAC",
    )
    assert outcome.ok
    result = outcome.result
    assert result.n_inliers >= 8
    assert result.metrics["rmse_px"] < 5.0
    assert "score" in result.uniformity
    assert "p95_px" in result.conditioning
    assert result.transform.shape == (3, 3)


def test_failure_is_classified_rather_than_raised():
    """Opposed illumination defeats classical matchers; that is data, not a crash."""
    source, reference, _, _ = illumination_pair(
        shape=(256, 256), seed=5,
        source_sun=(285.0, 6.0), reference_sun=(105.0, 62.0),
    )
    outcome = register_pair(source, reference, "hard", config=PipelineConfig(matcher="sift"))
    assert not outcome.ok
    assert outcome.status.is_failure
    assert outcome.detail


def test_sun_angles_select_the_ecc_prefilter(easy_pair):
    source, reference, _ = easy_pair
    same = register_pair(
        source, reference, "same", config=PipelineConfig(matcher="akaze", n_bootstrap=0),
        source_sun=(285.0, 45.0), reference_sun=(285.0, 45.0),
    )
    differing = register_pair(
        source, reference, "diff", config=PipelineConfig(matcher="akaze", n_bootstrap=0),
        source_sun=(285.0, 45.0), reference_sun=(330.0, 45.0),
    )
    assert same.result.extra["ecc_prefilter"] == "none"
    assert differing.result.extra["ecc_prefilter"] == "local_contrast"


def test_batch_report_counts_and_samples_every_failure(easy_pair):
    source, reference, _ = easy_pair
    hard_src, hard_ref, _, _ = illumination_pair(
        shape=(256, 256), seed=5,
        source_sun=(285.0, 6.0), reference_sun=(105.0, 62.0),
    )
    report = run_batch(
        [
            {"source": source, "reference": reference, "pair_id": "good"},
            {"source": hard_src, "reference": hard_ref, "pair_id": "bad"},
        ],
        config=PipelineConfig(matcher="sift", n_bootstrap=0),
    )
    assert len(report.results) == 1
    assert len(report.failures) == 1
    text = report.report()
    assert RunStatus.TOO_FEW_MATCHES.value in text
    # The report must carry a concrete sample, not only a count.
    assert "bad" in text


def test_batch_persists_when_a_root_is_given(easy_pair, tmp_path):
    source, reference, _ = easy_pair
    run_batch(
        [{"source": source, "reference": reference, "pair_id": "one"}],
        config=PipelineConfig(matcher="akaze", n_bootstrap=0), root=tmp_path,
    )
    assert len(load_index(tmp_path)) == 1
    assert load_pair("one", tmp_path).n_inliers > 0


# --- figures --------------------------------------------------------------


def test_to_rgb_handles_grey_and_float():
    assert to_rgb(np.zeros((8, 8), np.uint8)).shape == (8, 8, 3)
    out = to_rgb(np.linspace(0, 1, 64).reshape(8, 8).astype(np.float32))
    assert out.dtype == np.uint8 and out.max() == 255


def test_side_by_side_is_the_width_of_both_images():
    src = np.zeros((32, 40), np.uint8)
    ref = np.zeros((32, 25), np.uint8)
    pts = np.array([[5.0, 5.0], [10.0, 10.0]])
    canvas = side_by_side_matches(src, ref, pts, pts, np.array([True, False]))
    assert canvas.shape == (32, 65, 3)


def test_line_subsampling_is_deterministic():
    rng = np.random.default_rng(0)
    src = rng.uniform(0, 60, (500, 2))
    image = np.zeros((64, 64), np.uint8)
    a = side_by_side_matches(image, image, src, src, max_lines=20)
    b = side_by_side_matches(image, image, src, src, max_lines=20)
    np.testing.assert_array_equal(a, b)


def test_checkerboard_alternates_between_the_two_images():
    source = np.full((64, 64), 200, np.uint8)
    reference = np.zeros((64, 64), np.uint8)
    board = checkerboard(source, reference, np.eye(3), tile=16)
    assert board[..., 0].min() == 0
    assert board[..., 0].max() > 150


def test_blend_and_anaglyph_return_matching_shapes():
    source = np.full((32, 32), 120, np.uint8)
    reference = np.zeros((32, 32), np.uint8)
    assert blend(source, reference, np.eye(3)).shape == (32, 32, 3)
    assert anaglyph(source, reference, np.eye(3)).shape == (32, 32, 3)


def test_warp_accepts_a_2x3_affine():
    affine = np.array([[1.0, 0.0, 2.0], [0.0, 1.0, 3.0]])
    assert warp_source(np.zeros((16, 16), np.uint8), affine, (16, 16)).shape == (16, 16)


def test_heatmap_colour_is_scaled_against_the_gate():
    """Colour must mean the same thing on every pair, or two cannot be compared."""
    cool = coverage_heatmap(np.zeros((4, 4)), (16, 16), gate_px=1.0)
    hot = coverage_heatmap(np.full((4, 4), 5.0), (16, 16), gate_px=1.0)
    assert not np.array_equal(cool, hot)
    # Beyond the gate everything saturates, so 5x and 50x look the same.
    np.testing.assert_array_equal(
        hot, coverage_heatmap(np.full((4, 4), 50.0), (16, 16), gate_px=1.0)
    )
