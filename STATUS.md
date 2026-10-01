# STATUS

current: P0.11
phase: 0
state: READY
branch: phase-0
last_done: P0.10
notes:
- P0.10: results.py schema v2 (C04/C05): PAIR_ID_PATTERN validation, ransac_mask/pre_ecc_transform/schema_version, JSON-encoded container cells, atomic npz/index/failures writes, save_pair refuses overwrite, failures.parquet (append), StoreReport + reindex(force) that KEEPS a good index. pipeline: PairResult gets ransac_mask/pre_ecc_transform; run_batch persists results + failures, BatchReport.store. Scripts print store.report(); reindex_results --force, exit 1 when KEPT.
- Live store untouched (13 v1 pairs load read-only). Q-P0.10-1: script re-runs now refuse existing pair ids.
- scripts/ci.sh: 516 passed, 6 deselected.
- P1.DL may run before Phase 0 approval (Phase_1/prompts/P1.DL_download_session.md).
