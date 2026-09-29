# LLD — run_vikram numeric crop geometry (P0.11)

Closes: A034 (pr-5), A035 (pr-6), A036 (pr-20, run_vikram part), A037 (tooling-3), and the run_vikram half of A027 (pr-10: incremental save, None sun formatting).
Only `scripts/run_vikram.py` changes. The module stays a script; tests import it with `importlib.util.spec_from_file_location("run_vikram", "scripts/run_vikram.py")`.

## 1. Record the crop geometry at run time
`prepare_pair(...)` keeps its signature and return tuple. Its `geo` dict gains:
| key | value |
|---|---|
| `c0`, `r0` | int NAC px (unchanged) |
| `ref_factor` | float (unchanged) |
| `shift_e_m`, `shift_s_m` | float, the `shift_px` passed in (NAC px = 1 m) |
| `src_win_l0`, `src_win_s0`, `src_win_lines`, `src_win_samples` | ints of the OHRC window |
In `main`, after an OK outcome, `r.extra.update(geometry_extra(geo, gsd))` where the new module function
```python
def geometry_extra(geo: dict, gsd_m: float) -> dict:
    return {"ref_crop_c0": int(geo["c0"]), "ref_crop_r0": int(geo["r0"]), "ref_factor": float(geo["ref_factor"]),
            "shift_e_m": float(geo["shift_e_m"]), "shift_s_m": float(geo["shift_s_m"]),
            "src_win_l0": ..., "src_win_s0": ..., "src_win_lines": ..., "src_win_samples": ...,
            "gsd_m": float(gsd_m), "crop_geometry_source": "recorded"}
```
The coarse-pass note keeps its text but the shift is formatted `+.3f` (not `+.0f`).

## 2. Export classification
```python
class ExportStatus(str, Enum):
    EXPORTED = "exported"
    RECORDED_GEOMETRY_MISSING = "recorded_geometry_missing"   # no ref_crop_c0/r0 and no parsable legacy note
    SETTINGS_UNRECORDED = "settings_unrecorded"               # window_m or margin_m or gsd_m absent
    INPUT_MISSING = "input_missing"                           # OHRC label or NAC label not on disk
    WRITE_FAILED = "write_failed"
```
`export_stored(only="")` per stored OHRC result:
1. Required settings: `window_m`, `margin_m`, and `gsd_m` must all be in `extra`; any missing → `SETTINGS_UNRECORDED` (no default numbers, no back-derived gsd).
2. Crop origin: if `ref_crop_c0` and `ref_crop_r0` are in `extra` → `prepare_pair` is still called to read the source window (with shift `(shift_e_m, shift_s_m)` from `extra`), but the GeoTIFF origin uses the recorded `ref_crop_c0`/`ref_crop_r0`, and the tag `crop_geometry_source = "recorded"`. Else call `_stored_shift(extra)`; it now returns `None` when neither regex matches (instead of `(0, 0)`) → `RECORDED_GEOMETRY_MISSING`; on a match, rebuild the crop with `prepare_pair` and mark the GeoTIFF tag `crop_geometry_source = "regex_legacy"`.
3. GeoTIFF tags: `model` and `min_inliers` come from `extra`; when absent the tag value is the string `"unrecorded"`.
4. Print one line per status with count and first pair_id sample on every run; return 0 when every result is EXPORTED, else 1.

Test seam: keep `load_index`, `load_pair` and `save_registered_geotiff` imported **inside** `export_stored`, and keep `import glob` / `glob.glob` and `rasterio.open` as they are; the harness monkeypatches them.

## 3. Robustness in `main` (pr-10 run_vikram half)
- Save each OK result immediately: `save_results([r], RESULTS_ROOT, overwrite=args.overwrite)` inside the matcher loop (one call per result), so an exception later loses nothing already computed. New flag `--overwrite` (default off). A `FileExistsError` is caught, the pair is listed as `NOT saved (exists; pass --overwrite): <pair_id>`, and the count of such pairs is printed in the final summary. Collect every `RunOutcome` (OK and failed) in a `BatchReport`; after the loop call `save_failures(report.failures, RESULTS_ROOT)` and print `report.report()`.
- Sun formatting: `fmt = lambda v: "n/a" if v is None else f"{v:.1f}"` for the per-strip line.
- Exit code: 1 when no run succeeded, else 0 (A111 is P1.16; this prompt only avoids the crash).

## 4. Tests the prompt adds (`tests/test_run_vikram_geometry.py`)
| test | asserts |
|---|---|
| `_stored_shift` legacy note | `"8 m/px LightGlue, 106 inliers, shift +556,-2888 m (E,S)"` → `(556.0, -2888.0)`; `"prior shift 556,-2888 m (E,S)"` → same; `"coarse pass failed"` → `None` |
| `geometry_extra` | keys exactly the C04 crop-geometry keys; types float/int as C04 |
| export classification | monkeypatched store with three results (recorded geometry, legacy note, nothing) → statuses EXPORTED / EXPORTED(regex_legacy) / RECORDED_GEOMETRY_MISSING, with `save_registered_geotiff` monkeypatched to a stub |
| settings unrecorded | result without `margin_m` → SETTINGS_UNRECORDED |
