# Phase 1 — prompt index

Status values: `todo` | `done` | `failed` | `skipped`. Implementers edit only the status column. P1.DL is out of sequence and never "next" (CLAUDE.md §Handoff).

| order | id | title | depends | check | status |
|---|---|---|---|---|---|
| 1 | P1.00 | preflight | P0 approved | harness/check_P1.00.sh | done |
| 2 | P1.DL | download session (out of sequence) | — (may run any time) | harness/check_P1.DL.sh | done |
| 3 | P1.01 | downloads manifest + verifier | P1.00 | harness/check_P1.01.sh | done |
| 4 | P1.02 | public fetch script (+ run step) | P1.01 | harness/check_P1.02.sh | done |
| 5 | P1.03 | product catalog + scan diagnostics | P1.01 | harness/check_P1.03.sh | done |
| 6 | P1.04 | NAC georeference from label | P1.00 | harness/check_P1.04.sh | done |
| 7 | P1.05 | geometry grid fixes | P1.00 | harness/check_P1.05.sh | done |
| 8 | P1.06 | overlap: grid wiring + fixes | P1.05, P1.03 | harness/check_P1.06.sh | done |
| 9 | P1.07 | datum convention + data test | P1.04, P1.05 | harness/check_P1.07.sh | done |
| 10 | P1.08 | nodata in radiometric + shadow | P1.00 | harness/check_P1.08.sh | done |
| 11 | P1.09 | preprocess geometry + StepStatus | P1.08 | harness/check_P1.09.sh | done |
| 12 | P1.10 | presets inside register_pair | P1.09 | harness/check_P1.10.sh | done |
| 13 | P1.11 | reference sun geometry | P1.04 | harness/check_P1.11.sh | done |
| 14 | P1.12 | cross-matcher agreement | P1.00 | harness/check_P1.12.sh | done |
| 15 | P1.13 | window-pair preparation | P1.04, P1.06, P1.08 | harness/check_P1.13.sh | done |
| 16 | P1.14 | matcher registry + SuperGlue opt-in | P1.00 | harness/check_P1.14.sh | done |
| 17 | P1.15 | TMC-2 + IIRS skip-if-absent | P1.03, P1.09 | harness/check_P1.15.sh | done |
| 18 | P1.16 | site runner | P1.10, P1.11, P1.12, P1.13, P1.14 | harness/check_P1.16.sh | done |
| 19 | P1.17 | run_jaxa, ablation driver, cli register/inspect | P1.10, P1.16 | harness/check_P1.17.sh | done |
| 20 | P1.24 | cross-instrument pairs at any site | P1.17 | harness/check_P1.24.sh | done |
| 21 | P1.25 | keypoint cap for brute-force matching (ASIFT) | P1.24 | harness/check_P1.25.sh | todo |
| 22 | P1.18 | RUN: archive v1, ablation, JAXA re-run | P1.17, P1.24, P1.25 | harness/check_P1.18.sh | todo |
| 23 | P1.19 | RUN: apply preset default + anchor into live store | P1.18 | harness/check_P1.19.sh | todo |
| 24 | P1.20 | RUN: 2023 diagnosis + exp-1 gate | P1.19 | harness/check_P1.20.sh | todo |
| 25 | P1.21 | viewers | P1.20 | harness/check_P1.21.sh | todo |
| 26 | P1.22 | docs + status refresh | P1.21 | harness/check_P1.22.sh | todo |
| 27 | P1.23 | code docstrings + script hints | P1.22 | harness/check_P1.23.sh | todo |
