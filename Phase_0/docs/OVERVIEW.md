# Phase 0 — what it does and why (for the human reviewer)

## The project in one paragraph
**Image registration** means finding where each pixel of one picture sits in another picture of the same ground. Here the "source" picture is from **OHRC** (the Orbiter High Resolution Camera on India's Chandrayaan-2, 0.25 m per pixel) and the "reference" picture is an **LRO NAC orthoimage** (a NASA map of the Moon's surface, 1 m per pixel, already placed on a map grid). The pipeline finds **correspondences** (pairs of points that show the same crater edge in both pictures), fits a **transform** (a small matrix that maps any source pixel to a reference pixel), and refines it.

## Why Phase 0 exists
Before any new feature, the code had defects that change the numbers it stores. Examples, each with its audit ID in `AUDIT.md`:

| defect | plain-language effect | example |
|---|---|---|
| S1 (A005) | Asking for an **affine** transform (rotation + scale + shear + shift, 6 numbers) silently produced a **homography** (adds perspective, 8 numbers), while the record still said "affine". | 9 of the 13 stored results say `affine` but carry a perspective row. |
| S2 (A006) | The count of raw correspondences was thrown away, so the **inlier ratio** (share of correspondences that agree with the fitted transform) came out as ≈ 1.0 for every pair. | Stored rows show 144 inliers out of 144 matches. |
| S3 (A024) | A "tight 1-pixel refit" documented in the code never ran; the loose 3-pixel threshold was reused. | Residuals were reported at the loose threshold. |
| A001 | The LightGlue matcher (a neural network that pairs keypoints) crashed on every GPU call. | Every LightGlue run on the laptop GPU became `MATCHER_ERROR`. |
| A002 | The LoFTR matcher (another neural matcher) received images whose sides were not multiples of 8, which shifts its answers. | Median error 3.04 px instead of 0.17 px in the audit's measurement. |

## What changes (13 prompts)
| prompt | change |
|---|---|
| P0.00 | Tag the starting point (`phase-base-approved`) and create branch `phase-0`. |
| P0.01 | One command runs all CPU tests (`scripts/ci.sh`); a GitHub workflow runs it; data bundles unpack safely. |
| P0.02 | One LoFTR and one LightGlue implementation, fixed and tested; duplicate files removed. |
| P0.03–P0.04 | Remove duplicate functions and dead files (`footprint.py`, `default.yaml`). |
| P0.05 | Label reader returns the first matching field in file order, not the last. |
| P0.06 | Catalogue footprints stored as polygons instead of a twisted "bow-tie". |
| P0.07 | A shared **provenance** label (`ValueSource`: measured / computed / documented / inferred / unknown) for every new number; a `run_record.json` written by every data run; a fixed random seed so the same input gives the same transform. |
| P0.08 | The refinement step (**ECC**, Enhanced Correlation Coefficient: nudges the transform until pixel brightness lines up) keeps the requested model, never edits its inputs, and rejects a jump larger than 3 px. |
| P0.09 | Raw / RANSAC / final inlier counts are all kept; every failure after matching gets a named status instead of a crash. (**RANSAC** = fit the transform many times on random subsets and keep the answer most points agree with.) |
| P0.10 | Results store version 2: validated names, safe writes, failures saved to `failures.parquet`. |
| P0.11 | Exported GeoTIFFs are rebuilt only from recorded numbers. |
| P0.12 | Evaluation fixes: which error dominates, a consistent **conditioning** measure (how much the transform could wobble), and a **uniformity** score (how evenly points cover the image) that small point sets can actually pass. |

## What is *not* in Phase 0
No new data, no GPU benchmark, no re-run of stored results (the live store is archived and re-run in Phase 1, P1.18). Numbers in docs are not touched.

## How it is checked
Each prompt has `Phase_0/harness/check_P0.<jj>.sh` (under 30 s). At the end, `harness/verify.sh` runs everything and `benchmark/run.sh` writes `benchmark/score.json` using the rubric in `benchmark/RUBRIC.md`. Scores come only from that run.
