# LLD — counts, refit threshold, classified stages (P0.09)

Produces: C02, C03 (Phase 0 fields). Closes: A006 (S2), A022 (align-1), A023 (eval-1), A024/A026 (S3), A025 (align-2), A027 (pr-10), A097 (match-19), A014 (match-9, pipeline side). Decision: G34.

## 1. `RunStatus`, `RunOutcome`, `PipelineConfig`
Exactly C02 and C03 (Phase 0 fields; `preprocess`, `device`, `precision` are **not** added in P0.09). `RunOutcome.extra` per C02.

## 2. `register_pair` stage table
Let `base = {source_id, reference_id, source_sensor, reference_sensor, matcher, model, **config.extra}`.
| # | stage | failure → status | `stage` value | extra added on failure | detail |
|---|---|---|---|---|---|
| 1 | build matcher + `match` | any exception → `MATCHER_ERROR` | `match` | — | `"<ExcType>: <msg>"` |
| 2 | `len(raw) < min_matches` | `TOO_FEW_MATCHES` | `match` | `n_raw_matches` | as today, plus `"; reason: <raw.meta['empty_reason']>"` when present |
| 3 | `estimate_transform(raw_copy, model, ransac_threshold_px, seed=config.seed)` | `ValueError` → `ESTIMATION_FAILED` | `estimate` | `n_raw_matches` | str(exc) |
| 4 | `n_ransac < min_inliers` | `TOO_FEW_INLIERS` | `estimate` | `n_raw_matches`, `n_ransac_inliers` | `"RANSAC kept <k> of <n> matches"` |
| 5 | `refine_full(first_pass_inliers..., threshold_px=config.refit_threshold_px, seed=config.seed, ecc_kwargs={prefilter, nodata, max_shift_px=config.ecc_max_shift_px, source_valid, reference_valid})` | any exception → `REFINEMENT_FAILED` | `refine` | + counts | `"<ExcType>: <msg>"` |
| 6 | `n_refit < min_inliers` | `TOO_FEW_INLIERS` | `refine` | + `n_refit_inliers` | `"after refit: <k> of <n_ransac> first-pass inliers at <thr> px"` |
| 7 | metrics, uniformity, conditioning | any exception → `EVAL_FAILED` | `eval` | + counts | `"<ExcType>: <msg>"` |
| 8 | OK | — | `done` | all counts | — |
Test seam: keep the stage functions (`estimate_transform`, `refine_full`, `choose_ecc_prefilter`, `compute_metrics`, `compute_uniformity`, `bootstrap_conditioning`) imported **inside** `register_pair` as today; the harness monkeypatches them as module attributes.
`raw_copy`: `estimate_transform` sets `inlier_mask` in place, so keep `raw` itself untouched by passing a shallow copy (`MatchResult(raw.src_pts, raw.dst_pts, raw.scores, raw.matcher, None, dict(raw.meta))`).

## 3. Masks over the raw set (G34)
- `ransac_mask` = mask returned by the first fit (length N_raw).
- `refit_mask` (length N_raw) = False everywhere, then at the indices of `ransac_mask` set to the refit's mask (refit runs on `raw.inliers()`, whose rows are the True rows of `ransac_mask` in order).
- `PairResult(src_pts=raw.src_pts, dst_pts=raw.dst_pts, inlier_mask=refit_mask, ...)`. P0.10 adds `ransac_mask=` and `pre_ecc_transform=` to this call.
- `metrics = compute_metrics(MatchResult(raw pts, inlier_mask=refit_mask), transform, gsd_m, ransac_mask=ransac_mask).as_dict()`.
- uniformity and conditioning use the refit inliers (unchanged semantics).

## 4. `eval/metrics.py`
```python
@dataclass
class RegistrationMetrics:
    n_matches: int            # raw
    n_ransac_inliers: int | None
    n_inliers: int            # final (refit)
    inlier_ratio: float       # n_inliers / n_matches
    ransac_inlier_ratio: float | None
    rmse_px: float; mae_px: float; median_px: float; p95_px: float; max_px: float
    model: str; matcher: str
    rmse_m: float | None = None
    residual_basis: str = "self_residual"    # "self_residual" | "truth"
    @property
    def self_residual_subpixel(self) -> bool   # rmse_px < 1 and p95_px < 1
    def as_dict(self) -> dict                  # asdict + {"self_residual_subpixel": ...}; no "is_subpixel" key
def compute_metrics(result, transform, gsd_m=None, ransac_mask=None,
                    residual_basis="self_residual") -> RegistrationMetrics
```
`n_inliers` = `int(result.inlier_mask.sum())` when a mask is set, else `transform.n_inliers`. Residuals over `result.inliers()`. `is_subpixel` is removed; update `tests/test_eval.py:54` and `tests/test_results_and_pipeline.py:47,76-77` to the new name (allowed by the file fence). README wording at `README.md:610-611` is P1.22.

## 5. `extra` written by `register_pair` on OK
Existing keys (`ecc_prefilter`, sun keys) plus: `refit_threshold_px`, `ransac_threshold_px`, `min_inliers`, `model`, `seed`, `refine_stages` (`"+".join(stages)`), `ecc_status`, `ecc_motion`, `ecc_cc`, `ecc_shift_px`, `cv2_version`, `numpy_version`, and `matcher_<k>` for every scalar `raw.meta[k]` (str, int, float, bool; others skipped).

## 6. Empty-result reasons (A097)
`ClassicalMatcher.match` returns `MatchResult.empty(name)` with `meta` = C-classical meta (P0.02) + `{"empty_reason": "too_few_keypoints" | "no_ratio_survivors", "n_keypoints_src": int, "n_keypoints_ref": int}`. `RIFT2Matcher.match` does the same at its two empty returns (`rift2/matcher.py:181-185`, `:200-201`) with the same reason strings.

## 7. Tests the prompt adds (`tests/test_pipeline_counts.py`)
| test | asserts |
|---|---|
| injected outliers | synthetic pair, matcher stub returning 60 exact + 40 random correspondences: `n_matches == 100`, `n_ransac_inliers >= 60`, `n_inliers <= n_ransac_inliers`, `inlier_ratio == n_inliers / 100` |
| refit threshold used | monkeypatch `refine_full` to record `threshold_px`; equals `config.refit_threshold_px` |
| refine raises | monkeypatch `refine_full` to raise `ValueError` → `REFINEMENT_FAILED`, stage `refine` |
| after-refit gate | monkeypatch refit to keep 3 inliers with `min_inliers=8` → `TOO_FEW_INLIERS`, detail starts `"after refit"` |
| eval raises | monkeypatch `compute_uniformity` to raise → `EVAL_FAILED` |
| empty reason | blank images with sift → detail contains `too_few_keypoints` |
Matcher stub: monkeypatch `lunar_reg.pipeline._build_matcher` to return an object with `name` and `match()`.
