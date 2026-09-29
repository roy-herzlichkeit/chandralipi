# LLD — device, timing, VRAM and OOM in register_pair (P2.05)

Produces: C03 fields `device`, `precision`; C02 member `OOM` becomes produced. Closes: A077 (match-5). TBD 2.3.

1. `PipelineConfig.device: str | None = None` (None → `get_device()`), `precision: str = "auto"` (`"auto"` → `"fp16"` on CUDA for LoFTR, `"fp32"` elsewhere; LightGlue ignores it — DISK fp16 / LightGlue fp32 as P0.02). Passed to `match.build_matcher(name, device=…)` and, for LoFTR, `precision=…`.
2. Timing: `time.perf_counter()` around the matcher call → `extra["seconds_match"]`; around the whole `register_pair` → `extra["seconds_total"]`.
3. VRAM: when the device starts with `"cuda"`, call `torch.cuda.reset_peak_memory_stats(dev)` before matching and record `torch.cuda.max_memory_allocated(dev)` after matching as `extra["peak_vram_bytes"]` (int); `extra["device"]`, `extra["precision"]` always recorded.
4. OOM: catch `torch.OutOfMemoryError` **before** the generic matcher `except` → `RunStatus.OOM`, `stage = "match"`, detail = first line of the message; then `torch.cuda.empty_cache()`.
5. `learned.py`: every forward pass in `try/finally`; the `finally` releases local tensors and calls `torch.cuda.empty_cache()` only when an exception is propagating (A077: the success path keeps the allocator warm).
6. torch is imported lazily (classical-only runs on CPU must not import torch; test: `sys.modules` has no `torch` after a sift run in a fresh subprocess).
Tests (`tests/test_pipeline_gpu.py`): fields and defaults; OOM classification with a stub matcher raising `torch.OutOfMemoryError("CUDA out of memory")`; timing keys present; a `gpu`-marked LightGlue run records `peak_vram_bytes > 0`; the lazy-import subprocess test.
