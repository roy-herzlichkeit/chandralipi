# STATUS

current: P1.09
phase: 1
state: READY
branch: phase-1
last_done: P1.08
notes:
- P1.08: every LLD preprocess_nodata §2 function takes valid=None (to_uint8, apply_clahe, normalize_intensity, suppress_shadows, invert, dilate, log_transform, match_histogram(+reference_valid), standard_chain, shadow_mask/fraction/estimate_shadow_severity/normalize_shadows). Masked uint8 output reserves 0 for nodata (radiometric.VALID_U8_MIN=1); float output NaN. Effective mask = valid & isfinite (shadow._effective_valid; ValueError on shape mismatch; empty mask -> all-0/all-NaN + one warning per call).
- _retinex (A107) fills NaN/invalid with valid median before blurring, restores NaN; reflectance range over usable pixels only. standard_chain computes the effective mask once and passes it to every step (NaN inside valid stays 0 through to_uint8/apply_clahe); hand-chained callers must pass the effective mask themselves.
- valid=None byte-identical to pre-change: hashes captured at HEAD 1d978f0 before editing (scratchpad p1/p108_hashes_before.txt), pinned in tests/test_preprocess_nodata.py (65 tests + review tests: retinex independent of nodata values; NaN inside valid through chain). pipeline.py untouched (P1.09 wires context.valid).
- Non-blocking Q-P1.08-1: method="none" with valid returns float32 NaN-masked copy; non-finite pixels count as nodata; log_transform valid outputs not clipped to >=1.
- ruff clean/formatted on the 3 files; scripts/ci.sh: 716 passed (log: scratchpad p1/ci_P1.08.log).
