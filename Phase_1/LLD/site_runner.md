# LLD — site runner (P1.16)

Closes: A110 (pr-13), A111 (pr-14), A112 (pr-15), A113 (pr-21). TBD 1.3/1.8 (the runner that exercises the experiments). Moves `scripts/run_vikram.py`'s matching logic into `src/lunar_reg/sites/runner.py`; the script stays as the CLI (and keeps `export_stored` from P0.11).

## 1. Types (`sites/runner.py`)
```python
@dataclass
class SiteConfig:
    site: str = "vikram"
    reference_label: Path = Path("data/raw/reference/lro_nac_vikram/NAC_DTM_VIKRAMSITE1_M1442997156_100CM.xml")
    reference_sensor: str = "LRO_NAC_ORTHO"
    raw_root: Path = Path("data/raw")
    instruments: tuple[str, ...] = ("OHRC", "TMC2", "IIRS")
    only: str = ""                           # substring filter on product id
    levels: tuple[str, ...] = ("raw", "calibrated")
    gsd_m: float = 4.0
    window_m: float = 3000.0
    margin_m: float = 1000.0
    matchers: tuple[str, ...] = ("sift", "akaze", "asift", "lightglue")
    model: str = "homography"
    min_inliers: int = 8
    ransac_threshold_px: float = 3.0
    preprocess: str = "none"
    ecc_prefilter: str = "none"
    coarse: bool = True
    coarse_gsd_m: float = 8.0
    coarse_margin_m: float = 4000.0
    coarse_matcher: str = "lightglue"
    prior_shift_m: tuple[float, float] | None = (556.0, -2888.0)   # MEASURED on the 2024 strip (run_vikram DEFAULT_PRIOR_SHIFT)
    band_reduction: str = "pca"              # IIRS
    results_root: Path = Path("data/processed/results")
    out_dir: Path = Path("data/processed/vikram/runs/latest")
    save_registered: bool = True
    overwrite: bool = False
    dry_run: bool = False
    reference_sun_json: Path | None = Path("data/processed/vikram/reference_sun/reference_sun.json")

@dataclass
class ProductRun:
    product_id: str; instrument: str; level: str
    prep: PrepStatus; prep_detail: str
    coarse_note: str; search_prior: str
    outcomes: list[RunOutcome]

@dataclass
class SiteReport:
    catalog: ProductCatalog
    runs: list[ProductRun]
    batch: BatchReport
    run_record_path: Path | None
    def report(self) -> str          # instrument statuses, prep outcomes (counts + sample), batch.report()
    @property
    def any_ok(self) -> bool

def run_site(cfg: SiteConfig) -> SiteReport
def compute_exp1_gate(results_root, tags: tuple[str, ...], reference_sun: dict | None,
                      run_record: str, threshold_px: float = 1.0) -> dict   # C20 document
```
Pair id: `f"{SENSOR}_{tag}-{reference_sensor}_{matcher}{variant}"` where `SENSOR` = `CH2_OHRC_RAW` / `CH2_OHRC_CAL` / `CH2_TMC2_<LEVEL>` / `CH2_IIRS_<LEVEL>` (LEVEL upper-cased), `tag` = the `YYYYMMDDTHHMMSSffff` token, `variant` = `""` for homography + preset none, else `_<model>` and/or `_pp-<preset>` in that order.

Test seam: `sites/runner.py` imports `build_catalog`, `georeference_from_label`, `prepare_window_pair`, `register_pair` and `sun_from_label` at module level (`from … import name`) and calls them through those module attributes; the harness monkeypatches them.

## 2. `run_site` flow
1. `catalog = build_catalog(cfg.raw_root)`; print nothing (the caller prints `report()`); instruments not PRESENT are counted in the report (G24) and skipped.
2. `reference_geo = georeference_from_label(cfg.reference_label)`; failure → raise `LabelGeoreferenceError` (programmer/data-setup error, not a per-pair outcome).
3. Reference sun: `json.load(cfg.reference_sun_json)["sun"]` when the file exists, else None.
4. For each PRESENT product of each requested instrument whose level is in `cfg.levels` and id contains `cfg.only`:
   a. **Coarse** (when `cfg.coarse` and not `cfg.dry_run`): `prepare_window_pair(..., gsd_m=cfg.coarse_gsd_m, margin_m=cfg.coarse_margin_m)`; `register_pair(..., PipelineConfig(matcher=cfg.coarse_matcher, use_ecc=False, n_bootstrap=0, min_inliers=cfg.min_inliers))`; OK → shift = found window centre − prior window centre, converted to metres east/south; `coarse_note = f"{coarse_gsd_m:g} m/px {matcher}, {n_inliers} inliers, shift {e:+.3f},{s:+.3f} m (E,S)"`; not OK → `coarse_note = f"coarse pass failed ({status})"` (A112: no claim about which prior was used).
   b. **Prior**: coarse OK → `search_prior = "coarse pass"`; else `cfg.prior_shift_m` not None → `search_prior = f"prior shift {e:g},{s:g} m (E,S)"`; else `"label corners"` (or `"geometry grid"` when the prep used one).
   c. **Fine prep** at `cfg.gsd_m`, `cfg.margin_m`, the chosen shift, `band_reduction=cfg.band_reduction`. Not OK → recorded in `ProductRun.prep`, no matching.
   d. `cfg.dry_run` → write `out_dir/preview/<tag>_src.png` and `_ref.png` (check `cv2.imwrite` return; False → prep_detail notes it) and continue (A110).
   e. For each matcher: `register_pair(pair.source, pair.reference, pair_id, PipelineConfig(matcher, model, min_inliers, ransac_threshold_px, gsd_m, preprocess, ecc_prefilter, extra={...}), source_valid=pair.source_valid, reference_valid=pair.reference_valid, source_id, reference_id, source_sensor, reference_sensor, synthetic=False, notes=<run_vikram's note text>)`. `extra` = `pair.geometry_extra()` + `{"site", "level", "window_m", "margin_m", "coarse_pass", "search_prior"}` + sun keys: `source_sun_azimuth/elevation` from `sun_from_label` (A113: OHRC sun as **source** sun), `reference_sun_azimuth/elevation/source` from the reference sun JSON when present. `source_sun`/`reference_sun` arguments are passed **only** when both suns share the same `azimuth_frame` (they do not today: OHRC `label_unverified` vs NAC `grid_up_clockwise`), otherwise None.
   f. OK → `label_offset_m` (as `run_vikram.centre_offset_m`) into extra; registered GeoTIFF when `save_registered` (origin = `reference_geo.x0_m + c0·psx`, `reference_geo.y0_m − r0·psy`, pixel size `gsd_m`, crs `reference_geo.crs_proj4`), path into `extra["registered_geotiff"]`; save immediately with `save_results([r], results_root, overwrite=cfg.overwrite)`; `FileExistsError` → listed as not saved.
5. After the loop: `save_failures(batch.failures, results_root)`; write `run_record.json` in `out_dir` (C15) with counts per `RunStatus`, per `PrepStatus`, per instrument status; artefacts = saved npz paths + GeoTIFFs + previews.

## 3. `compute_exp1_gate` (C20)
For each tag in `tags`: load every stored result whose `pair_id` contains the tag (live store); `best` = the OK result with the most `n_inliers` among those with `u_score ≥ 0.7` (else most inliers overall); agreement = `eval.agreement.agreement_for_stored` over that strip's OK results with `pre_ecc_transform`; `passes_targets = best.n_inliers ≥ 20 and best.u_score ≥ 0.7 and agreement.passes`. Tags with no result → `status = "no_result"`, `passes_targets = False`. `decision = "SKIP_1B"` iff every tag passes, else `"BUILD_1B"`. Output keys exactly C20.

## 4. `scripts/run_vikram.py` (thin CLI)
Keeps every current flag (defaults unchanged, `--min-inliers` default stays 5 for the demo per TBD 1.8 settings — pass it into `SiteConfig.min_inliers`), adds `--instruments`, `--levels`, `--preprocess`, `--ecc-prefilter`, `--results-root`, `--out-dir`, `--overwrite`, `--reference-sun-json`, `--band-reduction`; builds a `SiteConfig`, calls `run_site`, prints `report.report()`, returns `0 if report.any_ok else 1` (A111). `--export-only` still calls `export_stored`. `--dry-run` never runs the coarse pass (A110).

## 5. Tests the prompt adds (`tests/test_site_runner.py`)
With monkeypatched `build_catalog`, `georeference_from_label`, `prepare_window_pair` (returning a synthetic `WindowPair` built from `eval.scenes.illumination_pair`) and a tmp results root: OK path saves one npz per matcher and a `run_record.json`; coarse failure produces the A112 note and uses `prior_shift_m`; dry-run makes no `register_pair` call (monkeypatch counts) and writes previews; ABSENT instruments appear in `report()`; exit semantics via `any_ok`; `compute_exp1_gate` on a hand-built store (three tags: one passing, one failing, one missing) → `BUILD_1B`, and all-passing → `SKIP_1B`.
