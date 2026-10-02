> **Copy.** Copied on 2026-10-02 (prompt P1.22, review item A070) from
> data/processed/vikram/README.md, last written 2026-09-28. Text only; the two
> figures it names stay in data/processed/vikram/. The run it describes is the
> v1 store, which P1.18 moved to data/processed/results_archive_20260929/
> (decision G08); the live store now holds the P1.19 anchor re-run
> (data/processed/vikram/runs/p1_19_anchor/). Every number below is as the
> original page states it, sourced to that 2026-09-28 run.

# Chandrayaan-2 OHRC ↔ LRO NAC: Vikram landing site, 2026-09-28

**The project's first real Chandrayaan-2 registration result.** Real data on
both sides, no synthetic imagery. The results are in the normal store
(`data/processed/results/`, sensor names `CH2_OHRC_RAW` / `LRO_NAC_ORTHO`) and
show up on the dashboard. The run is reproduced by `scripts/run_vikram.py`, and
the logs are in `data/processed/logs/`.

## Inputs

| role | product | ground resolution | sun |
|---|---|---|---|
| source | 4 × OHRC **raw** (`nrp`) products, see below | 0.25 m/px nominal (label corners imply ~0.27 × 0.28 m) | from the label |
| reference | `NAC_DTM_VIKRAMSITE1_M1442997156_100CM` map-projected orthoimage | 1.0 m/px | incidence ~74° (ODE, source frames M1442997156L/RC, 2023-07-03); azimuth **not published** |

The OHRC products are raw, not radiometrically calibrated. They came from two
partly downloaded PRADAN tars; 4 of the 6 products in the tars were complete.
Both images were resampled to 4 m/px for matching.

## Method

1. Take the centre 3 km × 3 km window of each OHRC strip.
2. Use the label corners and the corrected NAC georeference (see
   `data/raw/reference/lro_nac_vikram/PROVENANCE.json`) to predict where that
   window sits in the NAC image.
3. **Coarse pass:** LightGlue at 8 m/px with a 4 km margin, to find where the
   window actually is.
4. **Fine pass:** re-centre the NAC crop on that position (500 m margin), then
   match with `pipeline.register_pair` (RANSAC → inlier re-estimate → ECC
   refinement → metrics).

Only the reference crop is moved by step 3. `label_offset_m` is still measured
against the original label prediction.

## Results

### 2024-04-25 OHRC (`…T1406019344`, sun elevation 11.5°, azimuth 304°): registered

MEASURED, from real runs:

| matcher | inliers | self-RMSE (px) | median (px) | self-RMSE (m) | uniformity | 0.7 gate | label offset (m) |
|---|---|---|---|---|---|---|---|
| SIFT | 140 | 0.88 | 0.68 | 3.5 | 0.83 | PASS | 2939 |
| AKAZE | 144 | 1.28 | 1.05 | 5.1 | 0.86 | PASS | 2939 |
| ASIFT | 2180 | 1.15 | 0.86 | 4.6 | 0.99 | PASS | 2939 |
| LightGlue | 808 | 0.99 | 0.78 | 4.0 | 0.92 | PASS | 2939 |

**Read these with care:**

- **There is no ground truth.** The RMSE columns are the fit's residual on its
  own inliers, not an error against a known answer. This repo has measured the
  two kinds of RMSE differing by 12.7–58.6× on synthetic pairs.
- **The four rows share one final transform.** After ECC refinement they are
  identical to 0.0 m. ECC aligns the images directly by pixel intensity and
  converges to a single answer, so identical rows mean each matcher got close
  enough to start ECC, not that four independent measurements agreed.
- **The independent check:** with ECC turned off (diagnostic only, not saved),
  SIFT and LightGlue place the 3 km window within **2.2 m of each other at the
  corners and 0.3 m at the centre**, about half a 4 m pixel. Each is within
  5 m of the ECC result. This is the strongest evidence available without
  ground truth. It shows agreement between methods, not accuracy against
  reality.
- **Inlier ratio is omitted.** The pipeline reports it as ~1.000 even without
  ECC, apparently because it counts matches after the inlier re-estimate step.
  Here it carries no information.
- **Label offset 2,939 m** (556 m east, 2,888 m north): the combined error of
  the OHRC raw label corners, interpolated bilinearly, plus the corrected NAC
  georeference, which is itself known only to about 1 km. The coarse pass
  (8 m/px) and fine pass (4 m/px) agree to within 2 m. This is the size of
  error that image registration exists to remove.

Figures: `2024_lightglue_matches.png`, `2024_lightglue_checkerboard.png`. In
the checkerboard, crater rims and ridges continue unbroken across tile edges
over the whole window.

### 2023-08-23 OHRC (3 products, sun elevation 8–9°, azimuth 62°): not registered

MEASURED: 0 of 12 fine runs succeeded (4 matchers × 3 products), and the coarse
pass failed on all three.

| product | SIFT | AKAZE | ASIFT | LightGlue |
|---|---|---|---|---|
| `…T1450475804` | 4 matches | 7 matches | 4 of 32 kept by RANSAC | 2 matches |
| `…T1647285085` | 4 matches | 4 of 10 kept | 5 of 31 kept | 5 matches |
| `…T1647285315` | 7 matches | 4 of 9 kept | 4 of 28 kept | 5 of 16 kept |

The minimum for a result is 8 inliers. These are real failures, stored as
classified outcomes in the logs, not dropped.

**Probable cause: illumination.** This is INFERRED, not measured. The reference
sun azimuth is not in the label. 2023-07-03 was full moon, which puts 32°E in
early lunar afternoon, with the sun north-west. On that estimate the 2023-08-23
images (sun north-east, 8°) are lit from roughly the opposite side to the
reference, and the 2024 image (north-west, 11.5°) from the same side. That fits
the observed split, but it has not been verified. The surface itself is
unlikely to be the cause: all three 2023 footprints lie inside the successfully
registered area. Checking the sun azimuth of M1442997156 against SPICE would
confirm or rule this out.

## What this does and does not show

- **Shows:** OHRC raw imagery registers to LRO NAC at the Vikram site with four
  independent matchers when the illumination is compatible. Uniformity passes
  the 0.7 gate on every successful run, and two unrelated matchers agree to
  about half a pixel before refinement.
- **Does not show:** sub-pixel *accuracy* (no ground truth), performance at
  native OHRC resolution (this ran at 4 m/px, 16× coarser than OHRC), or
  robustness to opposite-side lighting. That last case is exactly what failed.
