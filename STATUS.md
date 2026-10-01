# STATUS

current: P0.10
phase: 0
state: READY
branch: phase-0
last_done: P0.09
notes:
- P0.09: RunStatus (9 members), RunOutcome.extra, PipelineConfig P0 fields (C02/C03). register_pair: staged + classified (match/estimate/refine/eval), raw points stored with refit inlier_mask over the raw set (G34), ransac_mask computed but not yet stored (P0.10 adds ransac_mask=/pre_ecc_transform= to PairResult). metrics: n_ransac_inliers, ransac_inlier_ratio, residual_basis, self_residual_subpixel (is_subpixel gone). Empty reasons in classical + rift2.
- Tests updated (named in commit): test_eval.py:54, test_results_and_pipeline.py:47,76-77.
- Q-P0.09-1 (non-blocking): check_P0.09 takes ~69 s (pre-existing 64 s ASIFT test). scripts/ci.sh: 503 passed, 6 deselected.
- P1.DL may run before Phase 0 approval (Phase_1/prompts/P1.DL_download_session.md).
