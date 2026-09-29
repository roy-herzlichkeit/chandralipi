# Phase 2 — review focus

| # | where | why | how to check |
|---|---|---|---|
| 1 | `match/tiled.py` rectification + lifting | A wrong composition order silently misplaces every tile's matches. | `test_C18_scaled_prior`; read `T_t` construction against `Phase_2/LLD/tiling.md` step 2. |
| 2 | `align/native.py` `S` and `lift_to_native` | Half-pixel conventions decide whether native refinement has a systematic bias. | `test_C19_*`; recompute `S` for a 2048 → 512 resize by hand. |
| 3 | `pipeline.py` OOM ordering | `torch.OutOfMemoryError` is a `RuntimeError`; the wrong `except` order hides OOMs as matcher errors. | `test_P2_05.py::test_oom_classified`. |
| 4 | `configs/device_profiles/rtx4060-laptop.json` | Measured data drives every later tile plan; must come from the P2.04 run record, never hand edits. | Compare with `data/processed/benchmarks/p2_04/*.json`. |
| 5 | `docs/GPU_RUN.md`, `docs/VRAM_CONSTRAINTS.md` | Panel-facing numbers. | Every number has an artefact path next to it. |
