# Phase 1B — prompt index

Built only when `data/processed/vikram/exp1_gate.json` says `BUILD_1B` (DECISIONS G02). Status values: `todo` | `done` | `failed` | `skipped`.

| order | id | title | depends | check | status |
|---|---|---|---|---|---|
| 1 | P1B.00 | preflight + exp-1 gate | P2 approved | harness/check_P1B.00.sh | todo |
| 2 | P1B.01 | DTM shaded-relief renderer | P1B.00 | harness/check_P1B.01.sh | todo |
| 3 | P1B.02 | rendered reference preparation | P1B.01 | harness/check_P1B.02.sh | todo |
| 4 | P1B.03 | pooled multi-matcher consensus | P1B.00 | harness/check_P1B.03.sh | todo |
| 5 | P1B.04 | RIFT2 fixes | P1B.00 | harness/check_P1B.04.sh | todo |
| 6 | P1B.05 | site runner: bridge mode | P1B.02, P1B.03, P1B.04 | harness/check_P1B.05.sh | todo |
| 7 | P1B.06 | RUN: bridge on 2023 strips + RIFT2 baseline | P1B.05 | harness/check_P1B.06.sh | todo |
