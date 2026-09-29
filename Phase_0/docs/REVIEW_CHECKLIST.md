# Phase 0 — review checklist (human)

Terms: see `OVERVIEW.md`. Diff range: `git diff phase-base-approved..phase-0` (G07).

## Gate items (all must be yes)
- [ ] `Phase_0/REVIEW_PACK_0.md` exists and its `verify.sh` section shows exit code 0.
- [ ] `Phase_0/benchmark/score.json` has `"pass": true`; every skip reason in `skips.reasons` is an absent resource (GPU, weights, data), not a code problem.
- [ ] `git diff phase-base-approved..phase-0 -- Phase_0/harness Phase_0/benchmark` shows only `benchmark/score.json` and `benchmark/out/**`.
- [ ] One commit per prompt, messages `P0.<jj>: <title>`, in INDEX order.
- [ ] `Phase_0/QUESTIONS.md`: every entry answered or explicitly deferred by you.

## Spot checks (15 minutes)
- [ ] Open `src/lunar_reg/align/refine.py`: the ECC call still passes the **reference** as the first image and the **source** as the second (REVIEW_FOCUS #1).
- [ ] Open one test in `tests/test_pipeline_counts.py`: the raw count (e.g. 100) is larger than the inlier count, i.e. the inlier ratio is no longer ≈ 1.0.
- [ ] `src/lunar_reg/match/loftr.py` and `src/lunar_reg/ingest/footprint.py` are gone; `configs/default.yaml` is gone.
- [ ] `scripts/ci.sh` runs to completion on your machine: `bash scripts/ci.sh`.
- [ ] No doc gained a number without a run-artefact path next to it (`git diff phase-base-approved..phase-0 -- '*.md'`).

## Questions to send to the external reviewers
1. Is the affine ECC conversion (2×3 ↔ 3×3, inverse, back) correct? (`refine.py`)
2. Is the raw → RANSAC → refit mask bookkeeping correct? (`pipeline.py`)
3. Does anything still write a stored number from a default rather than a measurement? (`run_vikram.py`, `results.py`)
