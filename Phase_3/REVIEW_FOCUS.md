# Phase 3 — review focus

| # | where | why | how to check |
|---|---|---|---|
| 1 | `distributed/queue.py` transactions | Double-claims or lost acks corrupt counts silently. | `test_P3_04.py` (2 processes × 50 jobs); read each SQL statement's WHERE clause. |
| 2 | `distributed/worker.py` coordinate lifting | Native coordinates from tiles must use the same pixel-centre rule as C11/C19. | `test_C25_process_job_synthetic`; recompute one point by hand. |
| 3 | `distributed/reducer.py` ordering | Determinism depends on sorting by `(job_id, point index)` before fitting and on seeded fits. | `test_C26_order_independent`; the benchmark's order check. |
| 4 | `distributed/faults.py` | Fault injection must not change production code paths (only hooks passed in). | Grep for `faults` imports outside tests. |
| 5 | `docs/DISTRIBUTED_RUN.md` | Numbers from the run record only. | Paths next to numbers. |
