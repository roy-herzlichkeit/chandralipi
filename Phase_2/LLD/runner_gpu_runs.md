# LLD — site runner GPU + native mode (P2.10) and the GPU run (P2.11)

Closes: TBD 2.3, 1.8 step 6; A084 (tooling-10).

## P2.10 — `sites/runner.py`, `scripts/run_vikram.py`
`SiteConfig` gains (appended, defaults keep Phase 1 behaviour): `device: str | None = None`, `precision: str = "auto"`, `native: bool = False`, `native_matcher: str = "sift"`, `native_tile_px: int | None = None`, `native_max_drift_coarse_px: float = 1.0`.
- `device`/`precision` go into every `PipelineConfig` (P2.05).
- `native=True`: for each OK fine result whose matcher is `native_matcher` (one refinement per strip), read the native windows (`WindowPair.source_window` from the OHRC label via `pds4.open_product`; `reference_window` from the NAC), `prior_native = lift_to_native(result.transform, pair.source_to_native, pair.reference_to_native)`, call `refine_native_arrays(...)`, and store into the fine result's `extra`: `native_status`, `native_n_matches`, `native_n_inliers`, `native_drift_coarse_px`, `native_transform` (9 floats, JSON), `native_gsd_m = reference_native_gsd_m`, plus `native_tiles_<status>` counts. When `save_registered` and native status OK: write a native GeoTIFF at the reference native GSD with `warp_blockwise` (`dst_transform` from `GeoReference.affine()` shifted to the reference window) into `REGISTERED_DIR/<pair_id>_native.tif`.
- CLI flags: `--device`, `--precision`, `--native`, `--native-matcher`, `--native-tile-px`.
Tests (`tests/test_runner_native.py`): with monkeypatched I/O (as P1.16's tests) and a stub `refine_native_arrays` → native keys present in extra; `native=False` → none present.

## P2.11 — RUN (gpu): end-to-end GPU run
Preconditions: CUDA available; `configs/device_profiles/rtx4060-laptop.json` exists (P2.04).
1. `.venv/bin/python scripts/run_vikram.py --only 20240425T1406019344 --instruments OHRC --levels raw --matchers sift,akaze,asift,lightglue,loftr --device cuda --native --results-root data/processed/results --out-dir data/processed/gpu_run/anchor --overwrite`
2. For every 2023 tag whose `exp1_gate.json` row has `passes_targets: true`, the same command with `--only <tag>` and `--out-dir data/processed/gpu_run/<tag>`.
3. `docs/GPU_RUN.md` (G26): what ran, per-matcher table (status, seconds_match, peak_vram_bytes, inliers, U) read from the live store rows of this run, native refinement result (status, drift, native inliers), each value with its artefact path; `[INSERT RESULT]` where absent.
4. Rewrite `docs/VRAM_CONSTRAINTS.md` from `configs/device_profiles/rtx4060-laptop.json`: every figure tagged MEASURED (profile), COMPUTED (derived from the profile), or CAP (a constant in `device.py`), with the path next to it (A084).
Artefacts checked: run records C15-valid with `device` starting `cuda`; ≥ 1 anchor row in the live store with `x_device` starting `cuda`, `x_seconds_match` > 0 and `x_peak_vram_bytes` > 0; `x_native_status` present on the anchor's `native_matcher` row; both docs cite their artefact paths.
