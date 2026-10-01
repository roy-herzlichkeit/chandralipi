# STATUS

current: P0.04
phase: 0
state: READY
branch: phase-0
last_done: P0.03
notes:
- P0.03: radiometric.shadow_mask deleted (suppress_shadows + preprocess.__init__ use shadow.shadow_mask); constants.scale_ratio deleted; pseudo_gt.MAX_DIRECT_SCALE_RATIO now imports constants.MAX_SAFE_SCALE_RATIO (8.0).
- tests/test_footprint.py: removed test_scale_ratios_match_the_documented_sensor_gaps (file deleted in P0.04). pseudo_gt.py got ruff format drift.
- scripts/ci.sh: 448 passed, 5 deselected.
- P1.DL (download session) may run before Phase 0 is approved: see Phase_1/prompts/P1.DL_download_session.md.
