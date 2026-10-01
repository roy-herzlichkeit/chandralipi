# REVIEW PACK — Phase 0

## Diff range
`phase-base-approved..HEAD` (DECISIONS G07). Stat taken at HEAD = `d64cd82` (P0.12, last code commit); the `P0: review pack` commit adds only this file, `Phase_0/benchmark/score.json` and `STATUS.md`.

```
 .github/workflows/ci.yml                |  22 ++
 Phase_0/QUESTIONS.md                    |  36 +++
 Phase_0/prompts/INDEX.md                |  26 +-
 README.md                               |   1 -
 STATUS.md                               |  12 +-
 configs/default.yaml                    |  36 ---
 pyproject.toml                          |  11 +-
 scripts/build_demo_results.py           |   8 +-
 scripts/ci.sh                           |   7 +
 scripts/fetch_catalogue.py              |  32 +--
 scripts/reindex_results.py              |  43 +++-
 scripts/run_vikram.py                   | 199 +++++++++++----
 scripts/setup.sh                        |  18 +-
 scripts/untar_data.py                   | 201 +++++++++++++++
 src/lunar_reg/align/estimate.py         |  88 +++++--
 src/lunar_reg/align/refine.py           | 282 +++++++++++++++++----
 src/lunar_reg/constants.py              |  35 ++-
 src/lunar_reg/eval/conditioning.py      | 235 +++++++++++------
 src/lunar_reg/eval/error_budget.py      | 126 ++++++----
 src/lunar_reg/eval/metrics.py           |  50 +++-
 src/lunar_reg/eval/uniformity.py        | 115 +++++++--
 src/lunar_reg/ingest/__init__.py        |   4 +-
 src/lunar_reg/ingest/fieldmap.py        |  57 ++++-
 src/lunar_reg/ingest/footprint.py       | 120 ---------
 src/lunar_reg/ingest/lro.py             |  32 ++-
 src/lunar_reg/ingest/manifest.py        |  40 ++-
 src/lunar_reg/ingest/overlap.py         |  52 +++-
 src/lunar_reg/ingest/pds4.py            | 129 +++++++---
 src/lunar_reg/ingest/pseudo_gt.py       |  88 ++++---
 src/lunar_reg/match/classical.py        |  62 +++--
 src/lunar_reg/match/learned.py          | 123 +++++----
 src/lunar_reg/match/loftr.py            | 188 --------------
 src/lunar_reg/match/rift2/matcher.py    |  39 ++-
 src/lunar_reg/match/stitch.py           |  21 +-
 src/lunar_reg/match/superglue.py        | 107 ++------
 src/lunar_reg/pipeline.py               | 277 +++++++++++++++------
 src/lunar_reg/preprocess/__init__.py    |   2 +-
 src/lunar_reg/preprocess/radiometric.py |  17 +-
 src/lunar_reg/provenance.py             |  32 +++
 src/lunar_reg/results.py                | 429 ++++++++++++++++++++++++++++----
 src/lunar_reg/runrecord.py              | 227 +++++++++++++++++
 tests/test_catalogue_footprints.py      | 128 ++++++++++
 tests/test_ecc_fidelity.py              | 194 +++++++++++++++
 tests/test_estimate_seeded.py           | 126 ++++++++++
 tests/test_eval.py                      |  14 +-
 tests/test_eval_fixes.py                | 135 ++++++++++
 tests/test_footprint.py                 |  53 ----
 tests/test_learned_matchers.py          | 144 +++++++++++
 tests/test_pds4_resolver.py             | 135 ++++++++++
 tests/test_pipeline_counts.py           | 155 ++++++++++++
 tests/test_results_and_pipeline.py      |  10 +-
 tests/test_results_v2.py                | 159 ++++++++++++
 tests/test_run_vikram_geometry.py       | 206 +++++++++++++++
 tests/test_untar_data.py                | 111 +++++++++
 54 files changed, 4038 insertions(+), 1161 deletions(-)
```

## verify.sh
Exit code: **0** (`bash Phase_0/harness/verify.sh`). Last 30 lines:

```
tests/test_registered_export.py::test_provenance_tags_travel_with_the_file
tests/test_registered_export.py::test_affine_2x3_matrix_is_accepted
  /home/herzlichkeit/Desktop/Projects/sih/.venv/lib/python3.12/site-packages/rasterio/__init__.py:377: NotGeoreferencedWarning: The given matrix is equal to Affine.identity or its flipped counterpart. GDAL may ignore this matrix and save no geotransform without raising an error. This behavior is somewhat driver-specific.
    dataset = writer(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
- generated xml file: /home/herzlichkeit/Desktop/Projects/sih/Phase_0/benchmark/out/ci_junit.xml -
========== 536 passed, 6 deselected, 11 warnings in 100.70s (0:01:40) ==========
== resource-marked repo tests (gpu / weights / data; skip with reason when absent)
......                                                                   [100%]
=============================== warnings summary ===============================
tests/test_learned_matchers.py::test_loftr_cpu_odd_size_pads_and_drops_padding_matches
  /home/herzlichkeit/Desktop/Projects/sih/.venv/lib/python3.12/site-packages/torch/jit/_script.py:1491: FutureWarning: `torch.jit.script` is deprecated. Please switch to `torch.compile` or `torch.export`.
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
6 passed, 536 deselected, 1 warning in 4.19s
== Phase 0 harness
........................................................................ [ 62%]
...........................................                              [100%]
=============================== warnings summary ===============================
Phase_0/harness/tests/test_P0_02.py::test_loftr_odd_size_cpu
  /home/herzlichkeit/Desktop/Projects/sih/.venv/lib/python3.12/site-packages/torch/jit/_script.py:1491: FutureWarning: `torch.jit.script` is deprecated. Please switch to `torch.compile` or `torch.export`.
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
115 passed, 1 warning in 6.05s
== ruff on files changed since phase-base-approved
All checks passed!
CHECK OK: Phase 0 verify
```

## score.json
`Phase_0/benchmark/score.json`, verbatim:

```json
{
  "axes": {
    "correctness": {
      "detail": {
        "cpu_suite": {
          "errors": 0,
          "failed": 0,
          "failed_ids": [],
          "passed": 536,
          "returncode": 0,
          "skip_reasons": {},
          "skipped": 0,
          "tail": "pile` or `torch.export`.\n    warnings.warn(\n\ntests/test_overlap.py::test_crop_writes_both_sides\ntests/test_overlap.py::test_crop_filenames_encode_the_pair_not_just_the_product\ntests/test_overlap.py::test_crop_output_is_a_readable_geotiff\ntests/test_overlap.py::test_lid_with_colons_produces_a_safe_filename\n  /home/herzlichkeit/Desktop/Projects/sih/.venv/lib/python3.12/site-packages/rasterio/__init__.py:367: NotGeoreferencedWarning: Dataset has no geotransform, gcps, or rpcs. The identity matrix will be returned.\n    dataset = DatasetReader(path, driver=driver, sharing=sharing, thread_safe=thread_safe, **kwargs)\n\ntests/test_overlap.py::test_crop_writes_both_sides\ntests/test_overlap.py::test_crop_filenames_encode_the_pair_not_just_the_product\ntests/test_overlap.py::test_crop_output_is_a_readable_geotiff\ntests/test_overlap.py::test_lid_with_colons_produces_a_safe_filename\ntests/test_registered_export.py::test_provenance_tags_travel_with_the_file\ntests/test_registered_export.py::test_affine_2x3_matrix_is_accepted\n  /home/herzlichkeit/Desktop/Projects/sih/.venv/lib/python3.12/site-packages/rasterio/__init__.py:377: NotGeoreferencedWarning: The given matrix is equal to Affine.identity or its flipped counterpart. GDAL may ignore this matrix and save no geotransform without raising an error. This behavior is somewhat driver-specific.\n    dataset = writer(\n\n-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html\n536 passed, 6 deselected, 11 warnings in 99.05s (0:01:39)\n"
        },
        "harness": {
          "errors": 0,
          "failed": 0,
          "failed_ids": [],
          "passed": 115,
          "returncode": 0,
          "skip_reasons": {},
          "skipped": 0,
          "tail": "........................................................................ [ 62%]\n...........................................                              [100%]\n=============================== warnings summary ===============================\nPhase_0/harness/tests/test_P0_02.py::test_loftr_odd_size_cpu\n  /home/herzlichkeit/Desktop/Projects/sih/.venv/lib/python3.12/site-packages/torch/jit/_script.py:1491: FutureWarning: `torch.jit.script` is deprecated. Please switch to `torch.compile` or `torch.export`.\n    warnings.warn(\n\n-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html\n115 passed, 1 warning in 5.99s\n"
        }
      },
      "direction": ">=",
      "pass": true,
      "threshold": 1.0,
      "value": 1.0,
      "weight": 0.4
    },
    "quality": {
      "detail": {
        "parts": {
          "counts": {
            "samples": [],
            "truth_rms_px": [
              0.023223993894854966,
              0.012963571143151775,
              0.01634602280212799,
              0.0142889124326852,
              0.009701594664348641,
              0.014970030069480712,
              0.0158650390745857,
              0.012326306971167548,
              0.018415721484820236,
              0.015492428393915177
            ],
            "unclassified_exceptions": 0,
            "value": 1.0
          },
          "determinism": {
            "in_process": true,
            "subprocess": true,
            "value": 1.0
          },
          "ecc_affine": {
            "samples": [],
            "value": 1.0
          }
        },
        "pass": {
          "counts": true,
          "determinism": true,
          "ecc_affine": true,
          "no_unclassified_exceptions": true
        },
        "thresholds": {
          "counts": 1.0,
          "determinism": 1.0,
          "ecc_affine": 0.9
        }
      },
      "direction": ">=",
      "pass": true,
      "threshold": 1.0,
      "value": 1.0,
      "weight": 0.3
    },
    "spec_conformance": {
      "detail": {
        "contracts": {
          "errors": 0,
          "failed": 0,
          "failed_ids": [],
          "passed": 29,
          "returncode": 0,
          "skip_reasons": {},
          "skipped": 0,
          "tail": ".............................                                            [100%]\n=============================== warnings summary ===============================\nPhase_0/harness/tests/test_contracts_P0.py::test_C15_roundtrip\n  /home/herzlichkeit/Desktop/Projects/sih/.venv/lib/python3.12/site-packages/torch/jit/_script.py:1491: FutureWarning: `torch.jit.script` is deprecated. Please switch to `torch.compile` or `torch.export`.\n    warnings.warn(\n\n-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html\n29 passed, 1 warning in 1.91s\n"
        }
      },
      "direction": ">=",
      "pass": true,
      "threshold": 1.0,
      "value": 1.0,
      "weight": 0.3
    },
    "synthetic": {
      "detail": {
        "label": "SYNTHETIC \u2014 truth-based error on generated scenes, never merged with real-data axes (Q19)",
        "metric": "median transform_rms_px vs known homography, sift, same illumination, 10 seeds",
        "values_px": [
          0.023223993894854966,
          0.012963571143151775,
          0.01634602280212799,
          0.0142889124326852,
          0.009701594664348641,
          0.014970030069480712,
          0.0158650390745857,
          0.012326306971167548,
          0.018415721484820236,
          0.015492428393915177
        ]
      },
      "direction": "<=",
      "pass": true,
      "threshold": 0.5,
      "value": 0.015231229231697944,
      "weight": 0.0
    }
  },
  "created_utc": "2026-10-01T07:39:28+00:00",
  "git_sha": "d64cd82184885dd35d22a3547339e0207c27cf20",
  "pass": true,
  "phase": "0",
  "provenance": "measured",
  "schema": 1,
  "skips": {
    "count": 0,
    "reasons": {}
  },
  "weighted_total": 1.0
}
```

## QUESTIONS
`Phase_0/QUESTIONS.md`, verbatim:

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

## LLD deviations
| file:line | LLD section | what differs | why |
|---|---|---|---|
| scripts/untar_data.py:164 | test_ci.md §4 | Directory members are not extracted; they are counted in the report header ("directory members created as needed") and created as parents of extracted files. | §4 says "extract every file member" and lists no status for directories; counting them keeps them visible without inventing a fifth `MemberStatus`. |
| scripts/untar_data.py:101 | test_ci.md §4 | `REFUSED_UNSAFE` is applied to every member that is neither a regular file nor a directory (a superset of symlink/hardlink/device/fifo). | Covers any other tar member type with the same refusal instead of letting it through. |
| scripts/untar_data.py:173 | test_ci.md §4 | A `tarfile.FilterError` raised in pass 2 (e.g. an existing symlink under `--dest` that resolves outside it) is recorded as `REFUSED_UNSAFE` and the script exits 2, after any earlier members were extracted. | Pass 1 cannot see the destination's existing symlinks; the data filter catches them in pass 2, and the refusal is reported rather than raised. |
| src/lunar_reg/match/learned.py:53 | matchers_learned.md §2.1 | The uint8-vs-`to_uint8` choice is made on the input dtype *before* the 3-D band mean. | The mean turns uint8 into float; deciding afterwards would percentile-stretch an 8-bit RGB input instead of dividing it by 255. |
| src/lunar_reg/match/superglue.py:30 | matchers_learned.md §1 | Docstring references now name `lunar_reg.match.learned.LightGlueMatcher`. | The class they referred to was deleted from this module. |
| scripts/fetch_catalogue.py:73 | dedupe_and_removals.md §P0.04 | Comment-only edit in a file the §P0.04 table does not list. | The protected harness grep (`test_P0_04.py::test_no_references_left`) fails otherwise; Q-P0.04-1. |
| src/lunar_reg/ingest/fieldmap.py:39 | pds4_resolver.md §2 | Segment parsing lives in public `parse_segment`/`parse_path` in fieldmap.py (shared by `Field.__post_init__` and `pds4._resolve`); an empty segment (`A//c`) is also malformed. | One parser for validation and matching. |
| src/lunar_reg/ingest/pds4.py:87 | pds4_resolver.md §2 | A predicate is also honoured on the last (leaf) segment, not only on ancestors. | Same matcher for every segment; no field in the map uses a leaf predicate today. |
| src/lunar_reg/ingest/manifest.py:95, src/lunar_reg/ingest/lro.py:311 | pds4_resolver.md §5 | Rows write `image_path = None` (not the string `"None"`) when the image path was rejected. | `str(None)` would put a fake path into the manifest. cli.py:39 still assumes a path (Q-P0.05-1). |
| scripts/fetch_catalogue.py:56 | catalogue_footprints.md §1 | `from __future__ import annotations` removed from the script. | Python 3.12 `dataclasses` cannot process string annotations in a module loaded via `spec_from_file_location` without a `sys.modules` entry; the protected `load_script` does exactly that (Q-P0.06-1). |
| src/lunar_reg/runrecord.py:46 | provenance_runrecord_fit.md §2 | Every `RunRecord` field has a default. | Lets `read_run_record` and partial construction work; field names, order and JSON keys are exactly C15. |
| src/lunar_reg/align/refine.py:194 | ecc.md §2 / C07 | `EccStatus.is_failure` property added (NOT_CONVERGED, REJECTED_DISPLACEMENT). | Classified-outcomes skill pattern; enum members and values unchanged. |
| src/lunar_reg/align/refine.py:436 | ecc.md §2 | A non-finite `cc` or a singular returned warp is classified `NOT_CONVERGED`. | Otherwise a non-finite result could be reported as APPLIED. |
| src/lunar_reg/align/refine.py:483 | ecc.md §2 | `nodata=NaN` builds the mask as `~isnan(image)`. | `image != NaN` is True everywhere and would mask nothing. |
| src/lunar_reg/align/refine.py:150 | ecc.md §3 / C07 | `reestimate_on_inliers` copies a mask-less `MatchResult` before fitting. | `MatchResult.inliers()` returns the same object when no mask is set, so the fit would write the caller's `inlier_mask` ("inputs are never mutated"). |
| src/lunar_reg/pipeline.py:266 | pipeline_counts.md §2 | `PairResult` construction sits inside the stage-7 `try`, so an invalid `pair_id` (C04 validation) is classified `EVAL_FAILED`. | `register_pair` must not raise for a bad pair (C02). |
| src/lunar_reg/pipeline.py:368 | results_v2.md §6 | `BatchReport.report()` appends `store.report()` when a store report exists. | The store outcome is printed on every run (classified-outcomes convention). |
| src/lunar_reg/results.py:563 | results_v2.md §5 / C05 | `StoreReport.report()` gets the root from a private `_root` attribute set by `reindex`/`save_results`, not a dataclass field. | C05 freezes `StoreReport`'s fields; the report line format needs the root. |
| src/lunar_reg/results.py:623 | results_v2.md §5 | `save_results(overwrite=False)` checks every target before writing any and raises one `FileExistsError` naming the clashes. | A clash midway would otherwise leave a half-saved batch and an un-reindexed store. |
| src/lunar_reg/results.py:500 | results_v2.md §4 | `save_failures` writes nothing when no outcome failed (returns the path anyway); `load_failures` on an absent file returns an empty frame with the C05 columns. | No empty parquet files; callers can still read the columns. |
| src/lunar_reg/results.py:347 | results_v2.md §3 | `load_pair` validates `pair_id` against `PAIR_ID_PATTERN` before building the path. | A pair id is a file name; `../x` must not read outside the store. |
| scripts/run_vikram.py:304 | run_vikram_geometry.md §2 | "Recorded" geometry requires `shift_e_m`/`shift_s_m` as well as `ref_crop_c0`/`ref_crop_r0`; otherwise the legacy note path is tried. | The shift sets the integer extent of the reference crop, hence the output shape; defaulting it would be a silent default. |
| scripts/run_vikram.py:427 | run_vikram_geometry.md §3 | `--dry-run` returns 0 (no run attempted) instead of "1 when no run succeeded". | A dry run never matches by design. |
| scripts/run_vikram.py | (G21 / CLAUDE.md fence) | Not `ruff format`ted. | Formatting would add pre-existing drift across the whole script and bury the geometry diff. |
| src/lunar_reg/eval/conditioning.py:148 | eval_fixes.md §2 | The least-squares fitters are one public function `fit_lsq(src, dst, model)`, reused by the error-budget oracle (§4); rank-deficient `lstsq` systems count as failed refits. | One fitter for §2 and §4; `lstsq` returns a finite minimum-norm answer on degenerate input instead of failing. |
| src/lunar_reg/eval/uniformity.py:142 | eval_fixes.md §3 | `max_occupiable_cells` is a read-only property (not a field, not in `as_dict`, not used by the score). | Named by the prompt's DO 3 but absent from LLD §3 / G33 (Q-P0.12-1). |
| src/lunar_reg/eval/uniformity.py:290 | eval_fixes.md §3 | `uniformity_profile` uses a fixed-grid helper `_uniformity_on_grid`; `compute_uniformity` picks `g_eff` and calls it. | LLD §3: the profile keeps fixed grids 4/8/16 while the gate uses the adaptive grid. |
| src/lunar_reg/eval/uniformity.py:355 | eval_fixes.md §3 | `enforce_uniformity` uses `_bin` but keeps clipping out-of-frame points into border cells (it still returns them). | LLD §3 changes only `cell_counts` to drop them; thinning behaviour is otherwise unchanged. |
| src/lunar_reg/eval/error_budget.py:267 | eval_fixes.md §1, ecc.md §3 | The refinement note prints `cc` only when `ecc_cc` is not None, else `ecc <ecc_status>`; the `ecc_skipped` branch is gone. | C07 makes `ecc_cc` always present and possibly None; the old `:.3f` format raised TypeError (Q-P0.08-1). |
| src/lunar_reg/eval/error_budget.py (dominant) | eval_fixes.md §1 | Docstring/report describe the not-resolved band as "within 25%". | The LLD comment says "20 %" but its formula is `larger / smaller <= 1.25`; the code follows the formula. |

## Review focus
`Phase_0/REVIEW_FOCUS.md`, verbatim:

# Phase 0 — review focus

Where reviewers should look hardest, and why. Ordered by risk to stored numbers.

| # | where | why it is risky | how to check |
|---|---|---|---|
| 1 | `align/refine.py` `ecc_refine` | The ECC argument convention (template = reference, input = source, init = inverse, invert result) is load-bearing; three of four orderings give wrong answers with a *higher* correlation coefficient (refine.py docstring). The affine path adds a 2×3 ↔ 3×3 conversion that is easy to transpose. | Read the inversion code for both motions; run `Phase_0/harness/tests/test_P0_08.py` and the C07 contract tests; compare against the known-affine scene. |
| 2 | `pipeline.register_pair` mask composition (G34) | Refit runs on the RANSAC-inlier subset; mapping its mask back to raw indices is an index-bookkeeping step where an off-by-order error silently marks the wrong points as inliers. | `test_P0_10.py::test_register_pair_fills_v2_fields` asserts refit ⊆ RANSAC; also inspect one stored pair by hand. |
| 3 | `align/estimate.py` centroid shift | Un-centring must be `T_dst⁻¹ · M · T_src` in float64; the wrong order still fits exact data near the origin. | `test_C06_large_coordinates` uses coordinates around 5×10⁵ px. |
| 4 | `ingest/pds4.py` traversal + predicates | Document order changes which element resolves for every label; ncp labels carry both System_Level and Refined corners. | `test_P0_05.py`; the data-marked real-label test; diff `lunar-reg probe-label` output on one real label before/after. |
| 5 | `results.py` atomic writes and v1 loading | `np.savez_compressed` appends `.npz` to paths without it, which breaks write-then-rename; v1 files must still load. | `test_C04_overwrite_refused`, `test_C04_v1_loads`; no `*.tmp` left. |
| 6 | `eval/uniformity.py` normalisation (G33) | Changes every stored U value; the Phase 1 gate (U ≥ 0.7) depends on it. | `test_P0_12.py::test_uniformity_small_sets_can_pass`; check the U of a clustered set still falls. |
| 7 | `scripts/run_vikram.py` export | Must never write a GeoTIFF from default or missing numbers; the old regex fallback returned (0, 0) silently. | `test_P0_11.py::test_export_classification`. |
| 8 | `scripts/untar_data.py` | Security boundary for data bundles. | Try `../`, absolute, symlink, `src/` members. |
