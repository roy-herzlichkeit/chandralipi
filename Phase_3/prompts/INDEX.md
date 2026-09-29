# Phase 3 — prompt index

Status values: `todo` | `done` | `failed` | `skipped`.

| order | id | title | depends | check | status |
|---|---|---|---|---|---|
| 1 | P3.00 | preflight | P1B approved (built or skipped) | harness/check_P3.00.sh | todo |
| 2 | P3.01 | job descriptor | P3.00 | harness/check_P3.01.sh | todo |
| 3 | P3.02 | job outcomes + result files | P3.01 | harness/check_P3.02.sh | todo |
| 4 | P3.03 | planner | P3.02 | harness/check_P3.03.sh | todo |
| 5 | P3.04 | queue protocol + local queue | P3.02 | harness/check_P3.04.sh | todo |
| 6 | P3.05 | worker | P3.03, P3.04 | harness/check_P3.05.sh | todo |
| 7 | P3.06 | reducer | P3.02 | harness/check_P3.06.sh | todo |
| 8 | P3.07 | local runner + CLI | P3.05, P3.06 | harness/check_P3.07.sh | todo |
| 9 | P3.08 | fault injection + determinism | P3.07 | harness/check_P3.08.sh | todo |
| 10 | P3.09 | RUN (gpu): single-host distributed run | P3.08 | harness/check_P3.09.sh | todo |
