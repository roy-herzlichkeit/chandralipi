# Phase 1B benchmark rubric

`bash Phase_1B/benchmark/run.sh` → `Phase_1B/benchmark/score.json` (schema as Phase 0). Only run when Phase 1B was built (G02).

| axis | weight | metric | threshold |
|---|---|---|---|
| correctness | 0.3 | min(pass fraction `Phase_1B/harness/tests`, CPU suite) | 1.0 |
| spec_conformance | 0.2 | contract tests P0 + P1 + P2 + P1B | 1.0 |
| quality | 0.5 | fraction of the three 2023 strips whose best `_bridge-` row has ≥ 20 final inliers, U ≥ 0.7 and consensus agreement < 1 px (TBD 1.8 experiment 3 success criterion) | 1.0 (below 1.0 is a finding for the review, not a code failure) |
The azimuth-calibration residual (`data/processed/bridge/azimuth_calibration.json`) is reported in `detail`, not scored. There is no SYNTHETIC axis in 1B (the renderer's geometry is covered by harness tests).
