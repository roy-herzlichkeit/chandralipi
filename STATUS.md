# STATUS

current: P2.06
phase: 2
state: READY
branch: phase-2
last_done: P2.05
notes:
- P2.05: PipelineConfig gains device=None, precision="auto" (C03; ValueError outside PRECISIONS). register_pair records device/precision/seconds_total (+seconds_match, peak_vram_bytes on cuda, timing_source/peak_vram_source="measured") in every RunOutcome.extra and PairResult.extra. torch.OutOfMemoryError -> RunStatus.OOM at stage "match" (detail = first line), empty_cache after the except clause.
- _build_matcher(name, *, device, precision) now gets keyword args; 4 stub lambdas in tests/test_presets.py and tests/test_matcher_registry.py changed to `lambda name, **kw:`.
- learned.py: LoFTR/LightGlue forward passes in try/finally; empty_cache only while an exception propagates (A077, success-path empty_cache removed); LoFTR fp16 / DISK autocast also on "cuda:<n>" (`_is_cuda`, pipeline `_resolve_precision` startswith; tests/test_pipeline_gpu.py). superglue.py untouched (Q-P2.05-3).
- Classical matchers always record device "cpu" and never import torch; unknown/stub names use config.device or "cpu" (Q-P2.05-1). Q-P2.04-1 (planner cap at max_tile_px) is still open for P2.06.
- Full CPU suite (scripts/ci.sh) 1079 passed; GPU tests in check passed (lightglue peak_vram_bytes > 0).
