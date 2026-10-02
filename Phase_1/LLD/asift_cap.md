# LLD — keypoint cap for brute-force matching (P1.25)

Closes: Q-P1.18-3 (human decision 2026-10-02: cap ASIFT keypoints before P1.19). Decision: G42.
Evidence tags: **M** = measured by the architect, 2026-10-02 · **I** = inference.

## 0. Facts
- ASIFT (`cv2.AffineFeature` around SIFT) runs SIFT on many simulated affine views. The `nfeatures` limit applies per view, so the total keypoint count is not bounded by `max_features`.
- On the anchor pair, every ASIFT run ended in `matcher_error` with the OpenCV assertion `trainDescCollection[iIdx].rows < IMGIDX_ONE` (Q-P1.18-3, `data/processed/ablation/ablation.json`). The pair was 750 × 750 source and 1330 × 1343 reference, at 4 m/px.
- `cv2.BFMatcher(NORM_L2).knnMatch(query, train, k=2)` in opencv 4.14.0 succeeds with 262 143 train rows and fails with 262 144 rows with that same assertion (M).
- Cost: 30 000 × 30 000 float descriptors take 1.8 s for one knnMatch direction on this laptop (24 OpenCV threads) (M). 50 000 per side therefore costs about 5 s per direction (I, n² scaling). With the cross-check there are two directions.

## 1. `src/lunar_reg/match/classical.py`
1. Add module constants:
   - `BF_TRAIN_LIMIT = 262_143` with `BF_TRAIN_LIMIT_SOURCE = ValueSource.MEASURED` and a comment citing opencv 4.14.0 and this LLD.
   - `ASIFT_MAX_TOTAL_KEYPOINTS = 50_000` with `ASIFT_MAX_TOTAL_KEYPOINTS_SOURCE = ValueSource.INFERRED` and a comment: "chosen bound, ≈ 5 s per match direction".
2. `DetectorInfo` gains `max_total_keypoints: int | None = None`, appended last. `DETECTOR_INFO["asift"]` sets it to `ASIFT_MAX_TOTAL_KEYPOINTS`; every other detector keeps `None`.
3. `ClassicalMatcher.__init__` gains `max_total_keypoints: int | None = None`, appended last.
   - The effective cap is `self.max_total_keypoints = min(max_total_keypoints or self.info.max_total_keypoints or BF_TRAIN_LIMIT, BF_TRAIN_LIMIT)`.
   - An explicit value `> BF_TRAIN_LIMIT` or `< 2` → `ValueError` (programmer error).
4. New method `_cap(self, keypoints, descriptors) -> tuple[list, np.ndarray | None, int, bool]`:
   - Returns the kept keypoints, the kept descriptors, the raw count, and whether it capped.
   - When `len(keypoints) > self.max_total_keypoints`, keep the strongest: `order = np.argsort(-np.array([k.response for k in keypoints]), kind="stable")[:cap]`, then `np.sort(order)`. The sort keeps the original relative order, so the result is deterministic.
   - Otherwise return the inputs unchanged.
5. `match`: apply `_cap` to both images right after `detect`, before any check or matching. Every returned `MatchResult.meta`, empty or not, gains:
   - `max_total_keypoints`
   - `n_keypoints_src_raw`, `n_keypoints_ref_raw`
   - `keypoints_capped_src`, `keypoints_capped_ref`

   `_meta()` also includes `max_total_keypoints`. `n_keypoints` keeps meaning the counts actually matched.
6. Detectors that never exceed their cap give results identical to today's. Only the cap check is added; no other code path changes.
7. Update the `DETECTOR_INFO["asift"]` note with one sentence: "Total keypoints capped (strongest by response) because BFMatcher rejects ≥ 262 144 train rows (P1.25)."

## 2. Tests the prompt adds (`tests/test_classical_cap.py`)
| test | asserts |
|---|---|
| a fake detector returning 270 000 keypoints + random float32 descriptors, `max_total_keypoints=1000` | `match` does not raise; `meta["keypoints_capped_src"]` and `meta["keypoints_capped_ref"]` are True; the raw counts are 270 000 |
| `_cap` determinism | the same input twice gives identical kept indices; the kept set has the highest responses; original order is preserved |
| defaults | `ClassicalMatcher("asift").max_total_keypoints == 50_000`; `ClassicalMatcher("sift").max_total_keypoints == BF_TRAIN_LIMIT` |
| validation | `max_total_keypoints=262_144` and `=1` raise `ValueError` |
| unchanged below the cap | SIFT on a 256 × 256 synthetic pair gives matches identical to a matcher built with `max_total_keypoints=None` |
