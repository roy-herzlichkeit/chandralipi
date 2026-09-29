# LLD — pooled multi-matcher consensus (P1B.03)

Produces: C21 `pooled_consensus`, `ConsensusStatus`, `ConsensusResult`. TBD 1.8 steps 4–5.

## 1. `pooled_consensus(results, shape, *, model, threshold_px, agreement_threshold_px, min_matchers, seed)`
1. Per matcher `m` with `len(results[m]) ≥ estimate._MIN_POINTS[model] + 1`: `estimate_transform(copy, model, threshold_px, seed=seed)`; `ValueError` → `per_matcher[m] = None`.
2. OK matchers < `min_matchers` → `TOO_FEW_MATCHERS` (transform None).
3. Probes: the C14 probe set on `shape`. Per probe, the median over OK matchers of the mapped position; a matcher **contributes** when its max probe distance to that median ≤ `agreement_threshold_px`.
4. Contributors < `min_matchers` → `DISAGREEMENT`; `agreement` = C14 result over all OK matchers; transform None.
5. Pooled set = concatenation of each contributor's RANSAC inliers (source order = sorted matcher name, then point index); `estimate_transform(pooled, model, threshold_px, seed=seed)` → failure → `ESTIMATION_FAILED`; then `reestimate_on_inliers(threshold_px=1.0, seed=seed)`.
6. `OK` with `transform`, `pooled` (the pooled `MatchResult` with its inlier mask), `agreement` over contributors, `contributing` sorted, `detail` naming excluded matchers and their distances.

## 2. `register_consensus(source, reference, pair_id, matchers, config, *, source_valid=None, reference_valid=None, **ids) -> RunOutcome`
Runs every matcher via `match.build_matcher(name, device=config.device)` (each failure classified per matcher and kept in `extra["consensus_<name>_status"]`), calls `pooled_consensus`, then (OK only) ECC via `refine_full`-equivalent: `ecc_refine(transform, source, reference, prefilter=config.ecc_prefilter, nodata=0 if valid masks given else config.nodata, max_shift_px=config.ecc_max_shift_px)`; metrics/uniformity/conditioning exactly as `register_pair` does on the pooled inliers; `PairResult.matcher = "consensus(" + "+".join(contributing) + ")"`; `extra` adds `consensus_status`, `consensus_contributing`, `consensus_agreement_px`, `consensus_excluded`. Non-OK consensus → `RunOutcome` with `RunStatus.TOO_FEW_MATCHES` (TOO_FEW_MATCHERS), `ESTIMATION_FAILED` (DISAGREEMENT or ESTIMATION_FAILED), detail = consensus detail, `extra["consensus_status"]` = the C21 value.

## 3. Tests (`tests/test_consensus.py`)
Three synthetic matchers agreeing (same homography + noise) → OK, 3 contributors, pooled fit within 0.2 px of truth; one matcher offset by 5 px → excluded, 2 contribute, OK; two of three offset in different directions → DISAGREEMENT; one OK matcher → TOO_FEW_MATCHERS; `register_consensus` with stub matchers returns a `PairResult` whose `matcher` starts with `consensus(`.
