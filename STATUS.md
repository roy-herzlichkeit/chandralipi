# STATUS

current: P1.18
phase: 1
state: READY
branch: phase-1
last_done: P1.25
notes:
- P1.25: classical.py caps total keypoints per image before BFMatcher, strongest by response, original order kept (G42). BF_TRAIN_LIMIT=262143 (MEASURED, opencv 4.14.0); ASIFT_MAX_TOTAL_KEYPOINTS=50000 (INFERRED); ClassicalMatcher(max_total_keypoints=) validated 2..BF_TRAIN_LIMIT; meta on every result: max_total_keypoints, n_keypoints_{src,ref}_raw, keypoints_capped_{src,ref}. ASIFT not run on real data here.
- P1.24 done (cross.py, run_cross.py find|run, configs/references.json). Q-P1.24-1 non-blocking.
- P1.18 resumes: steps 1, 3, 5 artefacts already on disk (uncommitted, data/processed); re-run step 2 (ablation, now with the ASIFT cap) and step 4 (via scripts/run_cross.py, per the revised LLD).
- scripts/ci.sh: 950 passed, 18 deselected (log: scratchpad p1/ci_P1.25.log).
