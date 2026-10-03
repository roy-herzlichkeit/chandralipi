# STATUS

current: P2.04
phase: 2
state: READY
branch: phase-2
last_done: P2.03
notes:
- memory.py: MeasureOutcome (ok/oom/timeout/setup_error/no_output) + MeasureDiagnostics.report(); MemoryMeasurement gains appended `outcome` (default OK); unreported method/device = "unknown"; OOM also on MemoryError / CPU allocator / SIGKILL rc -9 (Q-P2.03-1); describe_measurement_capability(device) no longer asserts driver facts.
- benchmark.py: SNIPPETS[(matcher, precision)] replaces MATCHER_SNIPPETS; explicit device in the snippet, RLIMIT_AS on CPU only; sweep stops at first OOM only; fit_profile(rows) -> C16 entry (max_tile_px = largest OK measured tile, Q-P2.03-3); merge_profile_entry, cuda_device_facts, free_bytes_before_sweep (nvidia-smi, so the parent holds no CUDA context). Review fix: free_bytes_before_sweep returns None (UNKNOWN) when torch sees no CUDA device; `--device cuda` with no CUDA classifies every size as setup_error, writes JSON + run_record and exits 1.
- `lunar-reg benchmark`: writes DIR/benchmark_<m>_<p>.json and DIR/run_<m>_<p>/run_record.json (per-run dir so P2.04's 4 runs into one DIR keep their provenance, Q-P2.03-2); --profile-out needs --device cuda (exit 2 otherwise); exit 1 on non-OOM failure or profile not written.
- For P2.04: the CLI process makes no CUDA context until after the sweep; the C16 profile's run_record/measured_utc/free_bytes_at_measure name the latest merged run. CPU smoke of all 4 snippets at 128 px returned ok (no GPU run done).
- New tests/test_benchmark_cli.py (31 tests); scripts/ci.sh: 1055 passed, 22 deselected.
