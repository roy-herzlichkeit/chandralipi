# LLD — cross-matcher agreement (P1.12)

Produces: C14. TBD 1.8 step 5. Context: real pairs have no ground truth; the only independent signals are pre-ECC cross-matcher agreement and bootstrap conditioning (FABLE_NOTES §4.6). ECC pulls every matcher to the same solution (TBD 1.8, MEASURED 0.0 m apart), so agreement must be measured on the **pre-ECC** transforms (`PairResult.pre_ecc_transform`, C04).

## 1. `eval/agreement.py` (new, C14)
- Probes: `(0, 0), (w−1, 0), (0, h−1), (w−1, h−1), ((w−1)/2, (h−1)/2)` in source pixels, `shape = (h, w)`.
- Each transform: 3×3 applied projectively, 2×3 affinely (reuse `align.estimate.Transform.apply` by wrapping the matrix with a dummy model string chosen from its shape).
- `pairwise_px["a|b"]` (names sorted, joined by `|`) = max over probes of the Euclidean distance between the two mapped probes.
- `max_disagreement_px` = max over pairs; NaN when fewer than 2 transforms. `passes = n_matchers ≥ 2 and max_disagreement_px ≤ threshold_px`.
- `max_disagreement_m = max_disagreement_px · gsd_m` when `gsd_m` is given.
- A transform with a non-finite entry or a singular 3×3 is skipped with one warning naming the matcher; it is not in `matchers` and does not count toward `n_matchers`.

## 2. Store helper
```python
def agreement_for_stored(results: list[PairResult], threshold_px: float = 1.0) -> AgreementResult
```
Uses each result's `pre_ecc_transform` (results where it is None — v1 records — are skipped), `matcher` as the name, shape = `source_image.shape[:2]` divided by `extra.get("source_scale", 1.0)` (thumbnail scale set by the C04 loader) and rounded, and `gsd_m = extra.get("gsd_m")`. All results must share `source_id` and `reference_id` (ValueError otherwise).

## 3. Tests the prompt adds (`tests/test_agreement.py`)
Identical transforms → 0.0 and passes; translation offset of 0.6 px between two → 0.6 and passes; 1.5 px → fails; one transform only → NaN, fails; affine vs homography of the same affine → 0.0; `gsd_m=4` → metres = px × 4; singular transform skipped.
