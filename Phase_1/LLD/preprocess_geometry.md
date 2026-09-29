# LLD — preprocess pipeline: step outcomes, pixel transforms, measured GSD (P1.09)

Closes: A010 (preprocess-2), A056 (ingest-13), A057 (preprocess-3), A058 (preprocess-4), A059 (preprocess-5), A060 (preprocess-7), A108 (preprocess-9), A055 (preprocess-13, geometry part). Files: `preprocess/pipeline.py`, `preprocess/resample.py`, `preprocess/georeference.py`, `constants.py`.

## 1. Step outcomes (A059)
```python
class StepStatus(str, Enum):
    RAN = "ran"
    SKIPPED_MISSING_INPUT = "skipped_missing_input"
    NOOP = "noop"                       # e.g. already at target GSD, CRSs already equal
    FAILED = "failed"                   # handler raised; detail = "<ExcType>: <msg>"
    DEGENERATE_OUTPUT = "degenerate_output"   # output has no finite / non-zero valid pixel, or a zero-size axis
```
`StepRecord` gains `status: StepStatus`; `ran` becomes a property `status is StepStatus.RAN`. Handlers return `(image, detail, status, reason)`; `run_pipeline` classifies exceptions as FAILED and checks every RAN output for degeneracy. `PreprocessResult` gains `status_counts -> dict[str, int]` and `failed -> bool` (any FAILED or DEGENERATE_OUTPUT).

## 2. Pixel transforms (A010)
`PreprocessResult` gains `pixel_transform: np.ndarray` — 3×3 float64 mapping **input pixel (x, y) → output pixel (x', y')**, the product of every geometric step that RAN (identity otherwise). Pixel-centre convention.
| step | matrix |
|---|---|
| resample (w,h) → (w',h') | `diag(w'/w, h'/h, 1)` with a half-pixel correction: `x' = (x + 0.5)·w'/w − 0.5` |
| georeference | `M = inv(dst_affine) @ src_affine` restricted to the 2-D affine part (both as 3×3), in pixel-centre convention; recorded only when both transforms are affine (rasterio `Affine`) |
Callers compose: a transform `T` found on preprocessed images maps back to input pixels as `inv(P_ref) @ T @ P_src`.

## 3. Measured GSD (A056, A057)
- `SensorSpec` gains `gsd_source: ValueSource` (all current entries `DOCUMENTED`: nominal values from the mission pages) and `gsd_note: str`. `LRO_NAC` note: "nominal EDR 0.5 m; the Vikram ortho is 1.0 m (label pixel_scale_x)".
- `_step_resample`: source GSD = `context.src_gsd_m`; when None and a sensor nominal exists, use it but set `detail["gsd_source"] = "nominal"` and log one warning; when both are None → `SKIPPED_MISSING_INPUT`.
- `PreprocessConfig` gains `side: str = "source"` (`"source" | "reference"`); on the reference side the resample step uses `context.ref_gsd_m` (falls back to the reference sensor's nominal with the same recording).

## 4. Guards (A058, A060)
- After band reduction, any step receiving `image.ndim != 2` → FAILED with reason `"input is <n>-D after band_reduction"`.
- `georeference(image, src_dataset, ref_dataset, resampling="cubic")`: FAILED when `image.shape[-2:] != (src.height, src.width)`; reprojects **onto the reference grid** (`dst_transform = ref.transform`, `dst_crs = ref.crs`, shape `(ref.height, ref.width)`), with `src_nodata`/`dst_nodata` from `src_dataset.nodata` (0 when None) and a float32 destination initialised to NaN; `GeoreferenceResult` gains `dst_transform` and `src_transform`.

## 5. Placeholders actually used (A108)
`PreprocessResult.uses_placeholders` = names of `PLACEHOLDER` params whose step RAN **and** whose value equals the placeholder's value in the config used (compare against `params.PARAMS_BY_NAME`).

## 6. Valid-mask plumbing (for C12)
`PreprocessContext` gains `valid: np.ndarray | None = None`. Every radiometric/shadow handler (`normalize`, `histogram_match`, `shadow`, `clahe`, `invert`, `dilate`, `log_transform`) passes `valid=context.valid` to the P1.08 functions; `histogram_match` also passes `reference_valid=context.reference_valid` (new field, default None). The resample handler resamples `context.valid` with nearest-neighbour to the new shape and stores it back into the context so later steps see the resampled mask.

## 7. Tests the prompt adds (`tests/test_preprocess_geometry.py`)
Resample 100×80 → 50×40: `pixel_transform` maps input centre (49.5, 39.5) to (24.5, 19.5); a 3-D cube with `band_reduction=False` → a FAILED record, not an exception; `side="reference"` uses `ref_gsd_m`; `context.valid` is honoured by `normalize` (zero border stays 0); nominal fallback recorded; an in-memory rasterio pair with different CRSs → georeference output shape equals the reference's and `pixel_transform` is not identity; a step raising → FAILED with the exception text; an all-zero output → DEGENERATE_OUTPUT.
