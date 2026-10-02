# STATUS

current: P1.19
phase: 1
state: READY
branch: phase-1
last_done: P1.18
notes:
- P1.18: preconditions passed; verify_downloads --no-scan exit=0, 211 files ok (scratchpad p1/verify_P1.18.log); catalog shows OHRC anchor nrp_20240425T1406019344 at level raw and LRO_NAC present; steps 1, 3, 5 not re-run. Q-P1.18-4 (non-blocking): step 4a moved all 12 first-attempt files into cross/attempt1_vikram_only/; run records git_dirty=true from untracked proposal*.txt plus a QUESTIONS.md edit, no code changed; proposal_outline_original.txt (human's) left alone.
- Ablation, ASIFT capped (data/processed/ablation/ablation.json): winner ohrc_nac, reason "anchor passes none=2 ohrc_nac=4 clahe_shadow=4; anchor tie between ohrc_nac, clahe_shadow; median synthetic truth_rms_px ohrc_nac=0.137 clahe_shadow=0.1373; ohrc_nac wins on synthetic". All 12 anchor rows ok, ASIFT included. Old run moved to data/processed/ablation_attempt1_asift_uncapped/.
- JAXA real demo v2: ok 10, all failure counts 0 (estimation/eval/matcher/oom/refinement/too_few_* = 0) (data/processed/demo_real/v2/run_record.json).
- Cross (data/processed/cross/overlaps.json, run_record.json): 20 candidates, 3 OVERLAP / 17 DISJOINT, NAC/SELENE nearest 457.3–663.7 km; 3 pairs run, 2 registrations OK / 7 failed, 0 setup errors. Both OK are TMC2 ncf_20231026T0943001971 vs tmc2_ortho_20231027 (sift 313 inliers, akaze 105; data/processed/cross/runs/tmc2_ortho_20231027/20231026T0943001971/run_record.json), RELATIVE ONLY (reference independent=false); saved to live store data/processed/results. IIRS: 0 ok (nci_20221226: too_few_matches 3; nci_20230125: too_few_matches 2, too_few_inliers 1). TMC2 ncn_20230521 DISJOINT from the ortho at 33.6 km.
- Differs from LLD runs.md §P1.18 step 4: IIRS nci_20221226T0416479474 also OVERLAPs tmc2_ortho_20231027 (14 of 1968 nodes, 224.0 km2), besides expected TMC-2 ncf_20231026T0943001971 (1803 nodes) and IIRS nci_20230125T1944138897 (20 nodes) (data/processed/cross/overlaps.json).
