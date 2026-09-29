# LLD — planner (P3.03)

TBD 3.2 (descriptor carries the prior; the udocs/70 window-only design is insufficient, FABLE_NOTES §8). Uses C10, C11, C16, C19, C22.

```python
@dataclass(frozen=True)
class PlanInputs:
    run_id: str; pair_id: str
    source_path: str; reference_path: str               # repo-relative
    reference_georef: dict                              # C10 as_dict
    source_window: tuple[int, int, int, int]            # native px (row_off, col_off, height, width)
    reference_window: tuple[int, int, int, int]         # native px, search area
    prior_native: tuple[float, ...]                     # 9 floats: source-native px -> reference-native px
    source_native_gsd_m: float; reference_native_gsd_m: float
    matcher: str = "sift"; precision: str = "fp32"; preprocess: str = "none"; base_seed: int = 0

@dataclass
class PlanReport:
    jobs: list[JobDescriptor]
    skipped: list[tuple[int, str]]      # (tile_index, reason) — "outside_reference" | "does_not_fit"
    tile_px: int; working_gsd_m: float; est_vram_bytes: int
    def report(self) -> str

def plan_jobs(inputs: PlanInputs, *, tile_px: int = 512, overlap: float = 0.25,
              ref_margin_px: int = 32, profile: DeviceProfile | None = None,
              free_bytes: int | None = None) -> PlanReport
def plan_inputs_from_result(result: PairResult, *, run_id: str, source_label: str,
                            reference_label: str, reference_geo: GeoReference) -> PlanInputs
```
`plan_jobs`:
1. `working_gsd_m = reference_native_gsd_m` (G10); `f = working / source_native_gsd_m`.
2. Working source size `(round(w/f), round(h/f))` of the source window; `plan_tiles(h_w, w_w, tile_px, overlap)` (existing `ingest/tiling.py`).
3. Per tile: native source window = the tile mapped through the C11 pixel-centre `to_native` of the resize, expanded to integer bounds (floor/ceil) and offset by the source window; `prior_tile` = `translate(−ref_win_off) @ prior_native @ to_native_tile` (tile working px → job reference-window px) where `ref_win` = bounding box of the prior-mapped tile corners ± `ref_margin_px`, clipped to `reference_window`; empty → skipped `"outside_reference"`.
4. `est_vram_bytes`: `profile.plan_tile(matcher, precision, free_bytes)` entry → `fixed + k · tile_px²` when a profile is given, else `device.dense_matcher_peak_bytes(tile_px, precision)` for loftr, `0` for classical matchers. A job whose estimate exceeds `0.75 · free_bytes` (when `free_bytes` given) → skipped `"does_not_fit"`.
5. `JobDescriptor(run_id, pair_id, tile.index, source_path, reference_path, native source window, ref_win, prior_tile as 9 floats, working_gsd_m, source_native_gsd_m, reference_native_gsd_m, preprocess, matcher, precision, tile_px, est, base_seed, reference_georef)`.
Jobs are returned sorted by `tile_index`.

`plan_inputs_from_result`: requires the C04 crop-geometry keys (`crop_geometry_source == "recorded"`), `extra["gsd_m"]` and the source window keys; rebuilds `source_to_native` / `reference_to_native` with the C11 pixel-centre rule from the recorded windows and sizes, `prior_native = lift_to_native(result.transform, …)` (C19), `reference_window` = the recorded crop window in native px. Missing keys → `ValueError` listing them.
Tests (`tests/test_planner.py`): a synthetic `PlanInputs` (identity-like prior with scale 0.25) → jobs cover the source window (union of native windows ⊇ window), every job's prior maps its tile centre inside its reference window, job ids unique and stable across two calls, `does_not_fit` with a tiny `free_bytes`, `plan_inputs_from_result` on a PairResult carrying the recorded keys.
