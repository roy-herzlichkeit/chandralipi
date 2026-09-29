# Phase 3 benchmark rubric

`bash Phase_3/benchmark/run.sh` → `Phase_3/benchmark/score.json` (schema as Phase 0). All values MEASURED by that run (synthetic GeoTIFFs for the fault and order checks; P3.09 artefacts for the equivalence check).

| axis | weight | metric | threshold |
|---|---|---|---|
| correctness | 0.35 | min(pass fraction `Phase_3/harness/tests`, CPU suite) | 1.0 |
| spec_conformance | 0.25 | contract tests P0–P3 | 1.0 |
| quality | 0.4 | fraction passing: **faults_classified** — a CPU run with injected faults (worker `cpu0` killed after 1 claim, 1 OOM tile, 1 read-failure tile, 1 duplicated result) ends with every job terminal, `lost_events ≥ 1`, exactly 1 `oom`, 1 `read_failed`, 1 duplicate counted, and an OK reducer (TBD 3.5: 100 % classification); **order_independent** — the same plan with 1 and 3 CPU workers gives byte-identical reduced transforms (TBD 4.4); **single_process_equivalence** — the P3.09 distributed transform and the single-process `refine_native_arrays` transform differ by ≤ 0.1 reference px at 5 probes | 1.0 |
