# STATUS

current: P0.12
phase: 0
state: READY
branch: phase-0
last_done: P0.11
notes:
- P0.11: run_vikram records crop geometry (geometry_extra -> C04 keys) on every OK result; coarse note shift +.3f; _stored_shift returns None (no silent 0,0); export_stored classifies ExportStatus (recorded / regex_legacy / settings_unrecorded / input_missing / write_failed), tags model/min_inliers "unrecorded" when absent, exit 1 unless all exported. main saves each result immediately (--overwrite), BatchReport + save_failures, sun "n/a", exit 1 when nothing succeeded. Script NOT run on real data.
- run_vikram.py deliberately not ruff-formatted (~300 lines of pre-existing drift would bury the diff).
- scripts/ci.sh: 523 passed, 6 deselected. P0.12 is the last Phase 0 prompt -> then §Phase end (verify.sh, benchmark/run.sh, REVIEW_PACK_0.md).
- Open non-blocking Qs: P0.04-1, P0.05-1, P0.06-1, P0.08-1 (error_budget ecc_cc None -> P0.12), P0.09-1, P0.10-1.
