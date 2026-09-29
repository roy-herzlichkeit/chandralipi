# LLD — CUDA environment, free memory, device profiles, benchmark CLI (P2.01–P2.04)

Produces: C16, C17. Closes: A073 (match-3), A074 (tooling-7), A126 (match-4), A075 (match-6), A076 (match-7), A089 rest (device.py:137 citation, memory.py:243-254 text). TBD 2.1, 2.2. Facts: torch 2.14.0+cu130 installed, `torch.cuda.is_available()` True, 8188 MiB total, ~754 MiB used by the desktop (FABLE_NOTES §9); `torch.OutOfMemoryError` subclasses `RuntimeError` (research).

## P2.01 — setup + free memory (C17)
- `scripts/setup.sh`: `--cuda` installs `torch==<pinned>` from `https://download.pytorch.org/whl/<index>`; new flag `--cuda-index` (default `cu130`; `cu126` for older drivers); the pinned version is read from the currently installed torch when present, else `2.14.0`. The verify step prints and asserts `torch.version.cuda` is not None when `--cuda` was given. README and `scripts/README.md`: replace every `cu124` mention with the flag description.
- `device.py`: add `MemoryReading` and `free_memory_bytes` exactly per C17. Device strings: `"cpu"`, `"cuda"` (= current device index), `"cuda:<n>"`. `free_vram_bytes(device)` returns `free_memory_bytes(device).free_bytes` — for `"cpu"` that is now host `MemAvailable`, never the 8 GiB nameplate. `ASSUMED_TOTAL_VRAM_BYTES` stays only as documentation of the nameplate; nothing uses it as a fallback (a failed reading is `UNKNOWN` with 0 bytes, and planners given 0 bytes return `TileBudget.fits = False`).
- Remove the device.py:137 citation of a non-existent CLI (it exists after P2.03 — keep the text but make it true: `lunar-reg benchmark`).

## P2.02 — device profiles (C16)
- `TileBudget` gains `fits: bool` and `source: ValueSource` (appended; defaults `True`, `ValueSource.INFERRED`).
- `plan_dense_tile(device="cuda", precision="fp16", matcher="loftr", profile: DeviceProfile | None = None)`: when `profile` has an entry for `(matcher, precision)`, choose the largest multiple of 64 ≤ `MAX_DENSE_TILE_PX` with `fixed_bytes + bytes_per_px · tile² ≤ safety · free` → `source = MEASURED`; else today's analytic model → `source = INFERRED`. The `MIN_DENSE_TILE_PX` floor still applies but sets `fits = est_peak_bytes <= safety · free` (A126: no silent raise).
- `DeviceProfile` per C16; `load_profile_for(device_name)` → the profile whose `device_name` equals the CUDA device name, searched in `configs/device_profiles/*.json`; None when absent.
- `configs/device_profiles/README.md`: the C16 schema, how a profile is produced (`lunar-reg benchmark`, P2.04), and that a profile is MEASURED data (G19: never hand-edited).

## P2.03 — benchmark CLI
`lunar-reg benchmark --matcher loftr|lightglue --precision fp16|fp32 --tile-sizes 256,384,512,640,768,896,1024 --device cuda|cpu --out DIR [--profile-out PATH] [--timeout 900]`
- `match/memory.py`: `MeasureOutcome(str, Enum)`: `OK, OOM, TIMEOUT, SETUP_ERROR, NO_OUTPUT`, parsed from the subprocess: exit 0 with `PEAK_BYTES` → OK; stderr containing `OutOfMemoryError` or `CUDA out of memory` → OOM; `TimeoutExpired` → TIMEOUT; non-zero exit otherwise → SETUP_ERROR; exit 0 without `PEAK_BYTES` → NO_OUTPUT. `MemoryMeasurement` gains `outcome: MeasureOutcome`; `method`/`device` not reported by the snippet → `"unknown"` (not the host defaults). The memory.py:243-254 text stops asserting driver facts on non-CUDA outcomes.
- `match/benchmark.py`: `RLIMIT_AS` only when the device is CPU (A075); on CUDA the snippet calls `torch.cuda.reset_peak_memory_stats()` before and reports `torch.cuda.max_memory_allocated()`; the sweep stops at the first OOM only (other failures are recorded and the sweep continues). New `fit_profile(rows) -> dict` = least squares of `peak_bytes = fixed + k · tile²` over OK rows (needs ≥ 3 OK rows, else raises `ValueError`), returning the C16 per-precision entry with `points`.
- CLI writes `DIR/benchmark_<matcher>_<precision>.json` (rows + outcome counts), prints a table and the outcome report, writes `run_record.json` (C15), and with `--profile-out` merges the fitted entry into that C16 file (creating it with `device_name`, `total_bytes`, `torch`, `cuda`, `driver` from `nvidia-smi --query-gpu=driver_version --format=csv,noheader`).

## P2.04 — RUN (gpu): measure the RTX 4060 profile
Preconditions: CUDA available; nothing else on the GPU but the desktop (`nvidia-smi`).
Commands (in order, one GPU process at a time):
1. `lunar-reg benchmark --matcher loftr --precision fp16 --device cuda --out data/processed/benchmarks/p2_04 --profile-out configs/device_profiles/rtx4060-laptop.json`
2. same with `--precision fp32`
3. `lunar-reg benchmark --matcher lightglue --precision fp16 --tile-sizes 512,768,1024,1536,2048 --device cuda --out data/processed/benchmarks/p2_04 --profile-out configs/device_profiles/rtx4060-laptop.json`
Artefacts: the profile JSON (C16-valid, `source == "measured"`, ≥ 3 points per entry), three benchmark JSONs, run records. `tests/test_device.py`'s CPU pins are **not** changed (they pin CPU host-RSS measurements; the GPU profile is separate data).
