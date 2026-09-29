"""P1.21 — viewers (Phase_1/LLD/viewers_docs.md §P1.21). Protected (G05)."""

from __future__ import annotations

import json
import os

import numpy as np
from _h1 import REPO, load_script


def test_side_by_side_scales():
    import inspect

    from lunar_reg.viz.figures import side_by_side_matches

    params = inspect.signature(side_by_side_matches).parameters
    assert "src_scale" in params and "ref_scale" in params and "scale" not in params


def test_export_atomic_with_failures(tmp_path, monkeypatch):
    from lunar_reg.pipeline import PipelineConfig, register_pair
    from lunar_reg.results import PairResult, save_failures, save_results

    root = tmp_path / "store"
    pts = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0], [7.0, 1.0]])
    r = PairResult("ok1", "s", "r", "A", "B", "sift", pts, pts, np.ones(4, bool), np.eye(3),
                   metrics={"model": "homography"}, source_image=np.zeros((40, 40), np.uint8),
                   reference_image=np.zeros((40, 40), np.uint8), extra={"licence": "L"})
    save_results([r], root)
    blank = np.zeros((64, 64), np.uint8)
    save_failures([register_pair(blank, blank, "bad1", PipelineConfig(matcher="sift"))], root)
    web = tmp_path / "web"
    ex = load_script("export_web_data")
    code = ex.main(["--results", str(root), "--out", str(web)])
    assert code == 0
    doc = json.loads((web / "results.json").read_text())
    assert doc["nFailures"] == 1 and doc["failures"][0]["status"] == "too_few_matches"
    assert doc["sourceDirectory"] == os.path.relpath(root.resolve(), REPO)
    assert not list(web.glob(".export_*"))


def test_demo_text_updated():
    for rel in ("scripts/demo.py", "dashboard/app.py"):
        text = (REPO / rel).read_text()
        assert "No Chandrayaan-2 product was available" not in text
        assert "No PDS4 product has been available" not in text
