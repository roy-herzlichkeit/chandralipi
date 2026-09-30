# Phase 2 benchmark rubric

`bash Phase_2/benchmark/run.sh` → `Phase_2/benchmark/score.json` (schema as Phase 0). All values MEASURED by that run from the repo, the device profile and the P2.11 artefacts.

| axis | weight | metric | threshold |
|---|---|---|---|
| correctness | 0.35 | min(pass fraction of `Phase_2/harness/tests`, pass fraction of the CPU suite); GPU/data tests run on this laptop (skips counted separately) | 1.0 |
| spec_conformance | 0.25 | pass fraction of contract tests P0 + P1 + P2 (C01–C19) | 1.0 |
| quality | 0.4 | fraction passing: **profile_measured** (`configs/device_profiles/rtx4060-laptop.json` is `measured` with ≥ 3 points per entry); **native_within_1_coarse_px** (anchor native refinement `ok` and drift ≤ 1 coarse (4 m) px — TBD 1.8 step 6); **vram_headroom** (max `peak_vram_bytes` of the anchor GPU rows ≤ 0.75 × profile `total_bytes`, G18); **no_oom** (0 `oom` and ≥ 1 `ok` outcome in `data/processed/gpu_run/anchor/run_record.json`, review RC36) | 1.0 |
| synthetic | 0 (gates `pass`) | max probe error (reference px) of `refine_native_arrays` on a 2048² synthetic native source vs a 1 m reference with a known transform and a 0.5 coarse-px prior error | ≤ 0.5 px |
