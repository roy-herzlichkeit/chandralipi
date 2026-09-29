"""Phase 0 contract tests: CONTRACTS.md C01-C07 and C15 (G16). Protected (G05)."""

from __future__ import annotations

import dataclasses
import inspect
import json
import subprocess
import sys

import numpy as np
import pytest
from _h0 import exact_matches, textured

# --------------------------------------------------------------------- C01


def test_C01_members():
    from lunar_reg.provenance import ValueSource

    assert issubclass(ValueSource, str)
    assert [(m.name, m.value) for m in ValueSource] == [
        ("MEASURED", "measured"),
        ("COMPUTED", "computed"),
        ("DOCUMENTED", "documented"),
        ("INFERRED", "inferred"),
        ("UNKNOWN", "unknown"),
    ]


def test_C01_sourced_as_dict():
    from lunar_reg.provenance import Sourced, ValueSource

    s = Sourced(3.0, ValueSource.INFERRED, "why")
    assert s.as_dict() == {"value": 3.0, "source": "inferred", "note": "why"}
    assert Sourced(1, ValueSource.MEASURED).note == ""
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.value = 1.0  # type: ignore[misc]


# --------------------------------------------------------------------- C02

C02_MEMBERS = {
    "OK": "ok",
    "TOO_FEW_MATCHES": "too_few_matches",
    "ESTIMATION_FAILED": "estimation_failed",
    "TOO_FEW_INLIERS": "too_few_inliers",
    "MATCHER_ERROR": "matcher_error",
    "REFINEMENT_FAILED": "refinement_failed",
    "EVAL_FAILED": "eval_failed",
    "PREPROCESS_FAILED": "preprocess_failed",
    "OOM": "oom",
}


def test_C02_members():
    from lunar_reg.pipeline import RunOutcome, RunStatus

    assert {m.name: m.value for m in RunStatus} == C02_MEMBERS
    assert not RunStatus.OK.is_failure
    assert all(m.is_failure for m in RunStatus if m is not RunStatus.OK)
    names = [f.name for f in dataclasses.fields(RunOutcome)]
    assert names == ["pair_id", "status", "result", "detail", "extra"]


def test_C02_failure_extra_keys():
    from lunar_reg.pipeline import PipelineConfig, RunStatus, register_pair

    blank = np.zeros((128, 128), np.uint8)
    out = register_pair(
        blank, blank, "blank", PipelineConfig(matcher="sift", extra={"site": "test"}),
        source_id="s", reference_id="r", source_sensor="A", reference_sensor="B",
    )
    assert out.status is RunStatus.TOO_FEW_MATCHES
    for key in ("source_id", "reference_id", "source_sensor", "reference_sensor",
                "matcher", "model", "stage"):
        assert key in out.extra, f"RunOutcome.extra lacks {key!r} (C02)"
    assert out.extra["stage"] == "match"
    assert out.extra["site"] == "test"
    assert out.extra["n_raw_matches"] == 0
    assert out.extra["source_sensor"] == "A"


# --------------------------------------------------------------------- C03

C03_P0_DEFAULTS = {
    "matcher": "akaze",
    "model": "homography",
    "ransac_threshold_px": 3.0,
    "use_ecc": True,
    "ecc_prefilter": "none",
    "min_matches": 8,
    "min_inliers": 8,
    "n_bootstrap": 40,
    "gsd_m": None,
    "refit_threshold_px": 1.0,
    "seed": 0,
    "ecc_max_shift_px": 3.0,
    "nodata": None,
}


def test_C03_fields_and_defaults():
    from lunar_reg.pipeline import PipelineConfig

    fields = {f.name: f for f in dataclasses.fields(PipelineConfig)}
    for name, default in C03_P0_DEFAULTS.items():
        assert name in fields, f"PipelineConfig lacks {name} (C03)"
        assert fields[name].default == default, f"{name} default"
    assert "extra" in fields
    assert PipelineConfig().extra == {}


def test_C03_signature():
    from lunar_reg.pipeline import register_pair

    params = inspect.signature(register_pair).parameters
    assert list(params)[:12] == [
        "source", "reference", "pair_id", "config", "source_id", "reference_id",
        "source_sensor", "reference_sensor", "source_sun", "reference_sun",
        "synthetic", "notes",
    ]
    for name in ("source_valid", "reference_valid"):
        assert name in params and params[name].default is None


# --------------------------------------------------------------------- C04

C04_FIELDS = [
    "pair_id", "source_id", "reference_id", "source_sensor", "reference_sensor", "matcher",
    "src_pts", "dst_pts", "inlier_mask", "transform", "metrics", "uniformity",
    "conditioning", "source_image", "reference_image", "synthetic", "notes", "extra",
    "created_utc", "ransac_mask", "pre_ecc_transform", "schema_version",
]
C04_TOP = [
    "pair_id", "source_id", "reference_id", "source_sensor", "reference_sensor", "matcher",
    "n_matches", "n_ransac_inliers", "n_inliers", "inlier_ratio", "synthetic", "notes",
    "created_utc", "schema_version",
]


def _pair(**overrides):
    from lunar_reg.results import PairResult

    pts = np.arange(20, dtype=float).reshape(10, 2)
    base = dict(
        pair_id="p1", source_id="s", reference_id="r", source_sensor="A",
        reference_sensor="B", matcher="sift", src_pts=pts, dst_pts=pts + 0.5,
        inlier_mask=np.r_[np.ones(6, bool), np.zeros(4, bool)], transform=np.eye(3),
        ransac_mask=np.r_[np.ones(8, bool), np.zeros(2, bool)], pre_ecc_transform=np.eye(3),
        metrics={"rmse_px": np.float64(0.4)}, extra={"window_m": 3000.0},
    )
    base.update(overrides)
    return PairResult(**base)


def test_C04_fields():
    from lunar_reg.results import PAIR_ID_PATTERN, SCHEMA_VERSION, PairResult

    assert SCHEMA_VERSION == 2
    assert PAIR_ID_PATTERN == r"^[A-Za-z0-9][A-Za-z0-9._-]*$"
    assert [f.name for f in dataclasses.fields(PairResult)] == C04_FIELDS
    r = _pair()
    assert (r.n_matches, r.n_inliers, r.n_ransac_inliers) == (10, 6, 8)
    assert r.schema_version == 2
    assert _pair(ransac_mask=None).n_ransac_inliers is None


def test_C04_index_columns():
    row = _pair(extra={"lst": [1, 2], "arr": np.array([1.5])}).index_row()
    assert list(row)[:14] == C04_TOP
    assert row["inlier_ratio"] == pytest.approx(0.6)
    assert row["n_ransac_inliers"] == 8
    assert row["m_rmse_px"] == pytest.approx(0.4) and isinstance(row["m_rmse_px"], float)
    assert json.loads(row["x_lst"]) == [1, 2]
    assert json.loads(row["x_arr"]) == [1.5]
    with pytest.raises(TypeError, match="x_obj"):
        _pair(extra={"obj": object()}).index_row()


@pytest.mark.parametrize("bad", ["../x", ".hidden", "a/b", "", "a b", "-x"])
def test_C04_pair_id_rejected(bad):
    with pytest.raises(ValueError):
        _pair(pair_id=bad)


def test_C04_overwrite_refused(tmp_path):
    from lunar_reg.results import load_pair, save_pair

    r = _pair()
    path = save_pair(r, tmp_path)
    assert path == tmp_path / "pairs" / "p1.npz"
    with pytest.raises(FileExistsError):
        save_pair(r, tmp_path)
    save_pair(r, tmp_path, overwrite=True)
    assert not list(tmp_path.rglob("*.tmp"))
    back = load_pair("p1", tmp_path)
    assert back.schema_version == 2
    np.testing.assert_array_equal(back.ransac_mask, r.ransac_mask)
    np.testing.assert_array_equal(back.pre_ecc_transform, np.eye(3))
    assert back.src_pts.dtype == np.float64


def test_C04_v1_loads(tmp_path):
    from lunar_reg.results import load_pair

    (tmp_path / "pairs").mkdir()
    meta = {
        "pair_id": "old", "source_id": "s", "reference_id": "r", "source_sensor": "A",
        "reference_sensor": "B", "matcher": "sift", "metrics": {}, "uniformity": {},
        "conditioning": {}, "synthetic": False, "notes": "", "extra": {},
        "created_utc": "2026-09-01T00:00:00+00:00", "source_scale": 1.0,
        "reference_scale": 1.0, "schema_version": 1,
    }
    np.savez_compressed(
        tmp_path / "pairs" / "old.npz", src_pts=np.zeros((3, 2)), dst_pts=np.ones((3, 2)),
        transform=np.eye(3), meta=np.array(json.dumps(meta)), inlier_mask=np.ones(3, bool),
    )
    r = load_pair("old", tmp_path)
    assert r.schema_version == 1
    assert r.ransac_mask is None and r.pre_ecc_transform is None
    assert r.n_inliers == 3


# --------------------------------------------------------------------- C05

C05_COLUMNS = [
    "pair_id", "status", "detail", "stage", "matcher", "model", "source_id", "reference_id",
    "source_sensor", "reference_sensor", "n_raw_matches", "n_ransac_inliers", "created_utc",
    "schema_version",
]


def _blank_failure(pair_id="blank"):
    from lunar_reg.pipeline import PipelineConfig, register_pair

    blank = np.zeros((96, 96), np.uint8)
    return register_pair(blank, blank, pair_id, PipelineConfig(matcher="sift", extra={"site": "t"}))


def test_C05_failures_columns(tmp_path):
    from lunar_reg.results import load_failures, save_failures

    assert len(load_failures(tmp_path)) == 0
    path = save_failures([_blank_failure()], tmp_path)
    assert path == tmp_path / "failures.parquet"
    frame = load_failures(tmp_path)
    assert list(frame.columns)[:14] == C05_COLUMNS
    assert "x_site" in frame.columns
    assert frame.loc[0, "status"] == "too_few_matches"
    save_failures([_blank_failure("blank2")], tmp_path)
    assert len(load_failures(tmp_path)) == 2  # appended, never rewritten


def test_C05_reindex_keeps_index(tmp_path):
    from lunar_reg.results import StoreReport, load_index, reindex, save_results

    report = save_results([_pair(pair_id="a"), _pair(pair_id="b")], tmp_path)
    assert isinstance(report, StoreReport)
    assert report.n_saved == 2 and len(report.frame) == 2 and report.index_written
    (tmp_path / "pairs" / "b.npz").write_bytes(b"not an npz")
    kept = reindex(tmp_path)
    assert kept.index_written is False
    assert len(load_index(tmp_path)) == 2
    assert [pid for pid, _ in kept.load_failures] == ["b"]
    assert "KEPT" in kept.report()
    forced = reindex(tmp_path, force=True)
    assert forced.index_written is True and len(load_index(tmp_path)) == 1


def test_C05_run_batch_persists_failures(tmp_path):
    from lunar_reg.pipeline import PipelineConfig, run_batch
    from lunar_reg.results import load_failures

    blank = np.zeros((96, 96), np.uint8)
    report = run_batch(
        [dict(source=blank, reference=blank, pair_id="blank")],
        PipelineConfig(matcher="sift"), root=tmp_path,
    )
    assert len(report.failures) == 1
    frame = load_failures(tmp_path)
    assert list(frame["status"]) == ["too_few_matches"]
    assert "too_few_matches" in report.report()


# --------------------------------------------------------------------- C06


def test_C06_signature():
    from lunar_reg.align.estimate import TRANSFORM_MODELS, Transform, estimate_transform

    assert TRANSFORM_MODELS == ("homography", "affine", "partial_affine")
    params = inspect.signature(estimate_transform).parameters
    assert list(params) == ["result", "model", "threshold_px", "max_iters", "confidence", "seed"]
    assert params["seed"].default == 0
    fields = [f.name for f in dataclasses.fields(Transform)]
    assert fields == ["matrix", "model", "n_inliers", "n_total", "estimator", "seed"]


def test_C06_deterministic():
    from lunar_reg.align.estimate import estimate_transform

    first, _ = exact_matches(n_in=140, n_out=60)
    second, _ = exact_matches(n_in=140, n_out=60)
    t1, r1 = estimate_transform(first, seed=5)
    t2, r2 = estimate_transform(second, seed=5)
    assert np.array_equal(t1.matrix, t2.matrix)
    assert np.array_equal(r1.inlier_mask, r2.inlier_mask)
    assert t1.estimator == "USAC_MAGSAC" and t1.seed == 5
    code = (
        "import sys; sys.path.insert(0, 'Phase_0/harness/tests');"
        "from _h0 import exact_matches;"
        "from lunar_reg.align.estimate import estimate_transform;"
        "m, _ = exact_matches(n_in=140, n_out=60);"
        "print(estimate_transform(m, seed=5)[0].matrix.tobytes().hex())"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == t1.matrix.tobytes().hex()


@pytest.mark.parametrize("model", ["homography", "affine", "partial_affine"])
def test_C06_large_coordinates(model):
    from lunar_reg.align.estimate import estimate_transform
    from lunar_reg.match.base import MatchResult

    rng = np.random.default_rng(3)
    src = 5e5 + rng.uniform(0, 3000, (100, 2))
    dst = src + np.array([12.25, -7.5])
    t, _ = estimate_transform(MatchResult(src, dst), model=model, threshold_px=1.0)
    assert t.matrix.shape == ((3, 3) if model == "homography" else (2, 3))
    assert np.abs(t.apply(src) - dst).max() < 1e-3


# --------------------------------------------------------------------- C07

C07_MEMBERS = {
    "APPLIED": "applied",
    "SKIPPED_NO_SIMILARITY_MOTION": "skipped_no_similarity_motion",
    "SKIPPED_SINGULAR": "skipped_singular",
    "SKIPPED_DISABLED": "skipped_disabled",
    "NOT_CONVERGED": "not_converged",
    "REJECTED_DISPLACEMENT": "rejected_displacement",
}


def test_C07_status_members():
    from lunar_reg.align.refine import ECC_MAX_SHIFT_PX, EccOutcome, EccStatus

    assert {m.name: m.value for m in EccStatus} == C07_MEMBERS
    assert [f.name for f in dataclasses.fields(EccOutcome)] == [
        "transform", "status", "cc", "motion", "shift_px", "detail"]
    assert ECC_MAX_SHIFT_PX.value == 3.0
    assert ECC_MAX_SHIFT_PX.source.value == "inferred"


def _affine_scene():
    import cv2

    src = textured((256, 256))
    A = np.array([[1.02, 0.03, 5.0], [-0.02, 0.99, -3.0]])
    ref = cv2.warpAffine(src, A, (256, 256), flags=cv2.INTER_CUBIC)
    return src, ref, A


def test_C07_affine_stays_affine():
    from lunar_reg.align.estimate import Transform
    from lunar_reg.align.refine import EccStatus, ecc_refine

    src, ref, A = _affine_scene()
    start = A.copy()
    start[:, 2] += (0.6, -0.4)
    out = ecc_refine(Transform(start, "affine", 50, 50), src, ref)
    assert out.status is EccStatus.APPLIED
    assert out.motion == "affine"
    assert out.transform.model == "affine" and out.transform.matrix.shape == (2, 3)
    probes = np.array([[40.0, 40.0], [200.0, 40.0], [40.0, 200.0], [200.0, 200.0]])
    truth = np.c_[probes, np.ones(4)] @ A.T
    assert np.abs(out.transform.apply(probes) - truth).max() < 0.1


def test_C07_detail_keys():
    from lunar_reg.align.refine import EccStatus, refine_full
    from lunar_reg.match.base import MatchResult

    src, ref, A = _affine_scene()
    pts = np.random.default_rng(1).uniform(20, 230, (60, 2))
    dst = np.c_[pts, np.ones(60)] @ A.T
    m = MatchResult(pts, dst, inlier_mask=np.ones(60, bool))
    transform, _, detail = refine_full(m, src, ref, model="affine", threshold_px=1.0, seed=0)
    for key in ("stages", "inliers_after_refit", "pre_ecc_matrix", "ecc_status",
                "ecc_motion", "ecc_cc", "ecc_shift_px"):
        assert key in detail, f"refine_full detail lacks {key!r} (C07)"
    assert detail["ecc_status"] in {m.value for m in EccStatus}
    assert transform.matrix.shape == (2, 3)
    _, _, off = refine_full(m, None, None, model="affine", use_ecc=False)
    assert off["ecc_status"] == "skipped_disabled"


# --------------------------------------------------------------------- C15

C15_KEYS = {
    "schema", "command", "params", "started_utc", "finished_utc", "git_sha", "git_dirty",
    "host", "device", "versions", "outcome_counts", "artefacts", "notes",
}


def test_C15_roundtrip(tmp_path, monkeypatch):
    from lunar_reg.runrecord import (
        finish_run, read_run_record, start_run, validate_run_record, write_run_record,
    )

    monkeypatch.chdir(tmp_path)
    (tmp_path / "out.txt").write_text("x")
    rec = start_run(["prog", "--flag"], {"a": 1})
    rec = finish_run(rec, {"ok": 2, "too_few_matches": 1}, ["out.txt"])
    path = write_run_record(rec, tmp_path / "run")
    assert path == tmp_path / "run" / "run_record.json"
    data = json.loads(path.read_text())
    assert set(data) == C15_KEYS
    assert data["schema"] == 1 and data["command"] == ["prog", "--flag"]
    assert len(data["git_sha"]) == 40
    assert set(data["versions"]) >= {"python", "numpy", "cv2", "torch", "kornia"}
    assert read_run_record(path).outcome_counts == {"ok": 2, "too_few_matches": 1}
    assert validate_run_record(path) == []


def test_C15_validate_flags_missing_artefact(tmp_path, monkeypatch):
    from lunar_reg.runrecord import finish_run, start_run, validate_run_record, write_run_record

    monkeypatch.chdir(tmp_path)
    rec = finish_run(start_run(["p"]), {"ok": 1}, ["missing.bin"])
    path = write_run_record(rec, tmp_path)
    problems = validate_run_record(path)
    assert problems and any("missing.bin" in p for p in problems)
    (tmp_path / "bad.json").write_text("{not json")
    assert validate_run_record(tmp_path / "bad.json")
