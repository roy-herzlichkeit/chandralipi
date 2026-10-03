# STATUS

current: P2.09
phase: 2
state: READY
branch: phase-2
last_done: P2.08
notes:
- P2.08: new src/lunar_reg/align/native.py (C19): lift_to_native, refine_native_arrays (source resampled to reference GSD with INTER_AREA plus full-support validity mask as source_valid, S = inv(C11 to_native), P = prior @ inv(S), TiledMatcher(tile_px or 512), 3 px fit then 1 px inlier refit, T_native = T_fit @ S, drift over a 5x5 probe grid in coarse px). NativeStatus, NativeRefinement (C19 fields unchanged) + provenance property, report(), NativeDiagnostics; thresholds are Sourced constants.
- Status rules in LLD order (TOO_FEW_MATCHES, ESTIMATION_FAILED, DRIFT_EXCEEDED, TILE_FAILURES, OK); TILE_FAILURES (transform None) replaces TOO_FEW_MATCHES/ESTIMATION_FAILED when more than half the tiles failed and no fit could be made; TOO_FEW_MATCHES detail names tile counts and cause. f < 1 raises ValueError (Q-P2.08-2).
- Not re-exported from lunar_reg.align (outside the file fence); P2.10 imports lunar_reg.align.native directly. Non-blocking Q-P2.08-3 on pairs.py _resample's INTER_NEAREST mask (outside the fence).
- Check passes but takes 35.7 s wall (over the G18 30 s budget). 27.0 s of that is the protected harness terrain((2048,2048)) fixture; refine itself takes 0.42 s (Q-P2.08-1; logs in scratchpad/p2/check_p208.log and c19_split_p208.log).
