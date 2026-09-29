# Phase 4 — prompt index

Status values: `todo` | `done` | `failed` | `skipped`.

| order | id | title | depends | check | status |
|---|---|---|---|---|---|
| 1 | P4.00 | preflight (hosts + redis) | P3 approved | harness/check_P4.00.sh | todo |
| 2 | P4.01 | Redis Streams queue | P4.00 | harness/check_P4.01.sh | todo |
| 3 | P4.02 | node-local cache + byte accounting | P4.01 | harness/check_P4.02.sh | todo |
| 4 | P4.03 | capacity-aware routing | P4.01 | harness/check_P4.03.sh | todo |
| 5 | P4.04 | host config + runbook + distributed CLI | P4.02, P4.03 | harness/check_P4.04.sh | todo |
| 6 | P4.05 | cross-worker determinism + idempotence | P4.04 | harness/check_P4.05.sh | todo |
| 7 | P4.06 | RUN (gpu, 2 hosts): two-host run | P4.05 | harness/check_P4.06.sh | todo |
