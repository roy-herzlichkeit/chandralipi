# STATUS

current: P0.01
phase: 0
state: READY
branch: phase-0
last_done: P0.00
notes:
- P0.00: tagged phase-base-approved at main 4e018d6; branch phase-0 created from it.
- Baseline (pytest -o addopts="" -p no:cacheprovider): 440 collected; 440 passed, 0 failed, 0 skipped, 10 warnings (129 s).
- ASSUMPTIONS A0-1..A0-10 all hold (py 3.12.3, cv2 4.14.0, torch 2.14.0+cu130, kornia 0.8.3, ruff 0.16.6; results index 13 rows; weights + 4 OHRC labels present).
- P1.DL (download session) may run before Phase 0 is approved: see Phase_1/prompts/P1.DL_download_session.md.
