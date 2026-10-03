# STATUS

current: P2.02
phase: 2
state: READY
branch: phase-2
last_done: P2.01
notes:
- P2.01 setup.sh: --cuda-index (default cu130, cu126 older drivers); --cuda pins torch==<ver>+<cuda-index> (ver from installed torch minus local tag, or 2.14.0 fresh); verify prints torch.version.cuda, fails if None or suffix mismatch. README/scripts/README drop cu124. Unchecked offline: whether download.pytorch.org/whl/cu126 has torch 2.14.0+cu126 (setup.sh now fails loudly if not).
- device.py: MemoryReading + free_memory_bytes per C17 ("cpu" /proc/meminfo, "cuda" current index, "cuda:<n>" mem_get_info(n)); any failure -> UNKNOWN, 0 bytes. free_vram_bytes = free_memory_bytes(...).free_bytes (host MemAvailable for "cpu"). ASSUMED_TOTAL_VRAM_BYTES documentation only (_SOURCE=DOCUMENTED); tile constants unchanged.
- Tests: tests/test_device.py unchanged (9 pass); new tests/test_free_memory.py (13 tests, incl. gpu-marked real cuda:0); new tests/test_setup_cuda_pin.py (5 passed). Full CPU suite: 1019 passed.
- ruff format of device.py re-wrapped one existing line in plan_dense_tile (quadratic-root expression); formatting only.
