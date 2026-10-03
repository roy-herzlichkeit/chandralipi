# STATUS

current: P2.11
phase: 2
state: READY
branch: phase-2
last_done: P2.11
notes:
- P2.11 (Q-P2.11-1 answer (a)): LLD cmd + --native-matcher lightglue -> data/processed/gpu_run/anchor; native ok, drift 0.7361811246 coarse px, 2367 native inliers (data/processed/gpu_run/anchor/store_rows.json); oom 0 (data/processed/gpu_run/anchor/run_record.json).
- Peak VRAM lightglue 2830844416 bytes MEASURED (data/processed/gpu_run/anchor/store_rows.json). seconds_match (same file): sift 0.419, akaze 0.311, asift 19.304, lightglue 0.411 (cuda); loftr matcher_error, untiled 1343x1330 > 896 px INFERRED cap (Q-P2.11-2).
- Earlier runs A (LLD as written: sift native drift_exceeded 2.453) and B archived in data/processed/gpu_run_archive_20261003/. No 2023 tag passes (data/processed/vikram/exp1_gate.json).
- Open: Q-P2.11-2 (LoFTR untiled, guard ignores profile), Q-P2.11-3 (doc snapshots under data/, runs used preprocess none).
- P2.11 was the last prompt of Phase 2: §Phase end pending.
