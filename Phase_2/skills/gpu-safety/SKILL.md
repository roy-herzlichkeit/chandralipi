---
name: gpu-safety
description: Rules for code and runs that touch the laptop GPU (RTX 4060 Laptop, 8 GB, ~0.75 GB used by the desktop). Used by every Phase 2–4 prompt that imports torch or runs a learned matcher.
---

# GPU safety

| rule | exact behaviour |
|---|---|
| one process | never start a second GPU process while one runs (CLAUDE.md); check `nvidia-smi` first |
| budget | plan against `0.75 × free` from `free_memory_bytes(device)` at the start of the run (G18), never the nameplate |
| OOM | catch `torch.OutOfMemoryError` **before** `RuntimeError`; classify it (`RunStatus.OOM`, `TileStatus.OOM`, `JobStatus.OOM`); call `torch.cuda.empty_cache()` after an OOM, not on the success path |
| lazy import | `import torch` inside functions in `pipeline.py`, `device.py` helpers and any CPU-only path |
| device strings | `"cpu"`, `"cuda"`, `"cuda:<n>"`; parse the index with `int(device.split(":")[1])` when present |
| precision | LoFTR: fp16 via autocast on CUDA; DISK fp16 autocast, LightGlue fp32 (P0.02); record `precision` in results |
| measurements | peak VRAM = `torch.cuda.max_memory_allocated(dev)` after `reset_peak_memory_stats(dev)`; label it MEASURED; never estimate a VRAM number into a doc |
| tests | `@pytest.mark.gpu` + `pytest.skip("CUDA not available")` guard; inputs ≤ 512 px; no test leaves tensors on the GPU (call `torch.cuda.empty_cache()` in teardown when it allocated) |
