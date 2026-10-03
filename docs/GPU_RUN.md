# End-to-end GPU run (P2.11)

What this page is: the record of the first full pipeline run on the laptop GPU
with native refinement switched on (Phase_2/LLD/runner_gpu_runs.md §P2.11).
Every number below is copied from a run artefact, and that artefact's path is in
the same table row or sentence. A cell that no artefact fills says
`[INSERT RESULT]`.

## Terms used on this page

| term | meaning |
|---|---|
| GPU, VRAM | the graphics card (here an NVIDIA RTX 4060 Laptop) and its own memory. Learned matchers run on it; VRAM is the limiting resource |
| OHRC | Orbiter High Resolution Camera on Chandrayaan-2: the *source* image we want to place on the map |
| NAC ortho | the LRO Narrow Angle Camera orthoimage of the Vikram landing site: the *reference* image, already map-projected |
| anchor | the 2024 OHRC strip `20240425T1406019344`, the one strip the pipeline is tuned and checked on |
| matcher | the algorithm that finds the same ground point in both images. `sift`, `akaze`, `asift` are classical (OpenCV, CPU). `lightglue` (DISK features + LightGlue) and `loftr` are learned (torch, GPU) |
| inliers | matched point pairs that agree with the fitted transform (RANSAC survivors). More is better, but it says nothing about accuracy on its own |
| U (`u_score`) | uniformity score in 0–1: how evenly the inliers cover the image. The Phase 1 target is ≥ 0.7 |
| working GSD | ground sample distance, metres per pixel. Matching runs at 4 m/px (the "coarse" grid) |
| native refinement | after the 4 m/px match, the transform is refined again at the reference's own resolution (the NAC's native GSD), using the 4 m/px transform as the starting guess (the *prior*) |
| drift (coarse px) | the largest distance, over a 5×5 grid of probe points, between where the refined transform and the prior put a point, measured in 4 m/px pixels. More than 1.0 is classified `drift_exceeded` (Phase_2/LLD/native.md step 6) |
| peak VRAM | `torch.cuda.max_memory_allocated` after a reset just before matching: MEASURED, the matcher's own allocations only, not the desktop's or the allocator cache's |
| live store | the results store `data/processed/results`; one row per (pair, matcher) |

## What ran

The official P2.11 run is the LLD §P2.11 step 1 command with one flag added,
`--native-matcher lightglue`. That flag is the human's answer (a) to Q-P2.11-1
(Phase_2/QUESTIONS.md). The LLD command alone refines the default native matcher,
`sift`. sift runs on the CPU, so its result row records `x_device = cpu`
(Q-P2.05-1), and the P2.11 check and the Phase 2 scorer only look for the native
result on a row whose device starts with `cuda`. LightGlue runs on the GPU.

| item | value | artefact |
|---|---|---|
| command | `scripts/run_vikram.py --only 20240425T1406019344 --instruments OHRC --levels raw --matchers sift,akaze,asift,lightglue,loftr --device cuda --native --native-matcher lightglue --results-root data/processed/results --out-dir data/processed/gpu_run/anchor --overwrite` | `data/processed/gpu_run/anchor/run_record.json` (`command`) |
| wrapper | `systemd-run --user --scope -p MemoryMax=12G -p MemorySwapMax=0` (host-RAM cap, DECISIONS G18) | first line of `data/processed/gpu_run/anchor/console_step1.log` names the scope unit |
| device | `cuda:0 NVIDIA GeForce RTX 4060 Laptop GPU` | `data/processed/gpu_run/anchor/run_record.json` (`device`; C15-valid) |
| exit code | 0 | last line `exit=0` of `data/processed/gpu_run/anchor/console_step1.log` |
| preprocess | `none` (the site runner default; the command passes no `--preprocess`, Q-P2.11-3) | `data/processed/gpu_run/anchor/run_record.json` (`params.preprocess`) |
| coarse pass | 8 m/px lightglue, 172 inliers, shift +554.052, −2890.812 m (E, S) | `data/processed/gpu_run/anchor/console_step1.log` |

The live-store rows of this run are saved, filtered to the run's start and finish
times, in `data/processed/gpu_run/anchor/store_rows.json`
(written by `data/processed/gpu_run/snap_rows.py`). This run record and the live
store rows come from the same run.

### Earlier attempts (archived, not used for any number above)

Two earlier runs were made before the human's answer. Both were moved, not
deleted, to `data/processed/gpu_run_archive_20261003/` (its `README.txt` explains
each folder):

- `runA_lld_sift_native/`: the LLD command exactly as written (native matcher
  `sift`). Its native refinement was classified `drift_exceeded`: drift 2.453
  coarse px against the 1.0 limit (`data/processed/gpu_run_archive_20261003/runA_lld_sift_native/console_step1.log`,
  counts `native_drift_exceeded: 1` in `.../runA_lld_sift_native/run_record.json`).
  The later run overwrote the live-store npz files that this run record lists as
  its artefacts, so run A's per-pair npz contents are lost. Its
  `store_rows.json` keeps the scalar columns.
- `runB_lightglue_native/`: the same command as the official run, written to a
  separate output folder. It overwrote run A's live-store rows, so the check then
  read run A's record together with run B's rows. A reviewer flagged that mix. Its
  four live-store npz files were copied to `runB_lightglue_store_npz/` before
  the official run replaced them.

Step 2 (2023 strips): no run. Every 2023 strip row in
`data/processed/vikram/exp1_gate.json` has `passes_targets: false`
(`20230823T1450475804`, `20230823T1647285085`, `20230823T1647285315`, all
`status: no_result`), so the LLD's "for every 2023 tag whose row has
`passes_targets: true`" selects nothing.

## Per-matcher results

Rows from `data/processed/gpu_run/anchor/store_rows.json` (snapshot of the live
store `data/processed/results`); status from
`data/processed/gpu_run/anchor/products.json`.

| matcher | status | device | precision | seconds_match | peak_vram_bytes | inliers | U |
|---|---|---|---|---|---|---|---|
| sift | ok | cpu | fp32 | 0.419 | n/a (CPU matcher, no VRAM reading) | 57 | 0.677 |
| akaze | ok | cpu | fp32 | 0.311 | n/a (CPU matcher) | 58 | 0.745 |
| asift | ok | cpu | fp32 | 19.304 | n/a (CPU matcher) | 156 | 0.789 |
| lightglue | ok | cuda | fp16-disk+fp32-lightglue | 0.411 | 2830844416 (MEASURED) | 191 | 0.829 |
| loftr | matcher_error | [INSERT RESULT] | [INSERT RESULT] | [INSERT RESULT] | [INSERT RESULT] | [INSERT RESULT] | [INSERT RESULT] |

LoFTR's message, from `data/processed/gpu_run/anchor/console_step1.log`, is
`loftr/outdoor: reference is 1343x1330 but the VRAM budget allows at most 896px
on this device. Tile the input first (lunar_reg.match.tiled.TiledMatcher)`. The
runner hands LoFTR the whole 4 m/px reference crop untiled, and the matcher's
guard refuses it before running. This is a classified `matcher_error`, not an
out-of-memory crash: the run record counts `oom: 0`
(`data/processed/gpu_run/anchor/run_record.json`). A failed outcome is not saved
to the store, so its timing and VRAM cells stay `[INSERT RESULT]`. The 896 px
limit comes from `LoFTRMatcher.max_tile_px`
(src/lunar_reg/match/learned.py:122). That property calls `plan_dense_tile`
without a device profile, so the limit is the analytic (INFERRED) model, not the
measured profile. The free VRAM it planned against at that moment is in no
artefact: `[INSERT RESULT]`. See Q-P2.11-2.

## Native refinement

| native matcher | status | drift (coarse px) | native matches | native inliers | native GSD (m) | artefact |
|---|---|---|---|---|---|---|
| lightglue | ok | 0.7361811246 | 14089 | 2367 | 1.0 | lightglue row of `data/processed/gpu_run/anchor/store_rows.json`; counts `native_ok: 1`, `native_drift_exceeded: 0` in `data/processed/gpu_run/anchor/run_record.json` |

- Provenance (`x_native_provenance`, same file): `n_matches` and `n_inliers`
  measured, `drift_coarse_px` and `transform` computed, `native_gsd_m` inferred
  (from the reference georeference).
- Native-GSD GeoTIFF:
  `data/processed/gpu_run/anchor/registered/CH2_OHRC_RAW_20240425T1406019344-LRO_NAC_ORTHO_lightglue_native.tif`
  (5322 × 5372 px, read back with rasterio from that file).
- Which device the native LightGlue matcher ran on is not recorded:
  `refine_native_arrays` builds its matcher without a `device` argument
  (Q-P2.10-2(d)). `[INSERT RESULT]`.
- Inlier counts and drift describe internal agreement only. Real pairs have no
  ground truth, so none of these numbers measures accuracy.

## Artefacts

| artefact | path |
|---|---|
| run record | `data/processed/gpu_run/anchor/run_record.json` |
| per-product outcomes | `data/processed/gpu_run/anchor/products.json` |
| console log (with exit code) | `data/processed/gpu_run/anchor/console_step1.log` |
| store-row snapshot | `data/processed/gpu_run/anchor/store_rows.json` |
| registered GeoTIFFs (4 m/px and native) | `data/processed/gpu_run/anchor/registered/` |
| archived earlier attempts | `data/processed/gpu_run_archive_20261003/` |
| 2023 gate (step 2 selection) | `data/processed/vikram/exp1_gate.json` |
