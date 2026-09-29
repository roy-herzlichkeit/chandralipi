"""P1.17 — run_jaxa, run_ablation, cli register/inspect (Phase_1/LLD/jaxa_cli_ablation.md). Protected (G05)."""

from __future__ import annotations

import json

import numpy as np
import pytest
from _h1 import illumination, load_script, pds4_label


def _tif(path, arr):
    import rasterio

    with rasterio.open(path, "w", driver="GTiff", width=arr.shape[1], height=arr.shape[0],
                       count=1, dtype=arr.dtype) as ds:
        ds.write(arr, 1)
    return path


def test_cli_register(tmp_path, capsys):
    from lunar_reg.cli import main

    src, ref, _, _ = illumination(seed=4, shape=(320, 320))
    a, b = _tif(tmp_path / "a.tif", src), _tif(tmp_path / "b.tif", ref)
    out_json = tmp_path / "r.json"
    code = main(["register", str(a), str(b), "--matcher", "sift", "--output", str(out_json),
                 "--save-root", str(tmp_path / "store"), "--pair-id", "cli_test"])
    assert code == 0, capsys.readouterr().out
    doc = json.loads(out_json.read_text())
    assert doc["status"] == "ok"
    assert (tmp_path / "store" / "pairs" / "cli_test.npz").exists()


def test_cli_register_failure_exit(tmp_path):
    from lunar_reg.cli import main

    z = np.zeros((128, 128), np.uint8)
    a, b = _tif(tmp_path / "a.tif", z), _tif(tmp_path / "b.tif", z)
    assert main(["register", str(a), str(b), "--matcher", "sift"]) == 1


def test_cli_inspect(tmp_path, capsys):
    from lunar_reg.cli import main

    label = tmp_path / "ch2_ohr_x.xml"
    label.write_text(pds4_label(file_name="x.img",
                                geometry={"sun_azimuth": 303.9, "sun_elevation": 11.5}))
    (tmp_path / "x.img").write_bytes(np.zeros(120, np.uint8).tobytes())
    assert main(["inspect", str(label)]) == 0
    assert "product" in capsys.readouterr().out


def test_run_jaxa_missing_inputs(tmp_path, monkeypatch, capsys):
    rj = load_script("run_jaxa")
    monkeypatch.chdir(tmp_path)
    assert rj.main(["--root", str(tmp_path / "store")]) == 1
    assert "input_missing" in capsys.readouterr().out.lower()
    assert {m.value for m in rj.PairPrepStatus} == {"ok", "input_missing", "no_overlap"}


def test_run_ablation_synthetic_only(tmp_path, monkeypatch):
    ra = load_script("run_ablation")
    monkeypatch.setattr(ra, "AZIMUTH_DELTAS", (0,), raising=False)
    monkeypatch.setattr(ra, "SEEDS", (0,), raising=False)
    code = ra.main(["--skip-anchor", "--presets", "none,clahe_shadow", "--matchers", "sift",
                    "--out", str(tmp_path)])
    assert code == 0
    doc = json.loads((tmp_path / "ablation.json").read_text())
    from lunar_reg.preprocess.presets import PRESET_NAMES

    assert doc["winner"] in PRESET_NAMES and doc["synthetic"]
    assert all("truth_rms_px" in r for r in doc["synthetic"])
    assert (tmp_path / "run_record.json").exists()
