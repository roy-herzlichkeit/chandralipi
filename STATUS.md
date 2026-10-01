# STATUS

current: P1.10
phase: 1
state: READY
branch: phase-1
last_done: P1.09
notes:
- P1.09: pipeline.StepStatus (ran/skipped_missing_input/noop/failed/degenerate_output); StepRecord.status (`ran` property); handlers return (image, detail, status, reason); PreprocessResult gains pixel_transform (3x3, input px centre -> output px centre), pixel_transform_source (weakest over composed steps), status_counts, failed; uses_placeholders needs config value == placeholder.
- PreprocessContext gains valid/reference_valid (passed to every radiometric/shadow step); run_pipeline works on a context copy; resample (INTER_NEAREST_EXACT mask) and georeference (reproject_valid_mask, nodata 0) move `valid`; after georeference context.valid = isfinite(output). Non-2-D after band_reduction -> FAILED; constant/all-zero normalize -> DEGENERATE_OUTPUT.
- Resample GSD per config.side (new config field, Q-P1.09-1), nominal fallback (gsd_source="nominal" + one warning), SKIPPED_MISSING_INPUT without GSD/target. SensorSpec gains gsd_source (all DOCUMENTED), gsd_note.
- georeference reprojects onto reference grid (float32, NaN init/dst_nodata), FAILED on grid-shape mismatch; pixel matrix is an affine fit of the CRS mapping with RMS in detail (Q-P1.09-2, LLD deviation for review pack). Q-P1.09-3 (non-blocking): nearest mask can mark INTER_AREA nodata blends valid.
- No existing assertions changed; config.py left unformatted. scripts/ci.sh: 741 passed (log: scratchpad p1/ci_P1.09.log).
