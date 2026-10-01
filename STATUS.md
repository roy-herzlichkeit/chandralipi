# STATUS

current: P0.09
phase: 0
state: READY
branch: phase-0
last_done: P0.08
notes:
- P0.08: refine.py gains EccStatus/EccOutcome/ECC_MAX_SHIFT_PX/ecc_refine (C07): homography->MOTION_HOMOGRAPHY 3x3, affine->MOTION_AFFINE 2x3, partial_affine skipped; copies only; 5x5 probe displacement gate; nodata/explicit masks via findTransformECCWithMask. refine_transform_ecc is a wrapper; refine_full(seed=) emits all C07 detail keys; reestimate_on_inliers(seed=) no longer writes the caller's mask.
- Q-P0.08-1 (non-blocking): eval/error_budget.py:230 crashes on detail["ecc_cc"] None; suggested for P0.12.
- scripts/ci.sh: 497 passed, 6 deselected. Open non-blocking Qs: P0.04-1, P0.05-1, P0.06-1, P0.08-1.
- P1.DL may run before Phase 0 approval (Phase_1/prompts/P1.DL_download_session.md).
