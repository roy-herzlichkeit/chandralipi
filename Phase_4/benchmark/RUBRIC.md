# Phase 4 benchmark rubric

`bash Phase_4/benchmark/run.sh` → `Phase_4/benchmark/score.json` (schema as Phase 0). Values MEASURED from the harness run and the P4.06 artefacts under `data/processed/multihost/anchor/`.

| axis | weight | metric | threshold |
|---|---|---|---|
| correctness | 0.35 | min(pass fraction `Phase_4/harness/tests`, CPU suite) | 1.0 |
| spec_conformance | 0.25 | contract tests P0, P3, P4 (C22–C27) | 1.0 |
| quality | 0.4 | fraction passing: **worker_lost_reclaimed** (run record `lost_events ≥ 1` — the injected loss was reclaimed and counted, TBD 4.1); **idempotent_merge** (`mismatched == 0`; duplicates counted, TBD 4.5); **bytes_per_host** (every OK job result carries `bytes_read > 0` and ≥ 2 hosts appear, TBD 4.2); **no_oom** (0 `oom` outcomes with the heterogeneous fleet, TBD 4.3) | 1.0 |
