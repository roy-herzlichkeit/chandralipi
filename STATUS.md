# STATUS

current: P2.11
phase: 2
state: READY
branch: phase-2
last_done: P2.10
notes:
- P2.10: six SiteConfig fields appended with Phase 1 defaults (device=None, precision="auto", native=False, native_matcher="sift", native_tile_px=None, native_max_drift_coarse_px=1.0); device/precision go into coarse and fine PipelineConfig; run_vikram flags --device, --precision, --native, --native-matcher, --native-tile-px. native=True with native_matcher missing from matchers raises ValueError; TMC2/IIRS are not_applicable (not a failure).
- Native: OK native_matcher result refined once per strip, prior moved into window px (Q-P2.10-1); extra keys native_status/_n_matches/_n_inliers/_drift_coarse_px/_transform (product->raster, JSON)/_gsd_m/_tiles_<status>/_provenance/_detail, full LLD key set on every outcome, native_drift_coarse_px nan when no value (Q-P2.10-3a). NativeRunStatus/NativeRunDiagnostics in report(); run_record gets native_<status> counts.
- Native GeoTIFF: <out_dir>/registered/<pair_id>_native.tif (not REGISTERED_DIR), via warp_blockwise from the in-memory source window. Working-GSD GeoTIFF does NOT get source_valid (Phase 1 output unchanged); Q-P2.09-3(a) stays open (Q-P2.10-3b).
- CPU suite (scripts/ci.sh): 1170 passed; check_P2.10 about 10-15 s. ruff format not run on run_vikram.py (never ruff-formatted, Q-P2.10-2f).
- P2.11 is the last prompt of Phase 2: §Phase end is pending after it.
