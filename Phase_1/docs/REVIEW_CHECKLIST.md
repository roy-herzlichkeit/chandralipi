# Phase 1 — review checklist (human)

Diff range: `git diff phase-0-approved..phase-1` (G07). Terms: `OVERVIEW.md`.

## Gate items
- [ ] `Phase_1/REVIEW_PACK_1.md`: `verify.sh` exit 0.
- [ ] `Phase_1/benchmark/score.json`: read every axis; for a failing `quality` part, the reason is in `docs/VIKRAM_2023_DIAGNOSIS.md` or the run records, not a code defect.
- [ ] `data/processed/vikram/exp1_gate.json` decision noted: ______ (BUILD_1B → Phase 1B runs after Phase 2).
- [ ] `data/processed/results_archive_20260929/` exists (old results kept, G08).
- [ ] Harness/benchmark unchanged since `phase-0-approved` except `score.json` / `out/`.
- [ ] `Phase_1/QUESTIONS.md`: each entry answered or deferred (TMC-2/IIRS probe entries are expected if those products were not downloaded).

## Spot checks
- [ ] Open the dashboard (`scripts/run_dashboard.sh`): the anchor strip shows its matches on the right pixels (thumbnail scale fix) and a "Failed runs" table exists.
- [ ] Open `docs/PREPROCESS_ABLATION.md`: every number has `data/processed/ablation/ablation.json` next to it.
- [ ] Open `docs/VIKRAM_2023_DIAGNOSIS.md`: each 2023 strip has exactly one cause class and the class follows the rule table.
- [ ] `lunar-reg catalog` lists every instrument with a status; absent ones do not stop anything.
- [ ] SuperGlue rows (if any) show the licence text in both viewers.

## Questions for the external reviewers
1. Is the NAC upper-left sign rule (fit to the label's bounding box) sound, and is `INFERRED` the right label for it?
2. Is the prior in `pairs.py` identical to the old script's, so `label_offset_m` means the same thing?
3. Does anything in the 2023 diagnosis state more than the artefacts show?
