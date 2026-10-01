# PLAN_PROGRESS — Task B

**COMPLETE** (sessions B1–B3, 2026-09-29). The plan is committed on `main` for external review; implementation starts with `P0.00` (`STATUS.md`).

## Global artefacts
- [x] 1. AUDIT.md — 132 rows, phase + closing prompt per row (from `.fable/audit_20260929.json`); every row is referenced by an LLD (checked by script in B3)
- [x] 2. HLD.md — components K1–K20, data flows, cross-cutting rules
- [x] 3. DECISIONS.md — G01–G35 (G27 reordered after G26; G14 revised; G30–G35 added)
- [x] 4. CONTRACTS.md — C01–C27 with producer/consumer phases and proving tests
- [x] 5. PHASES.md — 73 prompts with file ownership; TBD → prompt map
- [x] 6. Root CLAUDE.md (implementer-facing)
- [x] 7. STATUS.md (current = P0.00)
- [x] 8. Tool-level deny rules: superseded by CLARIFY Q22/R8 → G05 (MANIFEST.sha256 + git-diff check)
- [x] 9. PLAN_PROGRESS.md (this file)

## Phase folders (10)
| phase | prompts | LLD files | harness tests (collected) | checks | contracts proved |
|---|---|---|---|---|---|
| Phase_0 | 13 | 11 | 115 | 13 + verify | C01–C07, C15 |
| Phase_1 | 25 (incl. P1.DL) | 18 | 141 | 25 + verify | C03 (preprocess), C08–C14, C20 |
| Phase_2 | 12 | 5 | 43 | 12 + verify | C03 (device), C16–C19 |
| Phase_1B | 7 | 5 | 19 | 7 + verify | C21 |
| Phase_3 | 10 | 5 | 38 | 10 + verify | C22–C26 |
| Phase_4 | 7 | 4 | 18 | 7 + verify | C27 |
Each folder also has `benchmark/{RUBRIC.md,run.sh,score.py}`, `ASSUMPTIONS.md`, `DECISIONS.md`, `REVIEW_FOCUS.md`, `docs/{OVERVIEW.md,REVIEW_CHECKLIST.md}`, `QUESTIONS.md`, and `harness/MANIFEST.sha256`. Shared skills: `Phase_0/skills/{classified-outcomes,provenance-fields,atomic-writes,tests-and-checks}`, `Phase_1/skills/run-prompts`, `Phase_2/skills/gpu-safety`.

## Final consistency pass (11) — results of the B3 checks
- [x] every TBD → ≥ 1 phase (`PHASES.md` §4); every audit row → an existing prompt and an LLD mention (script: 132/132)
- [x] every contract's producer precedes its consumers (C01–C27 order checked against INDEX order)
- [x] no prompt LOADs a file that does not exist at that point (script: 12 LOAD paths not yet on disk, each created by an earlier prompt)
- [x] no banned words in Opus-facing docs (grep over CLAUDE/CONTRACTS/DECISIONS/PHASES/HLD and every Phase prompt, LLD, skill, ASSUMPTIONS, DECISIONS, REVIEW_FOCUS; "TBD n.m" backlog references excepted)
- [x] every harness test file collects (`pytest --co`, 356 tests) and, run against today's code, fails only for "not implemented yet" reasons (import errors, missing attributes, reproduced audit bugs) — checked per phase

## How an external reviewer should read this plan
1. `CLARIFY.md` (binding answers) → `DECISIONS.md` → `HLD.md` → `CONTRACTS.md` → `PHASES.md`.
2. Per phase: `docs/OVERVIEW.md`, `REVIEW_FOCUS.md`, then `prompts/INDEX.md` and the LLDs; `harness/tests/test_contracts_P<i>.py` shows exactly what "done" means.
3. Evidence behind defects: `AUDIT.md` (+ `.fable/audit_20260929.json`); behind data sources: `.fable/research_20260929.json`; behind signatures: `.fable/module_facts_20260929.txt`.
4. Things the architect checked by running code in B3 (not benchmark figures): the NAC upper-left sign rule on the real label (flipped 935 m vs as-written 23.9 km bbox residual); prior-rectified tiling prototype (median raw-match error 0.10 px on the C18 scene); LoFTR padding (median error 2.0 px unpadded vs 0.31 px padded on the P0.02 scene); geometry-grid CSV fixture format; that A009, A071, A107, A125 and A001 reproduce as test failures today.

## Open items for the human
- CLARIFY R2 (ISRO SIS PDFs → `docs/external/`), R3b (second host details) — neither blocks Phases 0–3.
- P1.DL tonight: product list and click-by-click steps in `Phase_1/LLD/downloads.md` §2–§3.
- `redis-server` install (sudo) before P4.06.
- Task D (external adversarial review): 38 items adjudicated in `REVIEW_DECISIONS_PLAN.md` (23 ACCEPT, 13 ACCEPT_MODIFIED, 2 REJECT, 0 NEEDS_HUMAN); how they were applied: `MERGE_PLAN_PLAN.md`. Harness now collects 374 tests.

## Fix log
| session | fix |
|---|---|
| B3 | P1.21 split into P1.21 (viewers) + P1.22 (docs); AUDIT rows A069/A070/A116/A120–A124 re-pointed; A114 moved to P1.14 |
| B3 | P1.19 became a RUN prompt (applies the ablation default, then registers the anchor into the live store) |
| B3 | `run_ablation.py` added to P1.17; ODE sun metadata switched to the VALIDATED box query (`results=m`) |
| B3 | Resampling matrices fixed to the pixel-centre convention of `cv2.resize` (C11/C19), removing a (f−1)/2-pixel bias |
| B3 | Phase 1B skip made a one-commit branch approved like any phase (G02/G07); Phase 3 base is always `phase-1B-approved` |
| B3 | `pytest` marker `weights` added (G15/G21); C23 `bytes_read`, C24 `claim(max_bytes)`, C25 `run_worker(max_bytes)` added before freeze |
| B3 | CLAUDE.md: existing-test edits allowed when the prompt changes the behaviour they pin; network exceptions listed by prompt |
| D | Review RC02/13/16 → G37: worker lifts with matrix products only; `job.prior` is patch→reference-window; Phase 3 fixtures use non-zero window offsets |
| D | Review RC01/04/06/28/29 → G36: `run_local` closes unfinished jobs when all workers die; C24 `renew` + worker heartbeat; Redis tier streams with a registry, no skip/re-add; XDEL on ack/reclaim; `purge`; `distributed supervise` |
| D | Review RC03/05/25/34 → `hosts.json` gains `results_dir`, `source_root`; `cluster_up.sh` passes cache/source/results dirs, `ssh -n` + `< /dev/null`, pid files, `--stop` |
| D | Review RC17/15 → G14: sun geometry from SPICE generic kernels (COMPUTED); ODE incidence and DTM-hillshade fit kept as cross-checks; C13 +2 functions |
| D | Review RC07 → G33 adaptive uniformity grid; RC14 → G39 ECC with both validity masks (C07); RC18 → G38 prior shift OHRC-only; RC21 → C10 keyword-only |
| D | Review RC09/10/11/12/22/27/35/36 → stricter Phase 1/1B/2 checks and benchmarks (native bridge, real IIRS, cross-instrument run, structured diagnosis, datum ran, run records required, `ok > 0`) |
| D | Review RC30 → P1.22 split into P1.22 (docs) + P1.23 (code text); total 74 prompts |
| 2026-10-01 | P1.DL overran the 20 GB disk budget (47.3 GB added); human raised CLARIFY Q17 to 60 GB for `data/raw/`, keeping everything. G40 large-raster rule; P1.15 gains `scripts/probe_raster.py` + two harness tests; downloads LLD §2.4 records what P1.DL fetched and §3 adds a running budget check |
