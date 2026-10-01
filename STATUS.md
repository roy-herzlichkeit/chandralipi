# STATUS

current: P0.12
phase: 0
state: READY
branch: phase-0
last_done: P0.12
notes:
- P0.12: ErrorBudget.shares + quadrature dominant; one least-squares bootstrap core (fit_lsq, conditioning_map max == headline max, conditioning_map_with_failures, estimator="lsq"); uniformity adaptive grid g_eff (G33), n_out_of_frame, shared _bin; oracle fit uses pipeline model; uint8 sweep chains; gate *_SOURCE siblings + gate_source in as_dict. error_budget ecc_cc None crash fixed (Q-P0.08-1).
- Updated test: tests/test_eval.py::test_enforce_uniformity_cannot_create_coverage (fixed-grid occupied cells). Q-P0.12-1 (non-blocking).
- scripts/ci.sh: 536 passed, 6 deselected. Last Phase 0 prompt: §Phase end in progress.
