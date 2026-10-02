# STATUS

current: P1.18
phase: 1
state: READY
branch: phase-1
last_done: P1.17
notes:
- P1.17: new scripts/run_jaxa.py (PairPrepStatus ok/input_missing/no_overlap; pair ids JAXA_SELENE_TC-JAXA_SELENE_TC_<m> and JAXA_SELENE_TC-LRO_WAC_<m>; run record at data/processed/demo_real/v2/run_record.json, relative to the cwd; common_gsd_m_source per pair, cross = documented (WAC grid pixel size); crop_bounds_source=computed) and scripts/run_ablation.py (AZIMUTH_DELTAS/SEEDS are module constants; synthetic matchers = (sift, lightglue) intersected with --matchers; an anchor matcher with no outcome gets a row with status "not_run", so there are always presets x matchers anchor rows; prints a per-status outcome report with the first sample of each status; failed synthetic rows carry detail and pair_id). Neither script was run on real data.
- cli.py: `register` now runs through register_pair (defaults sift, threshold 3.0, max-px 1152, --preprocess/--save-root/--pair-id; the --output JSON has exactly the LLD §3 keys; exits 0 only on OK). The tiled path and --overlap are removed. `overlap --crop-dir` prints "skipped <n>, e.g. <id>". `inspect` was already correct at HEAD and is unchanged.
- cli.py is still not ruff-formatted (it was not at HEAD either); ruff check passes.
- Non-blocking: Q-P1.17-1 (choices beyond the LLD: resampling, georeference NOOP fallback, extra JSON keys, not_run anchor rows, the synthetic matcher set).
- scripts/ci.sh: 928 passed, 18 deselected (log: scratchpad p1/ci_P1.17.log).
