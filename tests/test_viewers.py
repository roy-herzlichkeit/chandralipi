"""P1.21 viewers: per-side thumbnail scales, atomic web export, failures, stash moves.

Data-free: every store here is built in ``tmp_path`` from synthetic arrays.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import numpy as np
import pytest

from lunar_reg.pipeline import PipelineConfig, register_pair
from lunar_reg.results import PairResult, load_pair, save_failures, save_pair, save_results
from lunar_reg.viz.figures import (
    INLIER_COLOUR,
    points_outside,
    side_by_side_matches,
    thumbnail_transform,
    warp_source,
)

REPO = Path(__file__).resolve().parents[1]


def _script(name: str):
    spec = importlib.util.spec_from_file_location(
        f"_viewers_{name}", REPO / "scripts" / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _strict_json(text: str):
    def reject(token):
        raise ValueError(f"non-standard JSON constant {token}")

    return json.loads(text, parse_constant=reject)


def _result(
    pair_id="p1",
    n=4,
    *,
    src_shape=(40, 40),
    ref_shape=(40, 40),
    synthetic=False,
    extra=None,
    src_pts=None,
    dst_pts=None,
    model="homography",
):
    pts = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0], [7.0, 1.0]])[:n]
    src = pts if src_pts is None else np.asarray(src_pts, dtype=np.float64)
    dst = src if dst_pts is None else np.asarray(dst_pts, dtype=np.float64)
    return PairResult(
        pair_id,
        "s",
        "r",
        "A",
        "B",
        "sift",
        src,
        dst,
        np.ones(len(src), bool),
        np.eye(3),
        metrics={"model": model},
        source_image=np.zeros(src_shape, np.uint8),
        reference_image=np.zeros(ref_shape, np.uint8),
        synthetic=synthetic,
        extra=dict(extra or {}),
    )


# --------------------------------------------------------------------------
# A068: per-side scales and transform conjugation
# --------------------------------------------------------------------------


def test_stored_thumbnails_with_different_scales_put_a_point_on_the_right_pixel(tmp_path):
    # Source 1024x2048 -> thumbnail scale 0.5; reference 4096x4096 -> scale 0.25.
    src_full, dst_full = (400.0, 200.0), (800.0, 1200.0)
    result = _result(
        "scaled",
        src_shape=(1024, 2048),
        ref_shape=(4096, 4096),
        src_pts=[src_full],
        dst_pts=[dst_full],
    )
    save_pair(result, tmp_path)
    loaded = load_pair("scaled", tmp_path)
    src_scale, ref_scale = loaded.extra["source_scale"], loaded.extra["reference_scale"]
    assert (src_scale, ref_scale) == (0.5, 0.25)

    canvas = side_by_side_matches(
        loaded.source_image,
        loaded.reference_image,
        loaded.src_pts,
        loaded.dst_pts,
        loaded.inlier_mask,
        src_scale=src_scale,
        ref_scale=ref_scale,
    )
    offset = loaded.source_image.shape[1]
    # Full-resolution (400, 200) * 0.5 -> (200, 100) on the source thumbnail.
    assert tuple(canvas[100, 200]) == INLIER_COLOUR
    # Full-resolution (800, 1200) * 0.25 -> (200, 300) on the reference thumbnail.
    assert tuple(canvas[300, offset + 200]) == INLIER_COLOUR
    # With one shared scale (the old behaviour) the reference point lands elsewhere.
    assert tuple(canvas[600, offset + 400]) == (0, 0, 0)


def test_thumbnail_transform_is_the_conjugate():
    full = np.array([[1.0, 0.0, 100.0], [0.0, 1.0, 60.0], [0.0, 0.0, 1.0]])
    thumb = thumbnail_transform(full, 0.5, 0.25)
    s_src, s_ref = np.diag([0.5, 0.5, 1.0]), np.diag([0.25, 0.25, 1.0])
    np.testing.assert_allclose(thumb, s_ref @ full @ np.linalg.inv(s_src))
    # Source thumbnail (200, 100) = full (400, 200) -> full (500, 260) -> ref thumb (125, 65).
    np.testing.assert_allclose(thumb @ [200.0, 100.0, 1.0], [125.0, 65.0, 1.0])
    # A 2x3 affine is promoted, not rejected.
    np.testing.assert_allclose(thumbnail_transform(full[:2], 0.5, 0.25), thumb)


def test_conjugated_warp_moves_a_bright_pixel_onto_the_reference_thumbnail():
    full = np.array([[1.0, 0.0, 100.0], [0.0, 1.0, 60.0], [0.0, 0.0, 1.0]])
    source_thumb = np.zeros((300, 300), np.float32)
    source_thumb[100, 200] = 1.0
    warped = warp_source(source_thumb, thumbnail_transform(full, 0.5, 0.25), (200, 200))
    row, col = np.unravel_index(np.argmax(warped), warped.shape)
    assert abs(row - 65) <= 1 and abs(col - 125) <= 1


def test_points_outside_counts_rather_than_drops():
    pts = np.array([[0.0, 0.0], [99.0, 49.0], [100.0, 10.0], [-0.5, 3.0], [5.0, 50.0]])
    assert points_outside(pts, (50, 100)) == 3


# --------------------------------------------------------------------------
# A118 / A124 / C05 / G11: the web export
# --------------------------------------------------------------------------


def _store(tmp_path, results, failures=True):
    root = tmp_path / "store"
    save_results(results, root)
    if failures:
        blank = np.zeros((64, 64), np.uint8)
        save_failures([register_pair(blank, blank, "bad1", PipelineConfig(matcher="sift"))], root)
    return root


def test_export_writes_strict_json_with_failures_and_relative_source(tmp_path):
    root = _store(tmp_path, [_result("ok1", extra={"licence": "L-test"})])
    web = tmp_path / "web"
    ex = _script("export_web_data")
    assert ex.main(["--results", str(root), "--out", str(web)]) == 0

    doc = _strict_json((web / "results.json").read_text())
    assert doc["nPairs"] == 1 and doc["nFailures"] == 1 and doc["nLoadErrors"] == 0
    failure = doc["failures"][0]
    assert set(failure) == {"status", "detail", "stage", "pair_id", "created_utc"}
    assert failure["status"] == "too_few_matches" and failure["pair_id"] == "bad1"
    assert doc["sourceDirectory"] == os.path.relpath(root.resolve(), REPO)
    assert not Path(doc["sourceDirectory"]).is_absolute()
    assert doc["pairs"][0]["licence"] == "L-test"
    assert (web / "pairs" / doc["pairs"][0]["images"]["matches"]).exists()
    assert not (web / ".export_tmp").exists() and not (web / ".export_old").exists()


def test_export_swap_replaces_the_previous_export_and_leaves_no_scratch(tmp_path):
    root = _store(tmp_path, [_result("ok1")], failures=False)
    web = tmp_path / "web"
    (web / "pairs").mkdir(parents=True)
    (web / "pairs" / "stale.jpg").write_bytes(b"old")
    (web / "results.json").write_text("{}")
    ex = _script("export_web_data")
    assert ex.main(["--results", str(root), "--out", str(web)]) == 0
    assert not (web / "pairs" / "stale.jpg").exists()
    doc = _strict_json((web / "results.json").read_text())
    assert doc["nFailures"] == 0 and doc["failures"] == []
    assert sorted(p.name for p in web.iterdir()) == ["pairs", "results.json"]


def test_failed_export_leaves_the_current_one_untouched(tmp_path, monkeypatch):
    root = _store(tmp_path, [_result("ok1")])
    web = tmp_path / "web"
    ex = _script("export_web_data")
    assert ex.main(["--results", str(root), "--out", str(web)]) == 0
    before_json = (web / "results.json").read_text()
    before_files = sorted(p.name for p in (web / "pairs").iterdir())

    def boom(*args, **kwargs):
        raise RuntimeError("render failed")

    monkeypatch.setattr(ex, "_export", boom)
    with pytest.raises(RuntimeError, match="render failed"):
        ex.main(["--results", str(root), "--out", str(web)])
    assert (web / "results.json").read_text() == before_json
    assert sorted(p.name for p in (web / "pairs").iterdir()) == before_files
    assert not (web / ".export_tmp").exists() and not (web / ".export_old").exists()


def _snapshot(web: Path):
    return (
        (web / "results.json").read_text(),
        sorted(p.name for p in (web / "pairs").iterdir()),
    )


def _images_named_in(web: Path) -> set[str]:
    doc = _strict_json((web / "results.json").read_text())
    return {name for pair in doc["pairs"] for name in pair["images"].values() if name}


def test_failed_results_json_rename_rolls_back_the_new_pairs(tmp_path, monkeypatch):
    old_root = _store(tmp_path / "a", [_result("old1")], failures=False)
    new_root = _store(tmp_path / "b", [_result("new1")], failures=False)
    web = tmp_path / "web"
    ex = _script("export_web_data")
    assert ex.main(["--results", str(old_root), "--out", str(web)]) == 0
    before = _snapshot(web)

    real_replace = os.replace

    def flaky(src, dst):
        if Path(dst).name == "results.json":
            raise OSError("simulated results.json rename failure")
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", flaky)
    with pytest.raises(OSError, match="simulated results.json rename failure"):
        ex.main(["--results", str(new_root), "--out", str(web)])
    monkeypatch.setattr(os, "replace", real_replace)

    assert _snapshot(web) == before
    assert not (web / ".export_old").exists()
    # The next run clears the leftover scratch and keeps the export consistent.
    ex._recover_interrupted_swap(web)
    assert _snapshot(web) == before
    assert sorted(p.name for p in web.iterdir()) == ["pairs", "results.json"]
    assert _images_named_in(web) <= set(before[1])


def test_recovery_finishes_a_swap_killed_between_the_two_renames(tmp_path):
    old_root = _store(tmp_path / "a", [_result("old1")], failures=False)
    new_root = _store(tmp_path / "b", [_result("new1")], failures=False)
    web, staged = tmp_path / "web", tmp_path / "staged"
    ex = _script("export_web_data")
    assert ex.main(["--results", str(old_root), "--out", str(web)]) == 0
    assert ex.main(["--results", str(new_root), "--out", str(staged)]) == 0
    new = _snapshot(staged)
    # The state a kill right after `os.replace(tmp/pairs, pairs)` leaves behind.
    os.replace(web / "pairs", web / ".export_old")
    os.replace(staged / "pairs", web / "pairs")
    (web / ".export_tmp").mkdir()
    os.replace(staged / "results.json", web / ".export_tmp" / "results.json")

    ex._recover_interrupted_swap(web)
    assert _snapshot(web) == new
    assert sorted(p.name for p in web.iterdir()) == ["pairs", "results.json"]
    assert _images_named_in(web) <= set(new[1])


def test_recovery_restores_the_old_pairs_when_killed_before_the_new_moved_in(tmp_path):
    root = _store(tmp_path, [_result("old1")], failures=False)
    web = tmp_path / "web"
    ex = _script("export_web_data")
    assert ex.main(["--results", str(root), "--out", str(web)]) == 0
    before = _snapshot(web)
    # The state a kill right after `os.replace(pairs, .export_old)` leaves behind.
    (web / ".export_tmp" / "pairs").mkdir(parents=True)
    (web / ".export_tmp" / "pairs" / "new_ref.jpg").write_bytes(b"new")
    (web / ".export_tmp" / "results.json").write_text("{}")
    os.replace(web / "pairs", web / ".export_old")

    ex._recover_interrupted_swap(web)
    assert _snapshot(web) == before
    assert sorted(p.name for p in web.iterdir()) == ["pairs", "results.json"]


def test_export_counts_a_corrupt_pair_of_any_error_type(tmp_path):
    root = _store(tmp_path, [_result("ok1"), _result("ok2")], failures=False)
    (root / "pairs" / "ok2.npz").write_bytes(b"not an npz file")
    web = tmp_path / "web"
    ex = _script("export_web_data")
    assert ex.main(["--results", str(root), "--out", str(web)]) == 0
    doc = _strict_json((web / "results.json").read_text())
    assert [p["id"] for p in doc["pairs"]] == ["ok1"]
    assert doc["nLoadErrors"] == 1


def test_export_conditioning_uses_full_resolution_shape_and_counts_outside(tmp_path):
    rng = np.random.default_rng(7)
    src = np.column_stack([rng.uniform(0, 2048, 12), rng.uniform(0, 1024, 12)])
    src[0] = (2100.0, 10.0)  # beyond the 2048-px-wide full-resolution frame
    result = _result(
        "cond",
        src_shape=(1024, 2048),
        ref_shape=(1024, 2048),
        src_pts=src,
        dst_pts=src,
        model="affine",
    )
    root = _store(tmp_path, [result], failures=False)
    web = tmp_path / "web"
    ex = _script("export_web_data")
    assert ex.main(["--results", str(root), "--out", str(web)]) == 0
    pair = _strict_json((web / "results.json").read_text())["pairs"][0]
    assert pair["conditioningModel"]["value"] == "affine"
    assert pair["conditioningModel"]["source"] == "measured"
    assert pair["conditioningPointsOutside"]["value"] == 1
    assert pair["conditioningPointsOutside"]["source"] == "computed"
    assert "conditioning" in pair["images"]


# --------------------------------------------------------------------------
# A119: --exclude-synthetic stash moves
# --------------------------------------------------------------------------


def test_stash_refuses_overwrite_and_suffixes_created_utc(tmp_path):
    root = tmp_path / "results"
    save_results([_result("real1"), _result("syn1", synthetic=True)], root)
    stash = tmp_path / "stash"
    stash.mkdir()
    (stash / "syn1.npz").write_bytes(b"keep me")
    created = load_pair("syn1", root).created_utc

    ri = _script("reindex_results")
    assert ri.main(["--root", str(root), "--exclude-synthetic", "--stash-dir", str(stash)]) == 0
    assert (stash / "syn1.npz").read_bytes() == b"keep me"
    moved = stash / f"syn1_{ri._stamp(created)}.npz"
    assert moved.exists() and not (root / "pairs" / "syn1.npz").exists()


def test_stash_refuses_when_suffixed_name_is_taken_too(tmp_path):
    root = tmp_path / "results"
    save_results([_result("real1"), _result("syn1", synthetic=True)], root)
    created = load_pair("syn1", root).created_utc
    stash = tmp_path / "stash"
    stash.mkdir()
    ri = _script("reindex_results")
    (stash / "syn1.npz").write_bytes(b"a")
    (stash / f"syn1_{ri._stamp(created)}.npz").write_bytes(b"b")
    assert ri.main(["--root", str(root), "--exclude-synthetic", "--stash-dir", str(stash)]) == 1
    assert (root / "pairs" / "syn1.npz").exists()
    assert sorted(p.read_bytes() for p in stash.iterdir()) == [b"a", b"b"]


def test_stash_moves_the_scanned_file_not_a_rebuilt_name(tmp_path):
    root = tmp_path / "results"
    save_results([_result("real1"), _result("syn1", synthetic=True)], root)
    # The file on disk no longer matches its stored pair_id.
    os.replace(root / "pairs" / "syn1.npz", root / "pairs" / "syn1copy.npz")
    stash = tmp_path / "stash"
    ri = _script("reindex_results")
    assert ri.main(["--root", str(root), "--exclude-synthetic", "--stash-dir", str(stash)]) == 0
    assert (stash / "syn1copy.npz").exists()
    assert not (root / "pairs" / "syn1copy.npz").exists()


# --------------------------------------------------------------------------
# A117: synthetic wording
# --------------------------------------------------------------------------


@pytest.mark.parametrize("rel", ["scripts/demo.py", "dashboard/app.py"])
def test_synthetic_wording(rel):
    text = (REPO / rel).read_text()
    assert "this scene is synthetic (generated)" in text
    assert "No Chandrayaan-2 product was available" not in text
    assert "No PDS4 product has been available" not in text
