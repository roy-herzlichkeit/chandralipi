[← back to index](TBDs.md) · prev: [Phase 2](TBD_phase_2.md) · next: [Phase 4](TBD_phase_4.md)

# Phase 3 — Cluster computing, Stage 2: one machine, N GPUs

Source: `udocs/70_SYSTEM_DESIGN_distributed_gpu.md` Part 3 (architecture) and
Part 6 ("perhaps 150 lines on top of the existing pipeline... No broker, no
cluster, no new dependency"). **Blocked on [Phase 2](TBD_phase_2.md)** — the
tile-size/VRAM numbers this stage schedules against must be real, not
host-RSS proxies.

## 3.1 Worker process, pinned per GPU
- **File(s):** new — no worker module exists yet anywhere in `src/lunar_reg/`.
- **Design constraints already decided by the doc** (Part 3, "Why stateless
  workers"): a worker loads model weights once at startup, then loops
  take-job → read two windows → match → write result → acknowledge; holds no
  cross-job state; is addressed by `CUDA_VISIBLE_DEVICES` per process.
- **Done when:** N worker processes, each pinned to one GPU via
  `torch.multiprocessing` + `CUDA_VISIBLE_DEVICES`, each independently able to
  take a job off an in-process queue and produce a result.

## 3.2 Job descriptor as a real, serializable, self-contained object
- **File(s):** new. The doc gives the exact shape to implement (Part 3, "The
  job descriptor"): `job_id` (content hash, the idempotency key), `source`/
  `reference` as `{uri, window}` — **never raw pixel data**, `matcher`,
  `precision`, `tile_px`, `est_vram_bytes` (from
  `device.py`'s closed-form cost model), `seed` (for RANSAC determinism).
- **Why this matters even at single-machine scale:** the doc calls this the
  thing that makes Stage 3 "a transport swap rather than a redesign" — get the
  boundary right here and multi-machine reuses it unchanged.
- **Done when:** the planner emits these descriptors for a real pair's tile
  grid, and a worker can execute one given only the descriptor (no shared
  in-memory state with the planner).

## 3.3 In-process queue + local results directory
- **File(s):** new. `multiprocessing.Queue` of job descriptors; results written
  as one file per tile job, named by content hash (idempotent — a duplicate
  execution overwrites itself with identical content, per Part 5).
- **Done when:** a full strip's tile jobs run through the queue across N local
  GPU workers and land as individual result files in a local directory.

## 3.4 Reducer: stitch → fit → refine → metrics
- **File(s):** `src/lunar_reg/match/stitch.py` (exists, overlap-aware
  stitching already implemented for the single-process case — reuse, don't
  rewrite), `src/lunar_reg/align/estimate.py` / `refine.py` (RANSAC, ECC —
  already implemented, CPU, "milliseconds" per the doc so no distribution
  needed here), `src/lunar_reg/eval/` (metrics, uniformity, conditioning —
  same).
- **Current state:** these all already exist and run correctly in the
  single-process pipeline; Stage 2's job is to point them at the queue's
  collected per-tile results instead of a single-process match call.
- **Done when:** the reducer consumes all of one strip's tile-job result files
  and produces the same shape of output `pipeline.py` produces today (registered
  product + points + metrics + a classified-outcome diagnostics report).

## 3.5 Classified outcomes carried through the queue
- **File(s):** extends whatever failure-classification exists today in
  `pipeline.py` / `overlap.py` (`OverlapStatus`) to the queue path.
- **Required, per this project's standing rule** (`docs/project/CONTEXT.md` §3.2, and
  restated for the distributed case in the design doc Part 5): every job ends
  in exactly one outcome from `OK / NO_MATCHES / DEGENERATE_OVERLAP /
  READ_FAILED / OOM / WORKER_LOST / TIMEOUT`, counted and sampled, printed on
  every run. **`NO_MATCHES` and `WORKER_LOST` must never collapse into a
  generic "failed"** — one is a data result, the other an infrastructure fault.
- **Done when:** a run with induced failures (kill a worker mid-job; force an
  OOM by requesting an oversized tile) produces a printed report that correctly
  separates these categories, matching the table in Part 5 of the design doc.

---
[← back to index](TBDs.md) · prev: [Phase 2](TBD_phase_2.md) · next: [Phase 4](TBD_phase_4.md)
