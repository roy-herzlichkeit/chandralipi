# STATUS

current: P1.21
phase: 1
state: READY
branch: phase-1
last_done: P1.20
notes:
- P1.20 gate: BUILD_1B, 0 of 3 strips passing, all status no_result (data/processed/vikram/exp1_gate.json); doc docs/VIKRAM_2023_DIAGNOSIS.md.
- Cause class: ILLUMINATION_SUSPECTED for 20230823T1450475804, 20230823T1647285085 and 20230823T1647285315 (data/processed/vikram/exp1/diagnosis.json; run record data/processed/vikram/exp1/diagnosis_run/run_record.json).
- Reference sun: SPICE azimuth 327.09 deg north_clockwise (COMPUTED), DTM-fit peak_margin 0.046 (data/processed/vikram/reference_sun/reference_sun.json).
- Fourth-attempt artefacts checked and kept; only the gate step re-run (old files in data/processed/vikram/p1_20_attempt4_gate_superseded/). exp-1a console has 3 recovered CUDA allocator OOM warnings (noted in the doc).
- Open: Q-P1.20-1 (exp-1 ran with preset none) and Q-P1.20-2 (whether the classification needs a run record; now provided).
