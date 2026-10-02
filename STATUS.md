# STATUS

current: P1.14
phase: 1
state: READY
branch: phase-1
last_done: P1.13
notes:
- P1.13: new src/lunar_reg/pairs.py (C11 PrepStatus/WindowPair/PrepOutcome/prepare_window_pair; PriorSource re-exported from ingest.overlap) + PrepDiagnostics (counts, first sample, report()); P1.16 should record each outcome and print report() every run. Windowed reads only, decimated (Resampling.average, nearest for mask) at shrink factor >= 4.
- Prior source: explicit geometry_grid_path wins; else grid looked up under <product>/geometry, then the label dir's parent, found by a case-insensitive timestamp token (real LIDs use lower-case 't'); no token -> no discovery (Q-P1.13-2); no grid -> label corners. Unreadable grid -> READ_FAILED (no fallback); grid not covering corners -> NO_FOOTPRINT. source_id from the lower-case LID.
- Q-P1.13-1 (non-blocking): all-nodata source window returns OK with all-False source_valid (C11 has no member); pca no longer raises on it. Extras beyond LLD listed there -> review pack LLD deviations.
- scripts/run_vikram.py not touched (P1.16 switches it over).
- scripts/ci.sh: 852 passed (log: scratchpad p1/ci_P1.13.log); check_P1.13 ~11 s.
