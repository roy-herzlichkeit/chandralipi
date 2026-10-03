[← back to index](TBDs.md) · prev: [Phase 3](TBD_phase_3.md) · next: [Phase 5](TBD_phase_5.md)

# Phase 4 — Cluster computing, Stage 3: many machines

Source: `udocs/70_SYSTEM_DESIGN_distributed_gpu.md` Part 3, Part 4, Part 6.
**Blocked on [Phase 3](TBD_phase_3.md)** — the doc is explicit that this stage
should be "a transport swap rather than a redesign" if Stage 2's job
descriptor boundary was built correctly; do not start this phase by
redesigning the job format.

## 4.1 Pick and stand up a broker
- **Decision, not yet made:** the doc names two options and doesn't pick —
  **Ray** ("fewer lines") or **Redis Streams** ("fewer moving parts"). Neither
  is a current dependency (`pyproject.toml` has no cluster/broker package
  today). This is a call for whoever builds the HLD to make, informed by
  whatever's easiest to demo on SIH's available machines.
- **Done when:** the in-process `multiprocessing.Queue` from Stage 2 is
  replaced by the chosen broker, with the worker code otherwise unchanged.

## 4.2 Shared/node-local storage for product data
- **File(s):** new. The doc lays out three options in preference order (Part 4,
  "Locality"): (1) node-local cache keyed by consistent hashing on product URI
  — first touch pulls to local NVMe, everything after is local; (2)
  pre-staging, since the planner knows the full job list before dispatch; (3)
  reading from object storage every time — "simple... but measure before
  assuming it is fine" given ~1,300 HTTP range requests per strip per pair.
- **Constraint already established:** `rasterio` (already a dependency) does
  windowed reads — the job descriptor carries a window, never a whole array;
  this must not regress when storage becomes remote.
- **Done when:** a multi-machine run demonstrably does not re-fetch a whole
  1.2 GB strip per tile job — instrument and report the actual bytes read per
  strip against the ~1,300-tiles-per-strip baseline in the doc's Part 1.

## 4.3 Capacity-aware, bin-packed scheduling across heterogeneous GPUs
- **File(s):** extends the Stage 2 planner. Two policies from Part 3:
  **homogeneous-first** (drain one tile size at a time, since
  `match/learned.py` already calls `torch.cuda.empty_cache()` per dense pass
  specifically to avoid fragmentation) and **capacity-aware dispatch** (worker
  advertises free VRAM, planner sends the largest job that fits — this is what
  lets an 8 GB card and a 24 GB card coexist in one fleet).
- **Done when:** a mixed-capacity fleet (simulate with two workers artificially
  capped at different VRAM budgets, if a real heterogeneous fleet isn't
  available) is scheduled without OOMs and without leaving the larger card
  starved of appropriately-sized work.

## 4.4 Determinism across workers
- **File(s):** RANSAC call sites in `align/estimate.py`; the reducer's
  match-merge step.
- **Required, per Part 5:** the seed lives in the job descriptor (derived from
  the job hash) so the same job samples identically regardless of which worker
  runs it; the reducer sorts matches by a stable key before fitting, so the
  final transform doesn't depend on result-arrival order. The doc's own
  warning: skip the second point and "two runs over the same data produce
  transforms that differ in the last decimal places, and you will lose an
  afternoon to it."
- **Done when:** the same job set run twice (different worker-assignment order
  enforced deliberately) produces bit-identical or tolerance-identical final
  transforms.

## 4.5 At-least-once delivery correctness
- **File(s):** the results-writing path from Stage 2 (3.3), unchanged in
  approach — content-hash-named result files already make duplicate delivery
  harmless. This item is about *verifying* that property still holds once a
  real broker can redeliver a job after a lease expiry, not building something
  new.
- **Done when:** a deliberately-duplicated job (same descriptor dispatched
  twice) produces one result file, overwritten identically, with no
  double-counting in the reducer.

---
[← back to index](TBDs.md) · prev: [Phase 3](TBD_phase_3.md) · next: [Phase 5](TBD_phase_5.md)
