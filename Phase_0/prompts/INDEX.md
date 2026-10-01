# Phase 0 — prompt index

Status values: `todo` | `done` | `failed` | `skipped`. Implementers edit only the status column (CLAUDE.md).

| order | id | title | depends | check | status |
|---|---|---|---|---|---|
| 1 | P0.00 | preflight | — | harness/check_P0.00.sh | done |
| 2 | P0.01 | test runner + CI baseline | P0.00 | harness/check_P0.01.sh | done |
| 3 | P0.02 | learned matchers merge | P0.01 | harness/check_P0.02.sh | done |
| 4 | P0.03 | dedupe shadow_mask and scale_ratio | P0.01 | harness/check_P0.03.sh | done |
| 5 | P0.04 | remove footprint.py and default.yaml | P0.03 | harness/check_P0.04.sh | done |
| 6 | P0.05 | PDS4 resolver document order | P0.01 | harness/check_P0.05.sh | done |
| 7 | P0.06 | catalogue footprints as polygons | P0.04 | harness/check_P0.06.sh | done |
| 8 | P0.07 | provenance enum, run record, seeded fit | P0.01 | harness/check_P0.07.sh | done |
| 9 | P0.08 | ECC model fidelity, no mutation, gate, mask | P0.07 | harness/check_P0.08.sh | done |
| 10 | P0.09 | counts, refit threshold, classification | P0.02, P0.08 | harness/check_P0.09.sh | done |
| 11 | P0.10 | results schema v2 + persisted failures | P0.09 | harness/check_P0.10.sh | done |
| 12 | P0.11 | run_vikram numeric crop geometry | P0.10 | harness/check_P0.11.sh | done |
| 13 | P0.12 | eval correctness | P0.09 | harness/check_P0.12.sh | done |
