"""Site runner (Phase_1/LLD/site_runner.md §5): catalog -> prep -> coarse -> prior -> register."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
ANCHOR = "20240425T1406019344"
TAGS_2023 = ("20230823T1450475804", "20230823T1647285085", "20230823T1647285315")
PROJ = "+proj=stere +lat_0=-90 +lat_ts=-69.3 +lon_0=32.3 +R=1737400 +units=m"


def _window_pair(seed: int = 0):
    """A synthetic WindowPair from eval.scenes.illumination_pair (exact truth as the prior)."""
    from lunar_reg.eval.scenes import illumination_pair
    from lunar_reg.pairs import PriorSource, WindowPair

    src, ref, H, _ = illumination_pair(
        shape=(256, 256), seed=seed, source_sun=(300, 30), reference_sun=(300, 30)
    )
    ones = np.ones_like(src, bool)
    return WindowPair(
        source=src, reference=ref, source_valid=ones, reference_valid=ones.copy(), prior=H,
        prior_source=PriorSource.LABEL_CORNERS, gsd_m=4.0, source_window=(0, 0, 1024, 1024),
        reference_window=(10, 20, 256, 256), source_native_gsd_m=0.25,
        reference_native_gsd_m=1.0, source_to_native=np.diag([16.0, 16.0, 1.0]),
        reference_to_native=np.diag([4.0, 4.0, 1.0]), shift_m=(0.0, 0.0), source_id="src",
        reference_id="NAC_REF", provenance={"src_gsd": "documented"},
    )  # fmt: skip


@pytest.fixture
def env(monkeypatch, tmp_path):
    """Patch catalog, georeference and pair preparation; count register_pair calls."""
    from lunar_reg.ingest.catalog import CatalogEntry, InstrumentStatus, ProductCatalog
    from lunar_reg.ingest.lro import GeoReference
    from lunar_reg.ingest.manifest import ScanDiagnostics
    from lunar_reg.pairs import PrepOutcome, PrepStatus
    from lunar_reg.provenance import ValueSource
    from lunar_reg.sites import runner

    def entry(instrument: str, pid: str, level: str = "raw"):
        label = tmp_path / f"{pid}.xml"
        label.write_text("<x/>")
        return CatalogEntry(instrument=instrument, product_id=pid, label_path=label,
                            image_path=None, level=level, product_type="data",
                            geometry_grid_path=None)  # fmt: skip

    status = {
        k: InstrumentStatus.ABSENT
        for k in ("OHRC", "TMC2", "IIRS", "LRO_NAC", "LRO_NAC_DTM", "SELENE_TC")
    }
    status["OHRC"] = status["LRO_NAC"] = InstrumentStatus.PRESENT
    entries = [entry("OHRC", f"ch2_ohr_nrp_{ANCHOR}_d_img_d18")]
    cat = ProductCatalog(entries=entries, status=status, diagnostics=ScanDiagnostics())
    monkeypatch.setattr(runner, "build_catalog", lambda *a, **k: cat)
    geo = GeoReference(PROJ, 1000.0, 2000.0, 1.0, 1.0, 5000, 5000, ValueSource.INFERRED)
    monkeypatch.setattr(runner, "georeference_from_label", lambda *a, **k: geo)
    preps: list[dict] = []
    state = {"prep": lambda: PrepOutcome(PrepStatus.OK, _window_pair(), "")}

    def prep(*a, **k):
        preps.append(k)
        return state["prep"]()

    monkeypatch.setattr(runner, "prepare_window_pair", prep)
    calls: list[dict] = []
    real = runner.register_pair

    def counting(*a, **k):
        calls.append({"args": a, **k})
        return real(*a, **k)

    monkeypatch.setattr(runner, "register_pair", counting)

    def cfg(**kw):
        base = dict(
            matchers=("sift",),
            coarse=False,
            prior_shift_m=None,
            results_root=tmp_path / "store",
            out_dir=tmp_path / "out",
            save_registered=False,
            reference_sun_json=None,
            label_convention_json=None,
        )
        base.update(kw)
        return runner.SiteConfig(**base)

    return {"runner": runner, "tmp": tmp_path, "calls": calls, "preps": preps, "cfg": cfg,
            "cat": cat, "entry": entry, "state": state, "geo": geo}  # fmt: skip


def test_ok_path_saves_one_npz_per_matcher_and_run_record(env):
    runner, tmp = env["runner"], env["tmp"]
    rep = runner.run_site(env["cfg"](matchers=("sift", "akaze")))
    assert rep.any_ok and len(env["calls"]) == 2
    stored = sorted(p.stem for p in (tmp / "store" / "pairs").glob("*.npz"))
    assert stored == [
        f"CH2_OHRC_RAW_{ANCHOR}-LRO_NAC_ORTHO_akaze",
        f"CH2_OHRC_RAW_{ANCHOR}-LRO_NAC_ORTHO_sift",
    ]
    rr = json.loads((tmp / "out" / "run_record.json").read_text())
    counts = rr["outcome_counts"]
    assert counts["ok"] == 2 and counts["prep_ok"] == 1
    assert counts["instrument_OHRC_present"] == 1 and counts["instrument_TMC2_absent"] == 1
    assert any(a.endswith("LRO_NAC_ORTHO_sift.npz") for a in rr["artefacts"])

    from lunar_reg.results import load_pair

    r = load_pair(stored[1], tmp / "store")
    for key in (
        "ref_crop_c0",
        "src_win_l0",
        "gsd_m",
        "prior_source",
        "site",
        "level",
        "window_m",
        "margin_m",
        "coarse_pass",
        "search_prior",
        "label_offset_m",
    ):
        assert key in r.extra, key
    assert r.extra["search_prior"] == "label corners"
    assert r.extra["coarse_pass"].startswith("not run")
    assert r.extra["level"] == "raw" and r.source_sensor == "CH2_OHRC_RAW"
    assert r.extra["min_inliers"] == 8
    products = json.loads((tmp / "out" / "products.json").read_text())
    assert products[0]["prep"] == "ok" and len(products[0]["outcomes"]) == 2


def test_registered_geotiff_origin(env, monkeypatch):
    import lunar_reg.align.warp as warp

    written = []

    def fake(src, matrix, shape, path, **kw):
        written.append(kw)
        return {"path": str(path), "shape": shape, "valid_fraction": 1.0}

    monkeypatch.setattr(warp, "save_registered_geotiff", fake)
    rep = env["runner"].run_site(env["cfg"](save_registered=True))
    assert rep.any_ok and len(written) == 1
    # reference_window = (r0=10, c0=20); geo origin (1000, 2000), 1 m pixels
    assert written[0]["origin_xy"] == (1000.0 + 20, 2000.0 - 10)
    assert written[0]["pixel_size"] == 4.0 and written[0]["crs"] == PROJ
    assert rep.runs[0].outcomes[0].result.extra["registered_geotiff"].endswith("_sift.tif")


def test_existing_result_keeps_its_geotiff(env, monkeypatch):
    """Not saved (exists, no overwrite) -> the stored result's GeoTIFF is not rewritten."""
    import lunar_reg.align.warp as warp

    written = []

    def fake(src, matrix, shape, path, **kw):
        written.append(str(path))
        return {"path": str(path), "shape": shape, "valid_fraction": 1.0}

    monkeypatch.setattr(warp, "save_registered_geotiff", fake)
    runner = env["runner"]
    assert runner.run_site(env["cfg"](save_registered=True)).saved
    rep = runner.run_site(env["cfg"](save_registered=True))
    assert rep.not_saved and not rep.saved and len(written) == 1
    rr = json.loads((env["tmp"] / "out" / "run_record.json").read_text())
    assert not any(a.endswith(".tif") for a in rr["artefacts"])
    # with overwrite the result and its GeoTIFF are replaced together
    rep = runner.run_site(env["cfg"](save_registered=True, overwrite=True))
    assert rep.saved and len(written) == 2


def test_geotiff_write_failure_in_report(env, monkeypatch):
    import lunar_reg.align.warp as warp
    from lunar_reg.results import load_pair

    def broken(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(warp, "save_registered_geotiff", broken)
    rep = env["runner"].run_site(env["cfg"](save_registered=True))
    assert rep.saved and len(rep.geotiff_failures) == 1
    text = rep.report()
    assert "registered GeoTIFF: 1 write(s) FAILED" in text and "disk full" in text
    stored = load_pair(rep.saved[0], env["tmp"] / "store")
    assert "disk full" in stored.extra["registered_geotiff_error"]
    rr = json.loads((env["tmp"] / "out" / "run_record.json").read_text())
    assert rr["outcome_counts"]["geotiff_write_failed"] == 1


def test_coarse_failure_note_and_prior_shift(env, monkeypatch):
    from lunar_reg.pipeline import RunOutcome, RunStatus

    runner = env["runner"]
    real = runner.register_pair

    def coarse_fails(src, ref, pair_id, config=None, **kw):
        if config is not None and not config.use_ecc and config.n_bootstrap == 0:
            return RunOutcome(pair_id, RunStatus.TOO_FEW_MATCHES, None, "x", {})
        return real(src, ref, pair_id, config, **kw)

    monkeypatch.setattr(runner, "register_pair", coarse_fails)
    rep = runner.run_site(env["cfg"](coarse=True, prior_shift_m=(556.0, -2888.0)))
    run = rep.runs[0]
    # A112: the note names the failure only, not which prior was used
    assert run.coarse_note == "coarse pass failed (too_few_matches)"
    assert run.search_prior == "prior shift 556,-2888 m (E,S)"
    coarse_prep, fine_prep = env["preps"]
    assert coarse_prep["gsd_m"] == 8.0 and coarse_prep["margin_m"] == 4000.0
    assert fine_prep["shift_m"] == (556.0, -2888.0) and fine_prep["gsd_m"] == 4.0
    assert (
        "coarse_failed"
        in json.loads((env["tmp"] / "out" / "run_record.json").read_text())["outcome_counts"]
    )


def test_coarse_success_moves_the_fine_crop(env, monkeypatch):
    from types import SimpleNamespace

    from lunar_reg.pipeline import RunOutcome, RunStatus

    runner = env["runner"]
    real = runner.register_pair
    pair = _window_pair()
    # found = prior followed by +2 working px in x, -1 in y -> 4x native px at 1 m
    found = np.array([[1.0, 0, 2.0], [0, 1.0, -1.0], [0, 0, 1.0]]) @ pair.prior

    def coarse_ok(src, ref, pair_id, config=None, **kw):
        if config is not None and not config.use_ecc and config.n_bootstrap == 0:
            return RunOutcome(
                pair_id, RunStatus.OK, SimpleNamespace(transform=found, n_inliers=77), ""
            )
        return real(src, ref, pair_id, config, **kw)

    monkeypatch.setattr(runner, "register_pair", coarse_ok)
    rep = runner.run_site(env["cfg"](coarse=True, prior_shift_m=(556.0, -2888.0)))
    run = rep.runs[0]
    assert run.search_prior == "coarse pass"
    assert run.coarse_note == "8 m/px lightglue, 77 inliers, shift +8.000,-4.000 m (E,S)"
    assert env["preps"][1]["shift_m"] == pytest.approx((8.0, -4.0))


def test_prior_shift_only_for_listed_instruments(env, monkeypatch):
    """G38: a TMC2 product never receives the OHRC prior shift."""
    from lunar_reg.ingest.catalog import InstrumentStatus

    cat = env["cat"]
    cat.entries[:] = [
        env["entry"]("TMC2", "ch2_tmc_ncn_20230521T0857294318_d_img_d32", "calibrated")
    ]
    cat.status["OHRC"] = InstrumentStatus.ABSENT
    cat.status["TMC2"] = InstrumentStatus.PRESENT
    rep = env["runner"].run_site(
        env["cfg"](prior_shift_m=(556.0, -2888.0), instruments=("OHRC", "TMC2"))
    )
    assert env["runner"].SiteConfig().prior_shift_instruments == ("OHRC",)
    assert rep.runs[0].search_prior == "label corners"
    assert env["preps"][0]["shift_m"] == (0.0, 0.0)
    pair_id = rep.runs[0].outcomes[0].pair_id
    assert pair_id == "CH2_TMC2_CALIBRATED_20230521T0857294318-LRO_NAC_ORTHO_sift"
    assert "OHRC: ABSENT" in rep.report()


def test_dry_run_makes_no_register_call_and_writes_previews(env):
    rep = env["runner"].run_site(env["cfg"](dry_run=True, coarse=True))
    assert env["calls"] == [] and not rep.any_ok
    assert len(env["preps"]) == 1  # fine prep only, no coarse pass
    previews = sorted(p.name for p in (env["tmp"] / "out" / "preview").glob("*.png"))
    assert previews == [f"CH2_OHRC_RAW_{ANCHOR}_ref.png", f"CH2_OHRC_RAW_{ANCHOR}_src.png"]
    assert not (env["tmp"] / "store").exists()
    assert "dry run" in rep.report()


def test_prep_failure_is_recorded_not_matched(env):
    from lunar_reg.pairs import PrepOutcome, PrepStatus

    env["state"]["prep"] = lambda: PrepOutcome(PrepStatus.OUTSIDE_REFERENCE, None, "crop off")
    rep = env["runner"].run_site(env["cfg"]())
    assert env["calls"] == [] and not rep.any_ok
    assert rep.runs[0].prep is PrepStatus.OUTSIDE_REFERENCE
    text = rep.report()
    assert "outside_reference: 1" in text and "crop off" in text
    rr = json.loads((env["tmp"] / "out" / "run_record.json").read_text())
    assert rr["outcome_counts"]["prep_outside_reference"] == 1


def test_absent_instruments_in_report(env):
    rep = env["runner"].run_site(env["cfg"]())
    text = rep.report()
    assert "TMC2: ABSENT" in text and "IIRS: ABSENT" in text
    assert "OHRC: present" in text


def test_failures_persisted_and_any_ok_false(env, monkeypatch):
    from lunar_reg.pipeline import RunOutcome, RunStatus
    from lunar_reg.results import load_failures

    runner = env["runner"]
    monkeypatch.setattr(
        runner, "register_pair",
        lambda src, ref, pair_id, config=None, **kw: RunOutcome(
            pair_id, RunStatus.TOO_FEW_INLIERS, None, "3 < 8",
            {"matcher": config.matcher, "stage": "estimate", **config.extra},
        ),
    )  # fmt: skip
    rep = runner.run_site(env["cfg"](matchers=("sift", "akaze")))
    assert not rep.any_ok
    frame = load_failures(env["tmp"] / "store")
    assert len(frame) == 2 and set(frame["status"]) == {"too_few_inliers"}


def test_sun_passed_only_when_frames_match(env, monkeypatch):
    from lunar_reg.ingest.sun import SunGeometry
    from lunar_reg.provenance import ValueSource
    from lunar_reg.results import load_pair

    runner, tmp = env["runner"], env["tmp"]
    monkeypatch.setattr(
        runner, "sun_from_label",
        lambda product: SunGeometry(300.0, 12.0, ValueSource.DOCUMENTED, ValueSource.DOCUMENTED,
                                    "label_unverified"),
    )  # fmt: skip
    ref = tmp / "reference_sun.json"
    sun = SunGeometry(120.0, 18.0, ValueSource.COMPUTED, ValueSource.COMPUTED, "north_clockwise")
    ref.write_text(json.dumps({"sun": sun.as_dict()}))
    conv = tmp / "label_convention.json"
    conv.write_text(json.dumps({"convention": "mirror"}))

    store = tmp / "store"
    # no convention: frames differ -> no sun arguments, both suns still in the stored record
    rep = runner.run_site(env["cfg"](reference_sun_json=ref))
    call = env["calls"][-1]
    assert call["source_sun"] is None and call["reference_sun"] is None
    extra = load_pair(rep.saved[0], store).extra
    assert extra["source_sun_azimuth"] == 300.0 and extra["source_sun_elevation"] == 12.0
    assert extra["reference_sun_azimuth"] == 120.0 and extra["reference_sun_elevation"] == 18.0
    assert extra["reference_sun_source"] == "computed"
    assert extra["source_sun_azimuth_source"] == "documented"
    assert extra["source_sun_elevation_source"] == "documented"
    assert extra["source_sun_frame"] == "label_unverified"
    assert extra["reference_sun_frame"] == "north_clockwise"

    # with the convention: 360 - 300 = 60, north_clockwise -> both passed
    rep = runner.run_site(env["cfg"](reference_sun_json=ref, label_convention_json=conv,
                                     overwrite=True))  # fmt: skip
    call = env["calls"][-1]
    assert call["source_sun"] == (60.0, 12.0) and call["reference_sun"] == (120.0, 18.0)
    extra = load_pair(rep.saved[0], store).extra
    assert extra["source_sun_azimuth"] == 60.0 and extra["reference_sun_azimuth"] == 120.0
    # the convention computes the azimuth; the elevation stays as documented
    assert extra["source_sun_azimuth_source"] == "computed"
    assert extra["source_sun_elevation_source"] == "documented"
    assert extra["source_sun_frame"] == "north_clockwise"


def test_variant_pair_id(env):
    rep = env["runner"].run_site(env["cfg"](model="affine", preprocess="clahe_shadow"))
    pid = rep.runs[0].outcomes[0].pair_id
    assert pid == f"CH2_OHRC_RAW_{ANCHOR}-LRO_NAC_ORTHO_sift_affine_pp-clahe_shadow"


def test_existing_result_not_overwritten(env):
    runner = env["runner"]
    assert runner.run_site(env["cfg"]()).saved
    rep = runner.run_site(env["cfg"]())
    assert rep.not_saved == [f"CH2_OHRC_RAW_{ANCHOR}-LRO_NAC_ORTHO_sift"] and not rep.saved
    assert "NOT saved" in rep.report()


# ---------------------------------------------------------------------------
# run_vikram exit semantics (A111) and flags
# ---------------------------------------------------------------------------


def _run_vikram():
    spec = importlib.util.spec_from_file_location("_rv_site", REPO / "scripts" / "run_vikram.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("any_ok, code", [(True, 0), (False, 1)])
def test_run_vikram_exit_follows_any_ok(monkeypatch, capsys, any_ok, code):
    from types import SimpleNamespace

    from lunar_reg.sites import runner

    seen = {}

    def fake(cfg):
        seen["cfg"] = cfg
        return SimpleNamespace(any_ok=any_ok, report=lambda: "REPORT TEXT")

    monkeypatch.setattr(runner, "run_site", fake)
    rv = _run_vikram()
    assert rv.main(["--dry-run", "--prior-shift", "", "--instruments", "OHRC",
                    "--levels", "raw", "--reference-sun-json", ""]) == code  # fmt: skip
    assert "REPORT TEXT" in capsys.readouterr().out
    cfg = seen["cfg"]
    assert cfg.dry_run and not cfg.coarse  # A110: --dry-run never runs the coarse pass
    assert cfg.prior_shift_m is None and cfg.reference_sun_json is None
    assert cfg.instruments == ("OHRC",) and cfg.levels == ("raw",)
    assert cfg.min_inliers == 5  # demo default kept (TBD 1.8)


def test_run_vikram_defaults(monkeypatch):
    from types import SimpleNamespace

    from lunar_reg.sites import runner

    seen = {}
    monkeypatch.setattr(
        runner, "run_site",
        lambda cfg: seen.setdefault("cfg", cfg) and SimpleNamespace(any_ok=True, report=str),
    )  # fmt: skip
    _run_vikram().main(["--nac", "2", "--matchers", "sift,akaze"])
    cfg = seen["cfg"]
    assert cfg.coarse and cfg.prior_shift_m == (556.0, -2888.0)
    assert cfg.reference_sensor == "LRO_NAC_ORTHO_E2"
    assert cfg.reference_label.name == "NAC_DTM_VIKRAMSITE1_M1443025251_100CM.xml"
    assert cfg.matchers == ("sift", "akaze") and cfg.gsd_m == 4.0
    assert cfg.results_root == Path("data/processed/results")


# ---------------------------------------------------------------------------
# compute_exp1_gate (LLD §3, C20)
# ---------------------------------------------------------------------------


def _stored(root, tag, matcher, n_inl, u, dx, variant="", sensor="CH2_OHRC_RAW"):
    from lunar_reg.results import PairResult, save_pair

    pts = np.zeros((max(n_inl, 1), 2))
    H = np.array([[1.0, 0, dx], [0, 1.0, 0], [0, 0, 1.0]])
    source_id = tag if sensor == "CH2_OHRC_RAW" else f"{tag}_{sensor}"
    r = PairResult(
        f"{sensor}_{tag}-LRO_NAC_ORTHO_{matcher}{variant}", source_id, "nac", sensor,
        "LRO_NAC_ORTHO", matcher, pts, pts, np.ones(len(pts), bool), H,
        uniformity={"score": u}, source_image=np.zeros((100, 100), np.uint8),
        pre_ecc_transform=H, extra={"gsd_m": 4.0},
    )  # fmt: skip
    save_pair(r, root, overwrite=True)


def _reindex(root):
    from lunar_reg.results import load_all_pairs, write_index

    write_index(load_all_pairs(root)[0], root)


C20_KEYS = {"schema", "decision", "rule", "strips", "n_strips_passing", "reference_sun",
            "run_record", "created_utc"}  # fmt: skip
C20_STRIP_KEYS = {"tag", "best_matcher", "status", "n_inliers", "u_score", "agreement_px",
                  "passes_targets"}  # fmt: skip


def test_exp1_gate_build_then_skip(tmp_path):
    from lunar_reg.sites.runner import EXP1_RULE, compute_exp1_gate

    root = tmp_path / "store"
    _stored(root, TAGS_2023[0], "sift", 30, 0.8, 0.0)
    _stored(root, TAGS_2023[0], "akaze", 25, 0.75, 0.4)
    _stored(root, TAGS_2023[1], "sift", 5, 0.2, 0.0)
    _reindex(root)
    sun = {"azimuth_deg": 120.0, "azimuth_frame": "north_clockwise"}
    gate = compute_exp1_gate(root, TAGS_2023, sun, "data/processed/vikram/exp1/run_record.json")
    assert set(gate) == C20_KEYS and gate["schema"] == 1 and gate["rule"] == EXP1_RULE
    assert gate["decision"] == "BUILD_1B" and gate["n_strips_passing"] == 1
    assert gate["reference_sun"] == sun
    strips = {s["tag"]: s for s in gate["strips"]}
    assert all(set(s) == C20_STRIP_KEYS for s in gate["strips"])
    first = strips[TAGS_2023[0]]
    assert first["passes_targets"] is True and first["best_matcher"] == "sift"
    assert first["n_inliers"] == 30 and first["agreement_px"] == pytest.approx(0.4)
    assert strips[TAGS_2023[1]]["passes_targets"] is False  # 5 inliers, one matcher
    assert strips[TAGS_2023[2]]["status"] == "no_result"
    json.dumps(gate, allow_nan=False)  # C20 is strict JSON

    for tag in TAGS_2023[1:]:
        _stored(root, tag, "sift", 40, 0.9, 0.0)
        _stored(root, tag, "akaze", 40, 0.9, 0.2)
    _reindex(root)
    assert compute_exp1_gate(root, TAGS_2023, None, "rr.json")["decision"] == "SKIP_1B"


def test_exp1_gate_variants_do_not_crash_and_disagreement_fails(tmp_path):
    from lunar_reg.sites.runner import compute_exp1_gate

    root = tmp_path / "store"
    tag = TAGS_2023[0]
    _stored(root, tag, "sift", 50, 0.9, 0.0)
    _stored(root, tag, "akaze", 45, 0.9, 3.0)  # 3 px apart: agreement fails
    _stored(root, tag, "sift", 60, 0.5, 0.0, variant="_pp-clahe_shadow")
    _reindex(root)
    gate = compute_exp1_gate(root, (tag,), None, "rr.json")
    strip = gate["strips"][0]
    # best among u >= 0.7 is the plain sift result; agreement uses its variant group only
    assert strip["status"] == "ok" and strip["best_matcher"] == "sift"
    assert strip["n_inliers"] == 50 and strip["agreement_px"] == pytest.approx(3.0)
    assert strip["passes_targets"] is False and gate["decision"] == "BUILD_1B"


def test_exp1_gate_empty_store(tmp_path):
    from lunar_reg.sites.runner import compute_exp1_gate

    gate = compute_exp1_gate(tmp_path / "none", TAGS_2023, None, "rr.json")
    assert gate["decision"] == "BUILD_1B" and gate["n_strips_passing"] == 0
    assert {s["status"] for s in gate["strips"]} == {"no_result"}


def test_exp1_gate_any_comparable_group_passes(tmp_path):
    """exp-1a (raw) and exp-1b (calibrated) share the live store: each group is tested."""
    from lunar_reg.sites.runner import compute_exp1_gate

    root = tmp_path / "store"
    tag = TAGS_2023[0]
    _stored(root, tag, "sift", 50, 0.9, 0.0)
    _stored(root, tag, "akaze", 45, 0.9, 0.2)  # raw group: two matchers agree
    _stored(root, tag, "sift", 60, 0.9, 0.0, sensor="CH2_OHRC_CAL")  # one matcher only
    _reindex(root)
    strip = compute_exp1_gate(root, (tag,), None, "rr.json")["strips"][0]
    assert strip["passes_targets"] is True and strip["status"] == "ok"
    assert strip["best_matcher"] == "sift" and strip["n_inliers"] == 50
    assert strip["agreement_px"] == pytest.approx(0.2)

    # no group passes -> the row reports the group of the strip-wide best (calibrated sift)
    _stored(root, tag, "akaze", 45, 0.9, 3.0)
    _reindex(root)
    strip = compute_exp1_gate(root, (tag,), None, "rr.json")["strips"][0]
    assert strip["passes_targets"] is False and strip["n_inliers"] == 60
    assert strip["agreement_px"] is None  # one matcher: no agreement value


def test_exp1_gate_unloadable_records_are_classified(tmp_path, caplog):
    import logging

    from lunar_reg.sites.runner import compute_exp1_gate

    root = tmp_path / "store"
    tag, other = TAGS_2023[0], TAGS_2023[1]
    for t in (tag, other):
        _stored(root, t, "sift", 40, 0.9, 0.0)
        _stored(root, t, "akaze", 40, 0.9, 0.2)
    _reindex(root)
    for path in (root / "pairs").glob(f"*{tag}*.npz"):
        path.write_bytes(b"junk")
    (root / "pairs" / f"CH2_OHRC_RAW_{other}-LRO_NAC_ORTHO_akaze.npz").write_bytes(b"junk")
    with caplog.at_level(logging.INFO, logger="lunar_reg.sites.runner"):
        gate = compute_exp1_gate(root, TAGS_2023, None, "rr.json")
    strips = {s["tag"]: s for s in gate["strips"]}
    assert strips[tag]["status"] == "load_failed" and not strips[tag]["passes_targets"]
    assert strips[other]["status"] == "ok; 1 stored record(s) not loaded"
    assert strips[TAGS_2023[2]]["status"] == "no_result"
    gate_lines = [r.getMessage() for r in caplog.records if "exp-1 gate" in r.getMessage()]
    assert len(gate_lines) == 1 and "3 stored record(s) not loaded" in gate_lines[0]
