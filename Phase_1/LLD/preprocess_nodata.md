# LLD — nodata-aware radiometric and shadow steps (P1.08)

Closes: A054 (preprocess-1), A107 (preprocess-12), A055 (preprocess-13, radiometric part). Files: `preprocess/radiometric.py`, `preprocess/shadow.py`.

## 1. Convention
`valid: np.ndarray | None` — bool mask, True = real data. Every function below gains the keyword `valid=None`. When `valid is None` the function behaves **exactly** as today (existing tests and the P0.02 `_to_tensor` path are unchanged). When given:
- statistics (percentiles, means, histograms, CDFs) use `image[valid]` only;
- output pixels where `~valid` are 0 for uint8 outputs and `np.nan` for float outputs;
- a mask with no True pixel → return all-zero (uint8) / all-NaN (float) and log one warning.

## 2. Function table
| function | change when `valid` is given |
|---|---|
| `to_uint8(image, percentiles=(1, 99), valid=None)` | percentiles over valid pixels; valid pixels mapped into **1…255** (0 reserved for nodata), invalid → 0. Same formula as `scripts/run_vikram.stretch_u8`: `clip((x − lo) / max(hi − lo, 1e-6) · 254 + 1, 1, 255)`. |
| `apply_clahe(image, clip_limit, grid_size, valid=None)` | run CLAHE on the uint8 image (`to_uint8(image, valid=valid)` first when not uint8); afterwards set `~valid` to 0 and clip valid pixels to ≥ 1 |
| `normalize_intensity(image, valid=None)` | z-score over valid; invalid → NaN |
| `suppress_shadows(image, percentile, valid=None)` | shadow mask computed over valid pixels only (`shadow.shadow_mask(image, percentile, valid)`); replacement median over valid non-shadow pixels; invalid → NaN |
| `invert(image, valid=None)` | valid: `256 − x` for uint8 input (1…255 → 255…1); invalid stay 0 |
| `dilate(image, kernel_size, shape, valid=None)` | dilate, then set `~valid` back to 0 |
| `log_transform(image, scale=None, valid=None)` | scale from valid pixels; invalid → 0 |
| `match_histogram(source, reference, valid=None, reference_valid=None)` | both CDFs from valid pixels only; LUT applied to valid source pixels; invalid → 0 |
| `standard_chain(image, clahe=True, suppress_shadow=True, shadow_percentile=5.0, valid=None)` | passes `valid` through every call |
| `shadow.shadow_mask(image, percentile=5.0, valid=None)` | percentile over valid finite pixels; result False where `~valid` |
| `shadow.shadow_fraction(image, percentile, valid=None)` | fraction over valid pixels |
| `shadow.estimate_shadow_severity(image, dark_level=0.15, valid=None)` | over valid pixels |
| `shadow.normalize_shadows(image, method, percentile, gamma, sigma=25.0, valid=None)` | every method honours `valid`; float output NaN at invalid |
| `shadow._retinex` (A107) | fill NaN and invalid pixels with the median of valid finite pixels before blurring; restore NaN at those pixels afterwards |

## 3. Tests the prompt adds (`tests/test_preprocess_nodata.py`)
For every function in §2: an image with a zero border and `valid = image > 0` → output is 0 (or NaN) exactly on the border and the valid-region output equals the same function run on the valid pixels alone (for pointwise functions) or is computed from valid-only statistics (check `to_uint8`'s lo/hi against `np.percentile(image[valid], (1, 99))`). `_retinex` on an image containing NaN returns finite values off the NaN pixels. `valid=None` reproduces today's output byte for byte on a fixed random image (compare against a call made with the pre-change behaviour captured as a constant array in the test from `np.random.default_rng(0)` input — compute it by running the function before editing and pasting the resulting hash `hashlib.sha256(out.tobytes()).hexdigest()` into the test).
