# STATUS

current: P1.24
phase: 1
state: READY
branch: phase-1
last_done: P1.17
notes:
- Q-P1.18-1 answered by the architect (Phase_1/QUESTIONS.md): new prompt P1.24 (cross-instrument pairs at any site, G41) runs before P1.18. P1.18 step 4 then runs via scripts/run_cross.py. Steps 1, 3 and 5 artefacts stay as they are.
- P1.18 steps 1, 2, 3, 5 are done (uncommitted RUN artefacts under data/processed): v1 store moved to data/processed/results_archive_20260929; ablation winner ohrc_nac (data/processed/ablation/ablation.json); JAXA v2 10 OK (data/processed/demo_real/v2/run_record.json).
- Q-P1.18-3 answered: new prompt P1.25 (ASIFT keypoint cap, G42) runs after P1.24. P1.18 then re-runs steps 2 (ablation) and 4.
- Harness revised by the architect: tags phase-1-harness-r1 and r2 (G05); verify.sh guards from the newest.
- P1.01-P1.17 committed on phase-1.
