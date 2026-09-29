"""P0.10 — results store v2 wiring (Phase_0/LLD/results_v2.md). Protected (G05).

C04/C05 themselves are in test_contracts_P0.py; these cover the pipeline wiring and callers.
"""

from __future__ import annotations

import numpy as np
from _h0 import REPO, exact_matches, textured


class _Stub:
    name = "stub"

    def __init__(self, result):
        self._result = result

    def match(self, source, reference):
        return self._result


def test_register_pair_fills_v2_fields(monkeypatch):
    from lunar_reg.pipeline import PipelineConfig, register_pair

    raw, _ = exact_matches(n_in=60, n_out=40)
    monkeypatch.setattr("lunar_reg.pipeline._build_matcher", lambda name, **kw: _Stub(raw))
    out = register_pair(textured((400, 400), 3), textured((400, 400), 4), "p",
                        PipelineConfig(matcher="stub", use_ecc=False, n_bootstrap=0))
    r = out.result
    assert r.ransac_mask is not None and len(r.ransac_mask) == 100
    assert r.pre_ecc_transform is not None and r.pre_ecc_transform.shape == (3, 3)
    # refit inliers are a subset of RANSAC inliers
    assert not np.any(r.inlier_mask & ~r.ransac_mask)
    row = r.index_row()
    assert row["n_ransac_inliers"] == int(r.ransac_mask.sum())


def test_run_batch_store_report(tmp_path, monkeypatch):
    from lunar_reg.pipeline import PipelineConfig, run_batch
    from lunar_reg.results import load_index

    raw, _ = exact_matches()
    monkeypatch.setattr("lunar_reg.pipeline._build_matcher", lambda name, **kw: _Stub(raw))
    img = textured((400, 400), 3)
    report = run_batch([dict(source=img, reference=img, pair_id="ok1")],
                       PipelineConfig(matcher="stub", use_ecc=False, n_bootstrap=0),
                       root=tmp_path)
    assert report.store is not None and report.store.n_saved == 1
    assert list(load_index(tmp_path)["pair_id"]) == ["ok1"]


def test_callers_updated():
    vikram = (REPO / "scripts/run_vikram.py").read_text()
    demo = (REPO / "scripts/build_demo_results.py").read_text()
    reidx = (REPO / "scripts/reindex_results.py").read_text()
    assert "frame = save_results(" not in vikram
    assert "frame = save_results(" not in demo
    assert "--force" in reidx and ".report()" in reidx


def test_no_tmp_left_and_atomic_index(tmp_path):
    from lunar_reg.results import PairResult, save_results

    pts = np.zeros((4, 2))
    r = PairResult("a", "s", "r", "A", "B", "m", pts, pts, None, np.eye(3))
    save_results([r], tmp_path)
    assert not [p for p in tmp_path.rglob("*") if p.name.endswith(".tmp")]
    assert (tmp_path / "index.parquet").exists()
