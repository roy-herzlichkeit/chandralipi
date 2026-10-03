[← back to index](TBDs.md) · prev: [Phase 1](TBD_phase_1.md) · next: [Phase 3](TBD_phase_3.md)

# Phase 2 — Cluster computing, Stage 1: one machine, one real GPU

Source: `udocs/70_SYSTEM_DESIGN_distributed_gpu.md` Part 6, "Stage 1 (the next
real step)". **This is the actual prerequisite for everything else in Phases
3–4** — none of the VRAM/tile-size numbers used to design later stages have
been measured on real hardware yet.

## 2.1 Get a CUDA torch build actually running
- **File(s):** none — environment/install step. `./scripts/setup.sh --cuda`
  already exists and runs `pip install torch --index-url
  https://download.pytorch.org/whl/cu124` (documented in `README.md`).
- **Current state:** the development machine has no loaded NVIDIA kernel
  module; torch is CPU-only there. No run on any GPU has ever happened in this
  project (`docs/project/CONTEXT.md` §"most likely to mislead").
- **Done when:** `lunar-reg env` reports CUDA available on the target machine
  (RTX 4060 per `README.md`'s stated target, or whatever GPU is actually used).

## 2.2 Re-measure the memory model's constants on real hardware
- **File(s):** `src/lunar_reg/device.py` — specifically
  `BACKBONE_BYTES_PER_PX = 3203.0` (measured, but as a host-RSS proxy),
  `FP16_BACKBONE_FACTOR = 0.6` (marked **ESTIMATED, NOT MEASURED** in the
  source itself), `MAX_DENSE_TILE_PX = 1408` (derived from the proxy figures).
  Also `src/lunar_reg/match/benchmark.py` (`benchmark_matcher`,
  `scaling_exponent`) and `match/memory.py`
  (`describe_measurement_capability`, which currently prints "VRAM CANNOT BE
  MEASURED ON THIS MACHINE").
- **Current state:** every capacity number in the distributed-design doc is
  labeled as inheriting this caveat. The scaling *shape* (S⁴ term dominating
  above ~1024 px) is trustworthy; the absolute byte figures are not.
- **Done when:** `match/benchmark.py` has been re-run on the real GPU, and
  `BACKBONE_BYTES_PER_PX` / `FP16_BACKBONE_FACTOR` / `MAX_DENSE_TILE_PX` in
  `device.py` are updated from measured VRAM, not host RSS. `is_device_measurement`
  (already present in `match/memory.py`) should read `True` for these runs.

## 2.3 Run the existing pipeline end-to-end on the GPU
- **File(s):** `src/lunar_reg/pipeline.py` (`run_batch`), unchanged logic —
  this step is about execution, not new code.
- **Current state:** `pipeline.run_batch()` iterates pairs sequentially with
  classified outcomes today, on CPU only.
- **Done when:** a full pipeline run (register_pair through eval) has executed
  on GPU end-to-end on at least one real pair, with LoFTR/LightGlue timings and
  peak-VRAM figures recorded and attributable to the run (not estimated).

---
[← back to index](TBDs.md) · prev: [Phase 1](TBD_phase_1.md) · next: [Phase 3](TBD_phase_3.md)
