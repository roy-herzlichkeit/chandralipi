"""Seeded, float64-safe robust fit (C06) and the run record round trip (C15)."""

from __future__ import annotations

import json
import subprocess
import sys

import numpy as np
import pytest

from lunar_reg.align.estimate import estimate_transform
from lunar_reg.match.base import MatchResult

H_TRUE = np.array([[1.01, 0.02, 12.0], [-0.015, 0.99, -7.0], [1e-5, -2e-5, 1.0]])

#: Builds the same 200-point, 30 %-outlier set in this process and in a subprocess.
_MAKE_POINTS = """
import numpy as np
from lunar_reg.match.base import MatchResult

def make_points():
    H = np.array([[1.01, 0.02, 12.0], [-0.015, 0.99, -7.0], [1e-5, -2e-5, 1.0]])
    rng = np.random.default_rng(21)
    n_in, n_out = 140, 60
    src_in = rng.uniform(10, 390, (n_in, 2))
    hom = np.c_[src_in, np.ones(n_in)] @ H.T
    dst_in = hom[:, :2] / hom[:, 2:3]
    src_out = rng.uniform(10, 390, (n_out, 2))
    dst_out = rng.uniform(10, 390, (n_out, 2))
    return MatchResult(np.vstack([src_in, src_out]), np.vstack([dst_in, dst_out]))
"""

_namespace: dict = {}
exec(_MAKE_POINTS, _namespace)  # noqa: S102 - the same source runs in the subprocess test
make_points = _namespace["make_points"]


@pytest.mark.parametrize("model", ["homography", "affine", "partial_affine"])
def test_repeat_calls_are_bit_identical(model):
    t1, r1 = estimate_transform(make_points(), model=model, seed=3)
    t2, r2 = estimate_transform(make_points(), model=model, seed=3)
    assert np.array_equal(t1.matrix, t2.matrix)
    assert np.array_equal(r1.inlier_mask, r2.inlier_mask)
    assert t1.seed == 3


def test_subprocess_gives_identical_matrix():
    t, _ = estimate_transform(make_points(), seed=7)
    code = (
        _MAKE_POINTS
        + "\nfrom lunar_reg.align.estimate import estimate_transform"
        + "\nprint(estimate_transform(make_points(), seed=7)[0].matrix.tobytes().hex())"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == t.matrix.tobytes().hex()


@pytest.mark.parametrize("model", ["homography", "affine", "partial_affine"])
def test_large_coordinates_keep_subpixel_precision(model):
    rng = np.random.default_rng(5)
    src = 5e5 + rng.uniform(0, 2000, (100, 2))
    dst = src + np.array([12.25, -7.5])
    t, _ = estimate_transform(MatchResult(src, dst), model=model, threshold_px=1.0)
    assert np.abs(t.apply(src) - dst).max() < 1e-3


def test_model_shapes_and_estimators():
    th, _ = estimate_transform(make_points(), model="homography")
    ta, _ = estimate_transform(make_points(), model="affine")
    tp, _ = estimate_transform(make_points(), model="partial_affine")
    assert th.matrix.shape == (3, 3) and th.estimator == "USAC_MAGSAC"
    assert ta.matrix.shape == (2, 3) and ta.estimator == "RANSAC"
    assert tp.matrix.shape == (2, 3) and tp.estimator == "RANSAC"
    assert th.matrix.dtype == np.float64


def test_homography_recovers_truth_and_leaves_input_untouched():
    m = make_points()
    src_before, dst_before = m.src_pts.copy(), m.dst_pts.copy()
    t, r = estimate_transform(m)
    assert np.array_equal(m.src_pts, src_before) and np.array_equal(m.dst_pts, dst_before)
    assert r.inlier_mask[:140].all()
    assert np.allclose(t.matrix, H_TRUE, rtol=1e-4, atol=1e-6)


def test_run_record_round_trip(tmp_path, monkeypatch):
    from lunar_reg.runrecord import (
        finish_run,
        read_run_record,
        start_run,
        validate_run_record,
        write_run_record,
    )

    monkeypatch.chdir(tmp_path)
    (tmp_path / "result.parquet").write_bytes(b"x")
    record = start_run(["run_vikram.py", "--matcher", "sift"], {"matcher": "sift"})
    record = finish_run(record, {"ok": 3, "too_few_matches": 1}, ["result.parquet"])
    path = write_run_record(record, tmp_path / "out")

    assert path == tmp_path / "out" / "run_record.json"
    data = json.loads(path.read_text())
    assert data["started_utc"].endswith("Z") and data["finished_utc"].endswith("Z")
    assert data["versions"]["python"] == ".".join(map(str, sys.version_info[:3]))
    assert validate_run_record(path) == []
    back = read_run_record(path)
    assert back.outcome_counts == {"ok": 3, "too_few_matches": 1}
    assert back.params == {"matcher": "sift"}
    assert not list((tmp_path / "out").glob(".*.tmp"))


def test_run_record_validation_problems(tmp_path):
    from lunar_reg.runrecord import start_run, validate_run_record, write_run_record

    path = write_run_record(start_run(["p"]), tmp_path)  # never finished
    problems = validate_run_record(path)
    assert any("finished_utc" in p for p in problems)

    data = json.loads(path.read_text())
    data["outcome_counts"] = {"ok": -1}
    del data["host"]
    path.write_text(json.dumps(data))
    problems = validate_run_record(path)
    assert any("host" in p for p in problems)
    assert any("outcome_counts" in p for p in problems)
