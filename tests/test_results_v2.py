"""Results store schema v2: validated ids, refuse-to-overwrite, masks, failures, safe reindex."""

from __future__ import annotations

import json

import numpy as np
import pytest

from lunar_reg.pipeline import PipelineConfig, register_pair, run_batch
from lunar_reg.results import (
    FAILURE_COLUMNS,
    SCHEMA_VERSION,
    PairResult,
    load_failures,
    load_index,
    load_pair,
    reindex,
    save_failures,
    save_pair,
    save_results,
)


def _pair(**overrides) -> PairResult:
    pts = np.arange(20, dtype=float).reshape(10, 2) + 0.25
    base = dict(
        pair_id="p1",
        source_id="s",
        reference_id="r",
        source_sensor="OHRC",
        reference_sensor="LRO_NAC",
        matcher="sift",
        src_pts=pts,
        dst_pts=pts + 0.5,
        inlier_mask=np.r_[np.ones(6, bool), np.zeros(4, bool)],
        transform=np.eye(3),
        ransac_mask=np.r_[np.ones(8, bool), np.zeros(2, bool)],
        pre_ecc_transform=np.eye(3) * 2.0,
    )
    base.update(overrides)
    return PairResult(**base)


def _blank_failure(pair_id: str = "blank"):
    blank = np.zeros((96, 96), np.uint8)
    return register_pair(blank, blank, pair_id, PipelineConfig(matcher="sift", extra={"site": "t"}))


@pytest.mark.parametrize("bad", ["../x", ".x", "a/b", "", "a b"])
def test_invalid_pair_id_rejected(bad):
    with pytest.raises(ValueError, match="invalid pair_id"):
        _pair(pair_id=bad)


def test_mask_lengths_are_checked():
    with pytest.raises(ValueError, match="ransac mask"):
        _pair(ransac_mask=np.ones(3, bool))


def test_overwrite_refused_and_no_tmp_left(tmp_path):
    path = save_pair(_pair(), tmp_path)
    assert path == tmp_path / "pairs" / "p1.npz"
    with pytest.raises(FileExistsError):
        save_pair(_pair(), tmp_path)
    with pytest.raises(FileExistsError):
        save_results([_pair(pair_id="new"), _pair()], tmp_path)
    assert not (tmp_path / "pairs" / "new.npz").exists(), "a clash must stop the whole batch"
    save_pair(_pair(notes="second"), tmp_path, overwrite=True)
    assert load_pair("p1", tmp_path).notes == "second"
    assert not [p for p in tmp_path.rglob("*") if p.name.endswith(".tmp")]


def test_v2_round_trip_keeps_masks_and_pre_ecc_transform(tmp_path):
    original = _pair()
    save_pair(original, tmp_path)
    back = load_pair("p1", tmp_path)
    assert back.schema_version == SCHEMA_VERSION == 2
    np.testing.assert_array_equal(back.ransac_mask, original.ransac_mask)
    np.testing.assert_array_equal(back.inlier_mask, original.inlier_mask)
    np.testing.assert_array_equal(back.pre_ecc_transform, original.pre_ecc_transform)
    np.testing.assert_array_equal(back.src_pts, original.src_pts)
    assert (back.n_matches, back.n_ransac_inliers, back.n_inliers) == (10, 8, 6)


def test_v1_file_loads(tmp_path):
    (tmp_path / "pairs").mkdir()
    meta = {
        "pair_id": "old", "source_id": "s", "reference_id": "r", "source_sensor": "A",
        "reference_sensor": "B", "matcher": "sift", "metrics": {}, "uniformity": {},
        "conditioning": {}, "synthetic": False, "notes": "", "extra": {},
        "created_utc": "2026-09-01T00:00:00+00:00", "source_scale": 1.0,
        "reference_scale": 1.0, "schema_version": 1,
    }  # fmt: skip
    np.savez_compressed(
        tmp_path / "pairs" / "old.npz",
        src_pts=np.zeros((3, 2)),
        dst_pts=np.ones((3, 2)),
        transform=np.eye(3),
        meta=np.array(json.dumps(meta)),
        inlier_mask=np.ones(3, bool),
    )
    old = load_pair("old", tmp_path)
    assert old.schema_version == 1
    assert old.ransac_mask is None and old.pre_ecc_transform is None
    assert old.n_ransac_inliers is None
    assert old.index_row()["schema_version"] == 1


def test_index_json_encodes_containers_and_rejects_objects():
    row = _pair(extra={"crop": [1, 2], "shape": (3, 4), "arr": np.array([0.5])}).index_row()
    assert json.loads(row["x_crop"]) == [1, 2]
    assert json.loads(row["x_shape"]) == [3, 4]
    assert json.loads(row["x_arr"]) == [0.5]
    assert row["n_ransac_inliers"] == 8 and row["inlier_ratio"] == pytest.approx(0.6)
    with pytest.raises(TypeError, match="x_handle"):
        _pair(extra={"handle": object()}).index_row()


def test_failures_parquet_columns_and_append(tmp_path):
    assert len(load_failures(tmp_path)) == 0
    path = save_failures([_blank_failure()], tmp_path)
    assert path == tmp_path / "failures.parquet"
    frame = load_failures(tmp_path)
    assert tuple(frame.columns[: len(FAILURE_COLUMNS)]) == FAILURE_COLUMNS
    assert frame.loc[0, "status"] == "too_few_matches"
    assert frame.loc[0, "stage"] == "match"
    assert frame.loc[0, "x_site"] == "t"
    save_failures([_blank_failure("blank2")], tmp_path)
    assert list(load_failures(tmp_path)["pair_id"]) == ["blank", "blank2"]


def test_reindex_keeps_index_when_a_file_is_corrupt(tmp_path):
    store = save_results([_pair(pair_id="a"), _pair(pair_id="b")], tmp_path)
    assert store.n_saved == 2 and store.index_written and len(store.frame) == 2
    (tmp_path / "pairs" / "b.npz").write_bytes(b"not an npz")

    kept = reindex(tmp_path)
    assert kept.index_written is False
    assert len(load_index(tmp_path)) == 2
    assert [pid for pid, _ in kept.load_failures] == ["b"]
    assert "KEPT" in kept.report() and "b" in kept.report()

    forced = reindex(tmp_path, force=True)
    assert forced.index_written is True
    assert list(load_index(tmp_path)["pair_id"]) == ["a"]


def test_run_batch_writes_failures_parquet(tmp_path):
    blank = np.zeros((96, 96), np.uint8)
    report = run_batch(
        [dict(source=blank, reference=blank, pair_id="blank")],
        PipelineConfig(matcher="sift"),
        root=tmp_path,
    )
    assert len(report.failures) == 1
    assert list(load_failures(tmp_path)["status"]) == ["too_few_matches"]
    assert report.store is not None and report.store.n_saved == 0
    assert "too_few_matches" in report.report() and "store" in report.report()
