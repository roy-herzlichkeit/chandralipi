# Phase 3 — local decisions

| ID | decision | reason | rejected |
|---|---|---|---|
| D3-1 | The local queue is a SQLite file with WAL and `BEGIN IMMEDIATE` transactions. | Process-safe on one host, inspectable after a crash, no service to install; Phase 4 swaps only the queue implementation (HLD §3). | `multiprocessing.Queue` (no leases, lost on crash); a directory of lock files |
| D3-2 | One job = one source tile at the reference native GSD, with its own reference window and 3×3 prior. | Self-contained jobs are what makes WORKER_LOST recovery and multi-host execution possible (TBD 3.2). | Whole-strip jobs; window-only descriptors (udocs/70) |
| D3-3 | The reducer skips ECC. | ECC needs whole images; native strips are never loaded whole. The refit at 1 px is the final stage. | Tiled ECC (unmeasured) |
| D3-4 | GPU workers fall back to CPU (and say so) when CUDA is unavailable. | Tests and the benchmark run on any host; the report states which device each worker used. | Refusing to run |
