# Phase 4 — review focus

| # | where | why | how to check |
|---|---|---|---|
| 1 | `distributed/redis_queue.py` reclaim path | Lease loss handling decides whether WORKER_LOST is counted or silently retried (G04's reason for Redis). | `test_C27_*`; read the XAUTOCLAIM → XACK → XADD sequence. |
| 2 | RESP protocol pinning | RESP3 changes reply shapes; tests on fakeredis would still pass (research). | `test_P4_01.py::test_protocol_pinned`; verify.sh real-server tests. |
| 3 | `scripts/cluster_up.sh` | Runs commands on another machine; quoting and dry-run behaviour matter. | Read it; run `--dry-run`. |
| 4 | `outcome.merge_result_dirs` | Decides whether cross-host non-determinism is visible. | `test_P4_05.py`. |
| 5 | `configs/hosts.json` handling | Must never be committed with real addresses or secrets. | `git ls-files configs/` shows only the example. |
