# Phase 0 — local decisions

May not contradict `docs/plan/DECISIONS.md`. ID | decision | reason | rejected alternatives.

| ID | decision | reason | rejected |
|---|---|---|---|
| D0-1 | Field paths gain one predicate form `Name[child=value]` (P0.05). | Document order alone picks the spacecraft, not the camera, in the real OHRC label; a predicate states the intent in the field map. | Special-casing `instrument` in `read_label`; keeping reverse order |
| D0-2 | New pytest marker `weights` for tests that need cached pretrained weights (P0.01). | CI has no weights; `data` means "files under data/raw". | Reusing `data`; downloading weights in CI |
| D0-3 | Data bundles unpack through `scripts/untar_data.py` using Python's `tarfile` `data` filter and a two-pass refuse-first check. | Testable, refuses traversal/links/outside-`data/` members before writing anything, never overwrites results. | `tar --wildcards 'data/*'` (no symlink or overwrite protection) |
| D0-4 | ECC displacement gate default 3.0 px (`ValueSource.INFERRED`), equal to the default RANSAC threshold. | ECC is a refinement; a jump larger than the outlier threshold the fit already used means it left the basin. No measurement exists yet. | k × RMSE; no gate |
| D0-5 | Affine models keep `RANSAC`; the docstring is corrected instead of switching to USAC for affine. | Switching estimators changes stored numbers with no evidence it helps. | `cv2.USAC_MAGSAC` for affine |
| D0-6 | Bootstrap conditioning uses least squares for every model, via one shared core. | LMEDS on resamples measured a different quantity per model (A040). | Keeping LMEDS for affine |
| D0-7 | `RegistrationMetrics.is_subpixel` is renamed `self_residual_subpixel` and `residual_basis` is added. | The old name claimed an accuracy property the value does not have (A023). | Keeping the name with a docstring caveat |
| D0-8 | `save_results` / `reindex` return `StoreReport` (C05); the three callers are updated in the same prompt. | Load failures must reach the caller (S14); a DataFrame cannot carry them. | `DataFrame.attrs`; module-level last report |
| D0-9 | `run_vikram` saves each OK result immediately and refuses to overwrite without `--overwrite`. | A crash must not lose computed results (A027); silent overwrite lost provenance (A028). | Save once at the end |
| D0-10 | Catalogue rows carry `footprint_wkt`; `footprint_from_row` prefers corners, then WKT, then bbox. | Catalogue rings have no UL/UR/LL/LR labels (A004). | Guessing corner order from ring geometry |
