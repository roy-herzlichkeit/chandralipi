"""P1.16 — site runner (Phase_1/LLD/site_runner.md). Protected (G05)."""

from __future__ import annotations

import json

import numpy as np
import pytest
from _h1 import REPO, TAGS_2023, illumination


def _pair(seed=0):
    from lunar_reg.pairs import PriorSource, WindowPair

    src, ref, H, _ = illumination(seed=seed, shape=(256, 256))
    ones = np.ones_like(src, bool)
    return WindowPair(source=src, reference=ref, source_valid=ones, reference_valid=ones.copy(),
                      prior=H, prior_source=PriorSource.LABEL_CORNERS, gsd_m=4.0,
                      source_window=(0, 0, 1024, 1024), reference_window=(0, 0, 256, 256),
                      source_native_gsd_m=0.25, reference_native_gsd_m=1.0,
                      source_to_native=np.diag([16.0, 16.0, 1.0]),
                      reference_to_native=np.diag([4.0, 4.0, 1.0]), shift_m=(0.0, 0.0),
                      source_id="src", reference_id="ref", provenance={"src_gsd": "documented"})


@pytest.fixture
def patched(monkeypatch, tmp_path):
    from lunar_reg.ingest.catalog import CatalogEntry, InstrumentStatus, ProductCatalog
    from lunar_reg.ingest.lro import GeoReference
    from lunar_reg.ingest.manifest import ScanDiagnostics
    from lunar_reg.pairs import PrepOutcome, PrepStatus
    from lunar_reg.provenance import ValueSource
    from lunar_reg.sites import runner

    label = tmp_path / "ch2_ohr_nrp_20240425T1406019344_d_img_d18.xml"
    label.write_text("<x/>")
    entry = CatalogEntry(instrument="OHRC", product_id="ch2_ohr_nrp_20240425T1406019344_d_img_d18",
                         label_path=label, image_path=None, level="raw", product_type="data",
                         geometry_grid_path=None)
    status = {k: InstrumentStatus.ABSENT for k in
              ("OHRC", "TMC2", "IIRS", "LRO_NAC", "LRO_NAC_DTM", "SELENE_TC")}
    status["OHRC"] = status["LRO_NAC"] = InstrumentStatus.PRESENT
    cat = ProductCatalog(entries=[entry], status=status, diagnostics=ScanDiagnostics())
    monkeypatch.setattr(runner, "build_catalog", lambda *a, **k: cat)
    geo = GeoReference("+proj=stere +lat_0=-90 +lat_ts=-69.3 +lon_0=32.3 +R=1737400 +units=m",
                       0.0, 0.0, 1.0, 1.0, 1000, 1000, ValueSource.INFERRED)
    monkeypatch.setattr(runner, "georeference_from_label", lambda *a, **k: geo)
    monkeypatch.setattr(runner, "prepare_window_pair",
                        lambda *a, **k: PrepOutcome(PrepStatus.OK, _pair(), ""))
    calls = {"register": 0}
    real = runner.register_pair

    def counting(*a, **k):
        calls["register"] += 1
        return real(*a, **k)

    monkeypatch.setattr(runner, "register_pair", counting)
    return runner, tmp_path, calls


def test_run_site_ok(patched):
    runner, tmp, calls = patched
    cfg = runner.SiteConfig(matchers=("sift",), coarse=False, prior_shift_m=None,
                            results_root=tmp / "store", out_dir=tmp / "out",
                            save_registered=False, reference_sun_json=None)
    rep = runner.run_site(cfg)
    assert rep.any_ok and calls["register"] == 1
    assert list((tmp / "store" / "pairs").glob("*.npz"))
    rr = json.loads((tmp / "out" / "run_record.json").read_text())
    assert rr["outcome_counts"]
    text = rep.report()
    assert "TMC2" in text and "ABSENT" in text.upper()


def test_coarse_failure_note_and_prior(patched, monkeypatch):
    runner, tmp, _ = patched
    from lunar_reg.pipeline import RunOutcome, RunStatus

    real = runner.register_pair

    def coarse_fails(src, ref, pair_id, config=None, **kw):
        if config is not None and not config.use_ecc and config.n_bootstrap == 0:
            return RunOutcome(pair_id, RunStatus.TOO_FEW_MATCHES, None, "x", {})
        return real(src, ref, pair_id, config, **kw)

    monkeypatch.setattr(runner, "register_pair", coarse_fails)
    cfg = runner.SiteConfig(matchers=("sift",), coarse=True, prior_shift_m=(556.0, -2888.0),
                            results_root=tmp / "store", out_dir=tmp / "out",
                            save_registered=False, reference_sun_json=None)
    rep = runner.run_site(cfg)
    run = rep.runs[0]
    assert run.coarse_note.startswith("coarse pass failed (too_few_matches)")
    assert run.search_prior.startswith("prior shift 556")


def test_dry_run_no_matching(patched):
    runner, tmp, calls = patched
    cfg = runner.SiteConfig(matchers=("sift",), dry_run=True, results_root=tmp / "store",
                            out_dir=tmp / "out", reference_sun_json=None)
    rep = runner.run_site(cfg)
    assert calls["register"] == 0 and not rep.any_ok
    assert list((tmp / "out" / "preview").glob("*_src.png"))


def _stored(root, tag, matcher, n_inl, u, dx):
    from lunar_reg.results import PairResult, save_pair

    pts = np.zeros((max(n_inl, 1), 2))
    H = np.array([[1.0, 0, dx], [0, 1.0, 0], [0, 0, 1.0]])
    r = PairResult(f"CH2_OHRC_RAW_{tag}-LRO_NAC_ORTHO_{matcher}", tag, "nac", "CH2_OHRC_RAW",
                   "LRO_NAC_ORTHO", matcher, pts, pts, np.ones(len(pts), bool), H,
                   uniformity={"score": u}, source_image=np.zeros((100, 100), np.uint8),
                   pre_ecc_transform=H, extra={"gsd_m": 4.0})
    save_pair(r, root, overwrite=True)
    return r


def test_exp1_gate(tmp_path):
    from lunar_reg.results import load_all_pairs, write_index
    from lunar_reg.sites.runner import compute_exp1_gate

    root = tmp_path / "store"
    for m, dx in (("sift", 0.0), ("akaze", 0.4)):
        _stored(root, TAGS_2023[0], m, 30, 0.8, dx)
    _stored(root, TAGS_2023[1], "sift", 5, 0.2, 0.0)
    write_index(load_all_pairs(root)[0], root)
    gate = compute_exp1_gate(root, TAGS_2023, None, "rr.json")
    assert gate["decision"] == "BUILD_1B" and gate["n_strips_passing"] == 1
    statuses = {s["tag"]: s for s in gate["strips"]}
    assert statuses[TAGS_2023[0]]["passes_targets"] is True
    assert statuses[TAGS_2023[2]]["status"] == "no_result"
    for tag in TAGS_2023[1:]:
        for m, dx in (("sift", 0.0), ("akaze", 0.2)):
            _stored(root, tag, m, 40, 0.9, dx)
    write_index(load_all_pairs(root)[0], root)
    assert compute_exp1_gate(root, TAGS_2023, None, "rr.json")["decision"] == "SKIP_1B"


def test_run_vikram_is_thin():
    text = (REPO / "scripts/run_vikram.py").read_text()
    assert "run_site" in text and "SiteConfig" in text
    assert "def export_stored" in text
    assert "--dry-run" in text and "--preprocess" in text and "--overwrite" in text
