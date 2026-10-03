# STATUS

current: P2.08
phase: 2
state: READY
branch: phase-2
last_done: P2.07
notes:
- P2.07: classical.py caps akaze/kaze/brisk at max_features after detection (POSTHOC_CAP_DETECTORS, strongest by response, stable ties); every ClassicalMatcher meta has max_features_applied (True only for those three, Q-P2.07-3); meta adds n_keypoints_{src,ref}_detected and max_features_truncated_{src,ref}; n_keypoints_*_raw is the count after max_features.
- RIFT2Matcher(max_tile_px=None): the default is computed once at construction from free_memory_bytes("cpu") (300 B/px, INFERRED; 0 + UNKNOWN when meminfo is unreadable, which refuses every input). Both inputs over the cap raise ValueError naming it. The cap is a property, and TiledMatcher now sizes RIFT2 tiles from it (Q-P2.07-2).
- to_uint8 gained keyword-only sample_step and lo_hi, and runs in 4096-row blocks. Images up to 4e7 px are stretched in float64 (byte-identical to P1.08) and larger images in float32 (a deviation from the LLD's float32 wording, Q-P2.07-1). Empty strided sample falls back to all valid or finite pixels, with a warning.
- The one RuntimeWarning (NaN cast to uint8) is unchanged from the P1.08 unmasked behaviour and is triggered by the new NaN test.
- Full CPU suite (scripts/ci.sh) passes (1126 passed, scratch log ci_p207.log).
