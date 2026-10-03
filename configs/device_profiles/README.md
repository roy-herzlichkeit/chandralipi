# Device profiles (CONTRACTS C16)

A device profile records how much GPU memory each learned matcher needs per tile
on one specific device. `lunar_reg.device.plan_dense_tile(..., profile=...)` and
`DeviceProfile.plan_tile(...)` use it to choose the largest tile that fits the
free memory; without a profile (or for a matcher/precision the profile lacks)
they fall back to the analytic model in `src/lunar_reg/device.py`, labelled
`ValueSource.INFERRED`.

## A profile is MEASURED data

- Profiles are produced only by `lunar-reg benchmark ... --profile-out
  configs/device_profiles/<slug>.json` (added in P2.03, run on the RTX 4060 in
  P2.04). The command measures peak memory per tile size on the device and fits
  `peak_bytes = fixed_bytes + bytes_per_px * tile_px^2` by least squares.
- Never write or edit a profile by hand (DECISIONS G19: every number comes from a
  run). To change a profile, re-run the benchmark; the file names the run record
  that produced it (`run_record`).
- `load_profile_for(device_name)` picks the file whose `device_name` equals the
  CUDA device name exactly (`torch.cuda.get_device_name()`). A file that fails
  validation raises `ValueError` rather than being skipped. If several files
  name the same device, the canonical `<slug>.json` wins and a warning lists
  all of them; keep one profile per device.

## Schema (`schema: 1`)

```json
{"schema": 1, "slug": "rtx4060-laptop", "device_name": "...", "total_bytes": 0,
 "free_bytes_at_measure": 0, "torch": "...", "cuda": "...", "driver": "...",
 "measured_utc": "...", "run_record": "<path>", "source": "measured",
 "matchers": {"<name>": {"<precision>": {"fixed_bytes": 0, "bytes_per_px": 0.0,
      "max_tile_px": 0, "points": [[256, 0]]}}}}
```

| key | meaning |
|---|---|
| `schema` | format version, `1` |
| `slug` | file stem, e.g. `rtx4060-laptop` |
| `device_name` | CUDA device name the profile applies to |
| `total_bytes` | total device memory reported at measurement time |
| `free_bytes_at_measure` | free device memory when the benchmark ran |
| `torch`, `cuda`, `driver` | torch version, CUDA runtime version, NVIDIA driver version |
| `measured_utc` | UTC time of the measurement |
| `run_record` | path of the benchmark's `run_record.json` (C15) |
| `source` | `"measured"` (a `ValueSource` value) |
| `matchers.<name>.<precision>.fixed_bytes` | fitted size-independent bytes (weights, workspace) |
| `matchers.<name>.<precision>.bytes_per_px` | fitted bytes per input pixel (coefficient of `tile_px^2`) |
| `matchers.<name>.<precision>.max_tile_px` | largest tile size the benchmark measured for this entry |
| `matchers.<name>.<precision>.points` | measured `[tile_px, peak_bytes]` pairs the fit used |

## Planning rule

For an entry `(matcher, precision)` the planner picks the largest multiple of 64,
at most `MAX_DENSE_TILE_PX`, with `fixed_bytes + bytes_per_px * tile^2 <= safety *
free_bytes` (`source = MEASURED`). The tile never drops below `MIN_DENSE_TILE_PX`;
when even that floor exceeds the budget the returned `TileBudget` has
`fits = False` and callers must refuse or warn loudly. A free-memory reading of
0 bytes (a failed, `UNKNOWN` reading) always gives `fits = False`. The estimate
is never below the largest measured `points` peak at or below the tile (nor
below 1 byte), so a fit with a negative `fixed_bytes` cannot plan a negative
peak. `load` refuses `bytes_per_px <= 0`, malformed `points`, and any
`source` other than `"measured"`.

No profile is committed here until P2.04 measures one.
