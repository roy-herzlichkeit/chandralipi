"""P0.07 — provenance, run record, seeded fit (Phase_0/LLD/provenance_runrecord_fit.md). Protected (G05).

Contract behaviour (C01, C06, C15) is in test_contracts_P0.py; these are the LLD extras.
"""

from __future__ import annotations

import json

import numpy as np
from _h0 import REPO, exact_matches


def test_affine_shapes_and_estimators():
    from lunar_reg.align.estimate import estimate_transform

    m, _ = exact_matches(n_in=120, n_out=20)
    t_h, _ = estimate_transform(m, "homography")
    m, _ = exact_matches(n_in=120, n_out=20, H=np.array([[1.0, 0.01, 3], [0.0, 0.99, 2], [0, 0, 1]]))
    t_a, _ = estimate_transform(m, "affine")
    t_p, _ = estimate_transform(m, "partial_affine")
    assert t_h.matrix.shape == (3, 3) and t_h.estimator == "USAC_MAGSAC"
    assert t_a.matrix.shape == (2, 3) and t_a.estimator == "RANSAC"
    assert t_p.matrix.shape == (2, 3) and t_p.estimator == "RANSAC"


def test_input_points_not_modified():
    from lunar_reg.align.estimate import estimate_transform

    m, _ = exact_matches()
    before = m.src_pts.copy(), m.dst_pts.copy()
    estimate_transform(m)
    assert np.array_equal(m.src_pts, before[0]) and np.array_equal(m.dst_pts, before[1])
    assert m.src_pts.dtype == np.float64


def test_docstring_corrected():
    text = (REPO / "src/lunar_reg/align/estimate.py").read_text().split('"""')[1]
    assert "affine" in text.lower() and "ransac" in text.lower()


def test_runrecord_timestamps_and_paths(tmp_path, monkeypatch):
    from lunar_reg.runrecord import finish_run, start_run, write_run_record

    monkeypatch.chdir(REPO)
    art = REPO / "pyproject.toml"
    rec = finish_run(start_run(["x"]), {"ok": 1}, [art])
    data = json.loads(write_run_record(rec, tmp_path).read_text())
    assert data["started_utc"].endswith("Z") and data["finished_utc"].endswith("Z")
    assert data["artefacts"] == ["pyproject.toml"]
    assert isinstance(data["git_dirty"], bool)
    assert not list(tmp_path.glob(".*.tmp"))
