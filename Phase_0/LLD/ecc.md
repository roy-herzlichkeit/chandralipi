# LLD — ECC model fidelity, no mutation, displacement gate, validity mask (P0.08)

Produces: C07. Closes: A005 (S1), A018 (align-3), A019 (align-4), A020 (align-5). Decision: G35.
**Invariant (FABLE_NOTES §4.5, `refine.py:255-267`): template = reference, input = source, initial warp = inverse of src→ref, result inverted. Do not rearrange.**

## 1. Motion per model
| `transform.model` | ECC motion | warp shape passed to `cv2.findTransformECC` | output matrix |
|---|---|---|---|
| `homography` | `cv2.MOTION_HOMOGRAPHY` | 3×3 float32 = `inv(H)` normalised by `[2,2]` | `inv(warp)` normalised, 3×3 |
| `affine` | `cv2.MOTION_AFFINE` | 2×3 float32 = top two rows of `inv(A3)` where `A3` is the affine as 3×3 | top two rows of `inv(warp as 3×3)`, 2×3 |
| `partial_affine` | none | — | input unchanged, status `SKIPPED_NO_SIMILARITY_MOTION` |

## 2. `ecc_refine` (new, C07) — algorithm
1. `prefilter` handling unchanged (`"auto"`, `"local_contrast"`, `"none"`), applied to **copies**.
2. `src = np.array(source, dtype=np.float32, copy=True)`, same for `ref`; divide each by 255 when its max > 1. Caller arrays are never written.
3. Validity mask (only when `nodata` is not None): `valid = source != nodata`, eroded with a square kernel of side `gaussian_blur + 2` (cv2.erode, uint8 0/255), passed as `inputMask`. With `nodata is None` pass `None`.
4. Singular input (`np.linalg.LinAlgError` on inversion) → `SKIPPED_SINGULAR`, return input transform, `cc = nan`.
5. `cv2.error` from `findTransformECC` → `NOT_CONVERGED`, input transform, `cc = nan`, `detail` = first line of the error.
6. Displacement gate: probes = 5×5 grid over the source image (`linspace(0, w-1, 5) × linspace(0, h-1, 5)`); `shift_px = max ‖T_ecc(p) − T_in(p)‖` in reference px. `shift_px > max_shift_px` → `REJECTED_DISPLACEMENT`, input transform returned, `cc = nan`, `shift_px` recorded, `detail = f"displacement {shift_px:.3f} px > gate {max_shift_px} px"`.
7. Otherwise `APPLIED`, refined `Transform(matrix, model=transform.model, n_inliers, n_total, estimator=transform.estimator, seed=transform.seed)`, `cc` finite.
`refine_transform_ecc(...)` becomes a wrapper with its current positional parameters plus `nodata=None, max_shift_px=3.0`, returning `(outcome.transform, outcome.cc)`.

`ECC_MAX_SHIFT_PX` constant as in C07 (a `Sourced`), used as the default via `ECC_MAX_SHIFT_PX.value`.

## 3. `refine_full`
Signature per C07 (adds `seed: int = 0`, passed to `reestimate_on_inliers` → `estimate_transform(seed=seed)`). `reestimate_on_inliers(result, model, threshold_px, seed=0)` gains the same keyword.
`ecc_kwargs` may contain `prefilter`, `nodata`, `max_shift_px`, `max_iterations`, `epsilon`, `gaussian_blur`.
Detail keys exactly as C07. When `use_ecc` is False or an image is None → `ecc_status = "skipped_disabled"`. Keep the existing `"ecc_skipped"` key out (replaced by `ecc_status`).

## 4. Docstring fixes (A102 part in this file)
`refine.py` heading "The prefilter, and why it defaults on" → "The prefilter, and why it is off by default". `ECC_PREFILTER_SIGMA`, `ECC_SAME_ILLUMINATION_NCC` and `choose_ecc_prefilter`'s `azimuth_threshold_deg` keep their values; wrap the two module constants as `Sourced` **only if** no caller does arithmetic on them — otherwise leave them and add a sibling `ECC_PREFILTER_SIGMA_SOURCE = ValueSource.INFERRED` (and `ECC_SAME_ILLUMINATION_NCC_SOURCE = ValueSource.MEASURED`, synthetic-only per its comment). Choose the sibling form (callers do arithmetic).

## 5. Tests the prompt adds (`tests/test_ecc_fidelity.py`)
| test | asserts |
|---|---|
| affine in, affine out | 2×3 output, `motion == "affine"`, `model == "affine"`, probe error vs truth < 0.1 px starting from a 0.6 px perturbation |
| homography regression | 3×3, APPLIED, error < 0.1 px |
| partial_affine | `SKIPPED_NO_SIMILARITY_MOTION`, matrix identical to input |
| no mutation | float32 and uint8 inputs byte-identical after the call |
| gate | monkeypatch `cv2.findTransformECC` to return a warp shifted by 10 px → `REJECTED_DISPLACEMENT`, input returned |
| nodata mask | with a 40 px zero border on source and `nodata=0`, APPLIED and error < 0.2 px |
| refine_full keys | all C07 detail keys present |
