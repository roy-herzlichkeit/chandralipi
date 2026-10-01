"""P1.15 — TMC-2 / IIRS ingest (Phase_1/LLD/tmc2_iirs.md). Protected (G05)."""

from __future__ import annotations

import numpy as np
import pytest
from _h1 import REPO, pds4_label


@pytest.mark.parametrize("axes,expected", [
    ((("Band", 3), ("Line", 10), ("Sample", 12)), 0),
    ((("Line", 10), ("Sample", 12), ("Band", 3)), 2),
    ((("Line", 10), ("Sample", 12)), None),
])
def test_band_axis(tmp_path, axes, expected):
    from lunar_reg.ingest.pds4 import read_label

    p = tmp_path / "ch2_iir_x.xml"
    p.write_text(pds4_label(lid="urn:isro:isda:ch2_iir:x", file_name="x.img", axes=axes,
                            array_kind="Array_3D_Spectrum" if len(axes) == 3 else "Array_2D_Image"))
    product = read_label(p)
    assert product.band_axis == expected
    assert product.view is None


def test_incremental_pca_route():
    from rasterio.io import MemoryFile

    from lunar_reg.preprocess.config import PreprocessConfig
    from lunar_reg.preprocess.pipeline import PreprocessContext, run_pipeline

    rng = np.random.default_rng(0)
    base = rng.normal(0, 1, (64, 64)).astype(np.float32)
    cube = np.stack([base * k + rng.normal(0, 0.01, base.shape).astype(np.float32)
                     for k in (1.0, 2.0, 3.0)])
    cfg = PreprocessConfig(band_reduction=True, band_reduction_method="pca", resample=False,
                           normalize=False, clahe=False, shadow=False)
    with MemoryFile() as mem:
        with mem.open(driver="GTiff", width=64, height=64, count=3, dtype="float32") as ds:
            ds.write(cube)
        with mem.open() as ds:
            inc = run_pipeline(cube, cfg, PreprocessContext(src_dataset=ds))
    mem_res = run_pipeline(cube, cfg, PreprocessContext())
    rec = next(r for r in inc.history if r.name == "band_reduction")
    assert rec.detail.get("mode") == "incremental"
    assert next(r for r in mem_res.history if r.name == "band_reduction").detail.get("mode") == \
        "in_memory"
    corr = np.corrcoef(inc.image.ravel(), mem_res.image.ravel())[0, 1]
    assert abs(corr) > 0.99


def test_probe_outputs_or_question():
    probes = sorted((REPO / "docs/probes").glob("*.txt"))
    questions = (REPO / "Phase_1/QUESTIONS.md").read_text()
    present = []
    for inst, pattern in (("TMC2", "data/raw/ch2/tmc2/*/data/**/*.xml"),
                          ("IIRS", "data/raw/ch2/iirs/*/data/**/*.xml")):
        if list(REPO.glob(pattern)):
            present.append(inst)
    if present:
        assert probes, f"{present} on disk but no docs/probes/*.txt"
    else:
        assert "Q-P1.15" in questions, "no probe possible: a non-blocking QUESTIONS entry is required"


@pytest.mark.data
def test_real_iirs_band_reduction():
    """Review RC10: when an IIRS product is on disk, its real cube goes through band reduction."""
    labels = sorted(REPO.glob("data/raw/ch2/iirs/*/data/**/*.xml"))
    if not labels:
        pytest.skip("no IIRS product under data/raw/ch2/iirs (download pending, G24)")
    from rasterio.windows import Window

    from lunar_reg.ingest.pds4 import open_product
    from lunar_reg.preprocess.hyperspectral import reduce_bands

    with open_product(labels[0]) as ds:
        assert ds.count > 1, "IIRS cube expected to have several bands"
        h, w = min(256, ds.height), min(256, ds.width)
        cube = ds.read(window=Window(0, 0, w, h)).astype(np.float32)
    plane, detail = reduce_bands(cube, method="pca", n_components=1)
    assert plane.shape == (h, w) and np.isfinite(plane).mean() > 0.5


PROBE_KEYS = {"path", "width", "height", "count", "dtype", "block_shapes", "compression",
              "nodata_declared", "crs_wkt", "res", "decimation", "border_values",
              "fill_candidate", "fill_candidate_source", "fill_fraction", "peak_rss_bytes"}


def test_probe_raster_synthetic(tmp_path):
    """G40: the raster probe finds an undeclared 0 fill on a decimated read."""
    import json
    import subprocess
    import sys

    import rasterio

    h, w = 3000, 5000
    arr = np.zeros((h, w), np.uint16)
    arr[300:2700, 500:4500] = np.random.default_rng(0).integers(100, 4000, (2400, 4000))
    tif = tmp_path / "big.tif"
    with rasterio.open(tif, "w", driver="GTiff", width=w, height=h, count=1,
                       dtype="uint16") as ds:
        ds.write(arr, 1)
    out = tmp_path / "probe.json"
    res = subprocess.run([sys.executable, str(REPO / "scripts/probe_raster.py"), str(tif),
                          "--out", str(out)], cwd=REPO, capture_output=True, text=True,
                         timeout=120)
    assert res.returncode == 0, res.stdout + res.stderr
    doc = json.loads(out.read_text())
    assert set(doc) >= PROBE_KEYS, PROBE_KEYS - set(doc)
    assert doc["nodata_declared"] is None and doc["fill_candidate"] == 0
    assert doc["decimation"] == 3 and doc["fill_candidate_source"] == "inferred"
    assert 0.3 < doc["fill_fraction"] < 0.5   # true fill share = 1 - 0.64 = 0.36


@pytest.mark.data
def test_real_derived_tmc2_probed():
    """G40: every derived TMC-2 raster on disk has a probe JSON, read with bounded memory."""
    import json

    tifs = sorted(REPO.glob("data/raw/ch2/tmc2/*_d_oth_*/data/**/*.tif")) + \
        sorted(REPO.glob("data/raw/ch2/tmc2/*_d_dtm_*/data/**/*.tif"))
    if not tifs:
        pytest.skip("no derived TMC-2 raster under data/raw/ch2/tmc2")
    for tif in tifs:
        probe = REPO / "docs/probes" / f"{tif.stem}_raster.json"
        assert probe.exists(), f"missing {probe.relative_to(REPO)}"
        doc = json.loads(probe.read_text())
        assert set(doc) >= PROBE_KEYS, PROBE_KEYS - set(doc)
        assert doc["width"] * doc["height"] > 0 and max(doc["width"], doc["height"]) / doc["decimation"] <= 2048
        assert doc["peak_rss_bytes"] < 2 * 2**30, "probe read too much of the raster (G40)"
    if any(json.loads((REPO / "docs/probes" / f"{t.stem}_raster.json").read_text())["nodata_declared"] is None
           for t in tifs):
        assert "fill" in (REPO / "Phase_1/QUESTIONS.md").read_text().lower()
