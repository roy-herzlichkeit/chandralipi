# LLD — evaluation correctness (P0.12)

Closes: A038 (eval-2), A039 (eval-3), A040 (eval-4), A041 (eval-5, G33), A042 (preprocess-6), A100 (eval-6), A101 (eval-8), A102 (eval-9, eval side), A021 (eval-10, P0.12 part).

## 1. `error_budget.ErrorBudget.dominant` (A038)
```
dist = get("transform: distribution only"); fit = get("transform: RANSAC fit")
if dist is None or fit is None or fit <= 0: return None
corr = sqrt(max(fit**2 - dist**2, 0))
if corr == 0 and dist == 0: return None
larger, smaller = max(dist, corr), min(dist, corr)
if smaller > 0 and larger / smaller <= 1.25: return None          # the 20 % not-resolved band
return "point distribution" if dist > corr else "correspondence error"
```
Add `ErrorBudget.shares -> dict[str, float | None]` returning `{"distribution_px": dist, "correspondence_px": corr}` and print both in `report()`.

## 2. One bootstrap core (A039, A040)
New private function in `conditioning.py`:
```python
def _bootstrap_predictions(src_pts, dst_pts, probes, model, n_bootstrap, seed) -> tuple[np.ndarray, int]:
    """(n_ok, n_probes, 2) predictions and the number of failed refits."""
```
- Resampling: `rng = np.random.default_rng(seed)`, draws with replacement of size N each round.
- Fit: least squares for every model. homography → `cv2.findHomography(src, dst, method=0)`; affine → `np.linalg.lstsq` on `[x y 1]` for x' and y' separately; partial_affine → `np.linalg.lstsq` on the 4-parameter similarity system `[x -y 1 0; y x 0 1]`. A fit returning None, raising `cv2.error` / `LinAlgError`, or non-finite → counted as failed.
- Minimum points: `estimate._MIN_POINTS[model]` (import it; delete the duplicated literal dict at `conditioning.py:161`).
- `bootstrap_conditioning` and `conditioning_map` both call it. `conditioning_map` keeps its signature, supports all three models, and uses the **max** deviation per probe (same statistic as the headline). It returns `(map, n_failed)` **only** through a new function `conditioning_map_with_failures`; `conditioning_map` itself keeps returning the array (callers unchanged) and logs one warning line when `n_failed > 0`.
- `ConditioningMetrics` gains `estimator: str = "lsq"`.

## 3. Uniformity normalisation (A041, A100, G33)
In `compute_uniformity(pts, shape, grid=8)`:
- Out-of-frame points (x < 0, y < 0, x ≥ w, y ≥ h) are excluded from binning and counted in `n_out_of_frame`.
- `k = min(n_in_frame, grid*grid)`; `coverage = occupied / k` (0 when k = 0); `entropy = H / log(k)` when k > 1, else 1.0 when k == 1, 0.0 when k == 0.
- `UniformityMetrics` gains `n_out_of_frame: int = 0` and `max_occupiable_cells: int = 0` (appended fields).
- `cell_counts` and `enforce_uniformity` share one binning helper `_bin(pts, shape, grid) -> (row, col, in_frame_mask)`; `cell_counts` drops out-of-frame points instead of clipping them into border cells.

## 4. Oracle fit uses the pipeline model (A101)
`attribute_error`'s "transform: distribution only" stage fits with the same `model` argument via the §2 least-squares fitter, its minimum point count is `estimate._MIN_POINTS[model]`, and its `StageError.note` is exactly `f"oracle fit: {model} least squares"`.

## 5. `preprocessing_sweep` chains (A042)
`_normalize(image, _other) = to_uint8(normalize_intensity(image))`; `_shadow(image, _other) = to_uint8(normalize_shadows(image))`. No other chain changes.

## 6. Gate provenance (A102)
| constant | sibling constant added |
|---|---|
| `conditioning.EXTRAPOLATION_GATE_PX = 1.0` | `EXTRAPOLATION_GATE_SOURCE = ValueSource.INFERRED` (calibrated on synthetic layouts only) |
| `uniformity.UNIFORMITY_GATE = 0.7` | `UNIFORMITY_GATE_SOURCE = ValueSource.INFERRED` |
| `uniformity.CLUSTERED_R = 0.25` | `CLUSTERED_R_SOURCE = ValueSource.INFERRED` |
`ConditioningMetrics.as_dict()` adds `"gate_source": EXTRAPOLATION_GATE_SOURCE.value`; `UniformityMetrics.as_dict()` adds `"gate_source": UNIFORMITY_GATE_SOURCE.value`. Fix the contradictory blob-case numbers in the `uniformity.py` docstring by deleting the unsourced one (`R=0.101` vs `R 0.20`: keep neither number; write "see tests/test_eval.py for the measured values").

## 7. Tests the prompt adds (`tests/test_eval_fixes.py`)
dominant: three regimes (dist 0.35/fit 0.40 → corr 0.194 → "point distribution"; dist 0.10/fit 1.00 → corr 0.995 → "correspondence error"; dist 0.30/fit 0.40 → corr 0.265, ratio 1.13 → None); `conditioning_map(..., model="partial_affine")` runs, and for every model `conditioning_map(...).max()` equals `bootstrap_conditioning(...).max_px` within 1e-9 (same seed, same probe grid); 20 points one per cell in a 8×8 grid → coverage 1.0 and score ≥ 0.99; out-of-frame points counted, not binned; oracle fit with `model="affine"` yields a 2×3-compatible stage.
