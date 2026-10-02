# STATUS

current: P1.20
phase: 1
state: READY
branch: phase-1
last_done: P1.19
notes:
- P1.19: default chosen = ohrc_nac (choose_default_preset on data/processed/ablation/ablation.json; reason "anchor passes none=2 ohrc_nac=4 clahe_shadow=4; anchor tie between ohrc_nac, clahe_shadow; median synthetic truth_rms_px ohrc_nac=0.137 clahe_shadow=0.1373; ohrc_nac wins on synthetic"); PipelineConfig.preprocess default set in src/lunar_reg/pipeline.py; docs/PREPROCESS_ABLATION.md written.
- Anchor into live store: 4 of 4 matchers OK (outcome_counts ok=4, saved=4, 0 failures; data/processed/vikram/runs/p1_19_anchor/run_record.json); 4 live-store rows *_pp-ohrc_nac with schema_version 2 in data/processed/results.
- Q-P1.19-1 (non-blocking): run_vikram's --preprocess defaults to SiteConfig.preprocess="none" (src/lunar_reg/sites/runner.py:152), so step 4 was run with --preprocess ohrc_nac appended; P1.20 commands also omit --preprocess (they would run "none") — the next prompt should check the answer.
- Q-P1.19-2 (non-blocking): 5 existing tests pinned preprocess="none" (blank images now fail in the ohrc_nac preset stage) and test_pipeline_config_default_is_none now asserts "ohrc_nac"; CPU suite 950 passed, data/gpu-marked 18 passed.
- Q-P1.19-3 answered by the human (option b) and implemented: register_pair skips the preset when an input has no information (extra['preprocess_skipped']); the 6 protected harness tests pass; LLD deviation from preprocess_presets.md §2/§4 to list in REVIEW_PACK_1. scripts/ci.sh 955 passed (log: scratchpad p1/ci_Q-P1.19-3.log).
- ASIFT thread cap (Q-P1.20-0): the three P1.20 crashes were ASIFT detection using ~0.6 GB RAM per OpenCV thread (24 threads > 15 GiB host); detection now runs at ASIFT_DETECT_THREADS=4 (identical output). Post-fix exp-1a probe: asift peak 5.5 GB, lightglue 1.5 GB, no OOM (data/processed/probes/asift_memory_20261002.txt). Old partial P1.20 artefacts: data/processed/vikram/p1_20_attempt{1,2}_untrusted/ plus exp1/ and reference_sun/ from attempt 3.
