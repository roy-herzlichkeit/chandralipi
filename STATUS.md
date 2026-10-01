# STATUS

current: P0.03
phase: 0
state: READY
branch: phase-0
last_done: P0.02
notes:
- P0.02: match/loftr.py deleted; superglue.py keeps SuperGlueMatcher + licence_report only (uses learned._to_tensor). learned.py: _to_tensor via to_uint8 for non-uint8, LoFTR pads to 8 and drops padding matches, LightGlue matcher runs outside autocast in fp32 (CUDA works), meta per LLD §2. ClassicalMatcher meta on every result (incl. empty).
- ruff format applied to the 4 touched src files (pre-existing formatting drift in classical.py/stitch.py/superglue.py shows in the diff).
- Harness test_P0_02: 11 passed incl. CUDA LoFTR fp16 + CUDA LightGlue. scripts/ci.sh: 449 passed, 5 deselected.
- P1.DL (download session) may run before Phase 0 is approved: see Phase_1/prompts/P1.DL_download_session.md.
