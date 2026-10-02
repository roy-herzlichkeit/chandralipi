# Preprocessing presets: which one is the default, and why

This page records how the default preprocessing preset of the registration
pipeline was chosen (prompt P1.19, decision G09). The choice is not a judgement
call: a fixed rule (`choose_default_preset`, written down in
`Phase_1/LLD/preprocess_presets.md` §3) is applied to one measured artefact,
`data/processed/ablation/ablation.json`, produced by
`scripts/run_ablation.py` in prompt P1.18 (run record:
`data/processed/ablation/run_record.json`). Every number below is copied from
that file; the path is given in each table caption.

## Words used on this page

- **Registration**: finding the geometric transform that lines up a
  Chandrayaan-2 image (the *source*) with a reference image of the same ground
  (here, the LRO NAC orthoimage of the Vikram landing site), so that each
  source pixel can be given a map position.
- **Matcher**: the algorithm that finds the same small surface features (crater
  rims, boulders) in both images and pairs them up. Four are compared here:
  `sift`, `akaze`, `asift` (classical, hand-designed feature detectors) and
  `lightglue` (a learned neural-network matcher).
- **Inliers** (`n_inliers`): the feature pairs that agree with the single
  transform the pipeline fits; pairs that disagree are discarded as wrong
  matches. More inliers means more evidence for the transform, not proof that
  it is right.
- **Uniformity** (`u_score`, 0 to 1): how evenly the inliers are spread over the
  image. A transform supported only by points in one corner can be badly wrong
  elsewhere; a score near 1 means the points cover the image evenly.
- **Q18 targets**: the project's pass mark for a real pair, from CLARIFY Q18:
  at least 20 inliers and a uniformity of at least 0.7.
- **Truth RMS** (`truth_rms_px`): on a synthetic pair, where the true transform
  is known because the program made it, the root-mean-square distance (in
  pixels) between where the fitted transform and the true transform send a grid
  of points spread over the whole image. Lower is better. It only exists for
  SYNTHETIC pairs; real pairs have no ground truth.
- **Sun azimuth**: the compass direction the sunlight comes from. Shadows on
  the Moon point away from the sun, so two images taken with the sun in
  different directions show the same crater with differently placed shadows,
  which makes matching harder.

## What a preset is

A **preset** is a fixed recipe of brightness and contrast adjustments applied in
the same way to both images of a pair just before the matcher looks at them. It
never moves or resamples pixels, so the positions the matcher finds are still
positions in the original images. The three presets
(`src/lunar_reg/preprocess/presets.py`, CONTRACTS C12):

| preset | what it does, in plain words |
|---|---|
| `none` | uses the images as they are (only rescales them to 8-bit grey levels when needed) |
| `ohrc_nac` | the chain described by Makharia et al. for OHRC and NAC images: stretch the brightness range, boost local contrast (CLAHE: contrast-limited adaptive histogram equalisation, which raises contrast region by region rather than over the whole image), invert black and white, then thicken bright features slightly (dilation). Several of its parameters are PLACEHOLDERS, not values taken from the paper |
| `clahe_shadow` | stretch the brightness range, brighten dark (shadowed) areas with a gamma curve, then boost local contrast (CLAHE) |

If a preset produces an unusable image (for example, every valid pixel the same
value), the pair is recorded as `preprocess_failed`; it is never silently
skipped.

## What was measured

Two kinds of rows, kept apart in the artefact (`labels` in
`data/processed/ablation/ablation.json`: `anchor` = REAL, `synthetic` =
SYNTHETIC):

1. **Anchor (real data).** The anchor is OHRC strip
   `20240425T1406019344` (raw level) registered against the LRO NAC
   orthoimage, once per preset and matcher. There is no ground truth here, so
   the only question asked is whether the result clears the Q18 targets.
2. **Synthetic (SYNTHETIC).** Generated scenes with a known transform. The
   reference image's sun is rotated by 0°, 15°, 30° or 60° in azimuth relative
   to the source (`azimuth_delta_deg`), for five random scenes (seeds 0 to 4),
   with the `sift` and `lightglue` matchers. Here the transform error against
   the truth (`truth_rms_px`) is measured.

### Anchor table (REAL)

Source: `data/processed/ablation/ablation.json`, key `anchor` (`n_inliers` and
`u_score` are MEASURED per the file's `value_sources`). "Passes" = status `ok`,
`n_inliers` ≥ 20 and `u_score` ≥ 0.7.

| preset | matcher | status | n_inliers | u_score | passes Q18 targets |
|---|---|---|---:|---:|---|
| `none` | sift | ok | 58 | 0.672 | no |
| `none` | akaze | ok | 68 | 0.670 | no |
| `none` | asift | ok | 168 | 0.794 | yes |
| `none` | lightglue | ok | 392 | 0.891 | yes |
| `ohrc_nac` | sift | ok | 163 | 0.824 | yes |
| `ohrc_nac` | akaze | ok | 204 | 0.909 | yes |
| `ohrc_nac` | asift | ok | 222 | 0.822 | yes |
| `ohrc_nac` | lightglue | ok | 421 | 0.892 | yes |
| `clahe_shadow` | sift | ok | 35 | 0.723 | yes |
| `clahe_shadow` | akaze | ok | 100 | 0.796 | yes |
| `clahe_shadow` | asift | ok | 127 | 0.750 | yes |
| `clahe_shadow` | lightglue | ok | 429 | 0.894 | yes |

These counts say how much evidence each run found, not how accurate it is: a
real pair has no ground truth, and the fit's error on its own points is never
reported as accuracy.

### Synthetic summary (SYNTHETIC)

Source: `data/processed/ablation/ablation.json`, key `synthetic`
(`truth_rms_px` is COMPUTED per the file's `value_sources`). Each cell is the
SYNTHETIC median `truth_rms_px` (pixels) over the seeds whose status is `ok`,
followed by (OK seeds / seeds run). "—" = no seed was OK; the failed seeds are
`too_few_matches` or `too_few_inliers` (counts per status in
`data/processed/ablation/run_record.json`, `outcome_counts`).

| preset | matcher | Δaz 0° | Δaz 15° | Δaz 30° | Δaz 60° |
|---|---|---:|---:|---:|---:|
| `none` | sift | 0.211 (5/5) | 0.219 (5/5) | — (0/5) | — (0/5) |
| `none` | lightglue | 0.211 (5/5) | 0.219 (5/5) | 0.311 (5/5) | 2.238 (5/5) |
| `ohrc_nac` | sift | 0.111 (5/5) | 0.137 (5/5) | 1.731 (1/5) | — (0/5) |
| `ohrc_nac` | lightglue | 0.111 (5/5) | 0.137 (5/5) | 0.197 (5/5) | 2.816 (5/5) |
| `clahe_shadow` | sift | 0.111 (5/5) | 0.143 (5/5) | — (0/5) | — (0/5) |
| `clahe_shadow` | lightglue | 0.111 (5/5) | 0.143 (5/5) | 0.195 (5/5) | 3.115 (5/5) |

## The rule and its outcome

The rule (`Phase_1/LLD/preprocess_presets.md` §3, implemented as
`lunar_reg.preprocess.presets.choose_default_preset`), in order:

1. For each preset, count the anchor rows that pass the Q18 targets.
2. Keep the presets with the highest count.
3. If more than one is left, keep the one with the lowest median
   `truth_rms_px` over all of its OK SYNTHETIC rows (a preset with no OK
   synthetic row ranks last).
4. If still tied, prefer `none`; otherwise take the first in the order
   `none`, `ohrc_nac`, `clahe_shadow`.
5. Safety check: the winner may never pass fewer anchor rows than `none`.

Per-preset inputs to the rule, from `data/processed/ablation/ablation.json`:

| preset | anchor rows passing | SYNTHETIC OK rows | SYNTHETIC median `truth_rms_px` over OK rows |
|---|---:|---:|---:|
| `none` | 2 of 4 | 30 of 40 | 0.2893 |
| `ohrc_nac` | 4 of 4 | 31 of 40 | 0.1370 |
| `clahe_shadow` | 4 of 4 | 30 of 40 | 0.1373 |

Outcome: the rule returns **`ohrc_nac`**, with the reason string stored in
`data/processed/ablation/ablation.json` (`winner`, `reason`): "anchor passes
none=2 ohrc_nac=4 clahe_shadow=4; anchor tie between ohrc_nac, clahe_shadow;
median synthetic truth_rms_px ohrc_nac=0.137 clahe_shadow=0.1373; ohrc_nac wins
on synthetic". `ohrc_nac` and `clahe_shadow` tie on the real anchor, and the
SYNTHETIC tie-break separates them by 0.0003 px (0.1370 vs 0.1373,
`data/processed/ablation/ablation.json`): the decision is by rule, and the
margin between these two presets is small.

`PipelineConfig.preprocess` now defaults to `"ohrc_nac"`
(`src/lunar_reg/pipeline.py`, with a comment citing the artefact and the
reason).

## The anchor in the live results store

After the default was set, the anchor strip was registered into the live
results store with the new default preset (`scripts/run_vikram.py --only
20240425T1406019344 --instruments OHRC --levels raw --matchers
sift,akaze,asift,lightglue --min-inliers 8 --preprocess ohrc_nac`, run record
`data/processed/vikram/runs/p1_19_anchor/run_record.json`). All 4 of 4 matchers
returned `ok` and 4 rows were saved (`outcome_counts` `ok` = 4, `saved` = 4 in
`data/processed/vikram/runs/p1_19_anchor/run_record.json`). This is a separate
run from the ablation; its per-matcher inlier counts (console:
`data/processed/vikram/runs/p1_19_anchor/console_step4.log`) are not identical to
the ablation rows above, and the cause has not been investigated.
