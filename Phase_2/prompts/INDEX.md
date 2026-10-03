# Phase 2 — prompt index

Status values: `todo` | `done` | `failed` | `skipped`. Implementers edit only the status column.

| order | id | title | depends | check | status |
|---|---|---|---|---|---|
| 1 | P2.00 | preflight (CUDA live) | P1 approved | harness/check_P2.00.sh | done |
| 2 | P2.01 | CUDA setup + free memory | P2.00 | harness/check_P2.01.sh | done |
| 3 | P2.02 | device profiles | P2.01 | harness/check_P2.02.sh | done |
| 4 | P2.03 | benchmark CLI | P2.02 | harness/check_P2.03.sh | done |
| 5 | P2.04 | RUN (gpu): measure RTX 4060 profile | P2.03 | harness/check_P2.04.sh | done |
| 6 | P2.05 | device, timing, VRAM, OOM in register_pair | P2.02 | harness/check_P2.05.sh | todo |
| 7 | P2.06 | prior-driven tiling + tile outcomes | P2.05 | harness/check_P2.06.sh | todo |
| 8 | P2.07 | classical caps + RIFT2 memory guard | P2.06 | harness/check_P2.07.sh | todo |
| 9 | P2.08 | native-GSD refinement | P2.06 | harness/check_P2.08.sh | todo |
| 10 | P2.09 | georeferenced blockwise warp | P2.00 | harness/check_P2.09.sh | todo |
| 11 | P2.10 | site runner: GPU + native mode | P2.05, P2.08, P2.09 | harness/check_P2.10.sh | todo |
| 12 | P2.11 | RUN (gpu): end-to-end GPU run | P2.04, P2.10 | harness/check_P2.11.sh | todo |
