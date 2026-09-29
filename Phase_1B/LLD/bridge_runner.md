# LLD — site runner bridge mode (P1B.05) and the bridge run (P1B.06)

## P1B.05 — `sites/runner.py`
`SiteConfig` gains (appended): `bridge: bool = False`, `bridge_dtm: Path = Path("data/raw/reference/lro_nac_vikram/NAC_DTM_VIKRAMSITE1.TIF")`, `bridge_matchers: tuple[str, ...] = ("sift", "akaze", "asift", "lightglue", "rift2")`, `bridge_anchor_tag: str = "20240425T1406019344"`, `bridge_calibration_json: Path = Path("data/processed/bridge/azimuth_calibration.json")`.
Flow when `bridge=True` (after the Phase 1 fine prep of each strip):
1. Calibration: if `bridge_calibration_json` exists, load it; else compute it once from the anchor's best stored v2 result (most inliers) with `pairs.calibrate_label_azimuth` (re-preparing the anchor's `WindowPair` with the stored shift) and write it (JSON = the `AzimuthCalibration` fields + inputs + run record path).
2. Source sun in grid frame: `calibration.to_grid(label_azimuth)`, elevation from the label; `SunGeometry(azimuth, elevation, INFERRED, DOCUMENTED, "grid_up_clockwise", note=…)`.
3. Two reference variants: `nac` (the pair as prepared) and `rendered` (`prepare_rendered_pair`).
4. For each variant: `consensus.register_consensus(pair.source, variant.reference, f"{base_pair_id}_bridge-{variant}", cfg.bridge_matchers, PipelineConfig(... ecc_prefilter="local_contrast" for nac, "none" for rendered ...), source_valid, reference_valid, ids…)`; `extra` adds `bridge_variant`, `bridge_sun_azimuth_grid`, `bridge_calibration_convention`, `bridge_calibration_residual_deg`, the crop geometry.
5. Selection: among OK variants, the one with the lower `conditioning["p95_px"]` gets `extra["bridge_selected"] = True`; both are saved.
6. CLI flags on `run_vikram.py`: `--bridge`, `--bridge-dtm`, `--bridge-matchers`.
Tests (`tests/test_runner_bridge.py`): monkeypatched preparation/consensus as in P1.16's tests; both variants saved with the right pair ids; selection flag on the lower-p95 variant; calibration JSON written once and reused.

## P1B.06 — RUN: bridge on the 2023 strips + RIFT2 baseline
Preconditions: `exp1_gate.json` decision `BUILD_1B`; anchor v2 result in the live store; DTM on disk.
1. `.venv/bin/python scripts/run_vikram.py --only 20230823 --instruments OHRC --levels raw --prior-shift 556,-2888 --margin-m 2000 --bridge --matchers sift --results-root data/processed/results --out-dir data/processed/bridge/run --overwrite` (the `--matchers sift` single-matcher pass is kept for comparison; the bridge adds the consensus rows).
2. RIFT2 baseline (TBD 1.8 exp-4): `.venv/bin/python scripts/run_vikram.py --only 20230823 --instruments OHRC --levels raw --prior-shift 556,-2888 --margin-m 2000 --matchers rift2 --results-root data/processed/results --out-dir data/processed/bridge/rift2 --overwrite`.
3. `docs/ILLUMINATION_BRIDGE.md` (G26): what the bridge is (plain words + a figure path from the run: the rendered reference preview), the calibration (convention, offset, residual, peak margin — INFERRED, with its JSON path), a per-strip table (variant, status, contributors, inliers, U, agreement, conditioning p95, selected), the RIFT2 baseline rows, and the TBD 1.8 target check per strip (≥ 20 inliers, U ≥ 0.7, agreement < 1 px). Numbers only with artefact paths.
Artefacts checked: `data/processed/bridge/azimuth_calibration.json`, run records C15-valid, ≥ 1 live-store row per 2023 tag whose `pair_id` contains `_bridge-`, and the doc citing `data/processed/bridge/`.
