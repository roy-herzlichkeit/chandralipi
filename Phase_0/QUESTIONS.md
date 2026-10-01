# Phase 0 — questions

Implementers append entries here (format in root `CLAUDE.md` §Doubts). Empty at plan time.

## Q-P0.04-1  LLD grep hit in unlisted file scripts/fetch_catalogue.py conflicts with harness grep
context: Phase_0/LLD/dedupe_and_removals.md §P0.04 last paragraph; scripts/fetch_catalogue.py:73; Phase_0/harness/tests/test_P0_04.py::test_no_references_left
question: The LLD says a grep hit in a file not in the §P0.04 table gets a QUESTIONS entry and the file is not edited. scripts/fetch_catalogue.py:73 is such a hit (comment "Matches ``ingest.footprint.moon_datum``."), but the protected harness test greps `scripts/` for `ingest\.footprint` and fails while that comment exists. Which rule wins?
what I did meanwhile: Edited only that comment line to "Matches ``lunar_reg.constants.moon_datum``." (comment-only, no behaviour change, one-line revert) so check_P0.04 can pass. Same treatment for the comment at src/lunar_reg/constants.py:19, which is a listed file.

## Q-P0.05-1  cli.py dereferences PDS4Product.image_path, which is now Optional
context: src/lunar_reg/cli.py:39 (`print(f"image:      {product.image_path.name}")`); Phase_0/LLD/pds4_resolver.md §5
question: §5 makes `PDS4Product.image_path` `Path | None` (None when the label's file_name escapes the product directory). cli.py is not in P0.05's file list, so its `.name` access is unchanged and would raise AttributeError for a rejected label. Should a later prompt print `image_path_rejected` there instead?
what I did meanwhile: nothing in cli.py. In the listed files, manifest.product_to_row and lro.lro_to_row now write `image_path = None` (not the string "None") when the path is rejected; recorded as an LLD deviation.

## Q-P0.06-1  scripts loaded via importlib crash on @dataclass under `from __future__ import annotations`
context: scripts/fetch_catalogue.py `Diagnostics` dataclass; Phase_0/harness/tests/_h0.py::load_script; /usr/lib/python3.12/dataclasses.py:749
question: `spec_from_file_location` + `exec_module` does not register the module in `sys.modules`; Python 3.12 `dataclasses` then dereferences `sys.modules.get(cls.__module__).__dict__` for every string annotation and raises AttributeError, so `load_script("fetch_catalogue")` (test_P0_06::test_issdc_reader_writes_wkt) failed before any P0.06 code ran (reproduced on the untouched base). Is removing the future import the intended fix, or should `load_script`/the tests-and-checks skill register the module in `sys.modules` first? The same will hit any later script with a dataclass loaded this way (run_vikram in P0.11, fetch_public/run_jaxa/run_ablation/export_web_data in Phase 1).
what I did meanwhile: removed `from __future__ import annotations` from scripts/fetch_catalogue.py (all its annotations evaluate natively on 3.10+; script imports and `--help` runs). One-line revert.

## Q-P0.08-1  eval/error_budget.py formats detail["ecc_cc"], which C07 now makes always-present and possibly None
context: src/lunar_reg/eval/error_budget.py:230-233; CONTRACTS.md C07 (refine_full detail keys always present; ecc_cc float or None; "ecc_skipped" removed per Phase_0/LLD/ecc.md §3)
question: `if "ecc_cc" in detail: note += f", cc={detail['ecc_cc']:.3f}"` now raises TypeError whenever ECC is not APPLIED (ecc_cc is None), and the `ecc_skipped` branch is dead. error_budget.py is not in P0.08's file list. Should P0.12 (which already edits error_budget.py) change this to `if detail.get("ecc_cc") is not None` and report `detail["ecc_status"]` instead of `ecc_skipped`?
what I did meanwhile: nothing in error_budget.py. scripts/ci.sh is green (497 passed), so no current test reaches the None path.

## Q-P0.09-1  check_P0.09.sh takes ~69 s, over the G18 30 s check budget, because of a pre-existing ASIFT test
context: Phase_0/harness/check_P0.09.sh (`repo_pytest ... tests/test_pipeline.py ...`); tests/test_pipeline.py::test_every_available_detector_produces_usable_matches[asift]; DECISIONS.md G18
question: That one parametrised case takes 64 s on its own, and 64.13 s on the untouched base (phase-base-approved, measured in a temporary worktree), so P0.09 did not cause it. The check passes but breaks the < 30 s budget. Should the ASIFT case get a marker / smaller input, or should the check exclude it (`-k "not asift"`)? Both need a plan or harness change I may not make.
what I did meanwhile: nothing; check_P0.09 passes as written (exit 0).

## Q-P0.10-1  Re-running run_vikram / build_demo_results now refuses existing pair ids
context: CONTRACTS.md C04/C05 (`save_results(..., overwrite=False)`); scripts/run_vikram.py:391, scripts/build_demo_results.py:115 (changed only as LLD §6 lists)
question: With refuse-to-overwrite as the default, a second run of either script into a store that already holds the same pair ids raises FileExistsError (checked for the whole batch before anything is written, so nothing is half-saved). Should those scripts gain an `--overwrite` flag or write to a fresh root per run? Not in P0.10's DO, so left as is.
what I did meanwhile: save_results checks every target before writing any (a clash stops the batch cleanly); live store untouched (13 v1 pairs load read-only under the v2 reader).

## Q-P0.12-1  Prompt names `max_occupiable_cells`; LLD §3 / G33 do not define it
context: Phase_0/prompts/P0.12_eval_correctness.md DO 3; Phase_0/LLD/eval_fixes.md §3; DECISIONS.md G33
question: DO 3 lists `max_occupiable_cells` but LLD §3 and G33 (revised, RC07) fix coverage = occupied / g_eff² with no such term. Was it meant to survive from the superseded min(n, g²) rule?
what I did meanwhile: added `UniformityMetrics.max_occupiable_cells` as a read-only property (= min(n_points, total_cells)), not used in coverage/score and not in as_dict; the score follows LLD §3 exactly (20 spread points -> 0.946, quadrant-packed -> 0.336). Removing the property is a one-line revert.
also noted: with the adaptive grid, coverage is a fraction of g_eff², so thinning can raise `coverage` (300 corner points -> 5 points: 1/64 -> 1/4). tests/test_eval.py::test_enforce_uniformity_cannot_create_coverage now asserts on fixed-8x8 occupied cells instead. Q-P0.08-1 (error_budget ecc_cc None) is fixed in this prompt, since error_budget.py is in P0.12's file list.

## Q-P0.R-1  Phase 0 verify.sh now fails on ruff in a Phase 1 harness file from the architect commit d97121f
context: Phase_0/harness/verify.sh (`ruff_files $(changed_py_since phase-base-approved)`); Phase_1/harness/tests/test_P1_15.py:63,131,133 (E501, added in d97121f "Plan: accept P1.DL disk overrun ...")
question: After the review fixes (ce33460) phase-0 sits on top of d97121f, so verify.sh's "ruff on files changed since phase-base-approved" step includes Phase_1/harness/tests/test_P1_15.py, which has three E501 lines (102/112/110 > 100). The file is protected (G05) and the Phase 1 MANIFEST pins it, so the implementer cannot fix it. Can the architect wrap those three lines and regenerate Phase_1/harness/MANIFEST.sha256?
what I did meanwhile: nothing to that file. Every Phase 0 file passes ruff; all other verify.sh steps pass (scripts/ci.sh 541 passed; marked tests 6 passed; Phase 0 harness 115 passed); benchmark/run.sh pass=True at ce33460. REVIEW_PACK_0.md is not refreshed yet: it waits for a green verify.sh.
answer (architect, 2026-10-01): fixed on `phase-0`: the three lines are wrapped (no assertion changed), `ruff check` passes on that file and on every `.py` changed since `phase-base-approved`, and Phase_1/harness/MANIFEST.sha256 is regenerated. Re-run verify.sh and refresh REVIEW_PACK_0.md.
