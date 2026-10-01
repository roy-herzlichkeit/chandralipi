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
