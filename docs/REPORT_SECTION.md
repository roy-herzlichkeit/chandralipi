# Results, and how they relate to prior work

*Draft section for the internal-round submission. Every figure is from a run in
this repository on 2026-09-05. Figures we have not produced are marked
`[INSERT RESULT]` rather than estimated.*

## 1. Status of the evidence

We have not had access to Chandrayaan-2 products. PRADAN registration was
flagged on day one as an unknown-duration gate, and it has not cleared, so **no
number in this section was computed on lunar imagery.**

Rather than wait, the pipeline was exercised on synthetic scenes: a fractal
height field with stamped craters, rendered under controlled sun positions with
ray-marched cast shadows (`lunar_reg.eval.scenes`). This buys something real
data cannot give — an **exact ground-truth transform** — which is what makes the
error attribution in §3 possible at all.

It also costs something. The shading model omits lunar photometry (the Moon is
strongly backscattering, closer to Hapke than Lambert), the opposition surge,
detector noise and MTF, and the pushbroom geometry that makes a real OHRC strip
non-projective. Conclusions about *ranking* transfer; absolute numbers do not.

## 2. What was measured

36 pair-runs across 3 sensor pairings, 3 matchers and 4 illumination cases.
**26 registered; 10 did not**, and the failures are classified rather than
dropped: 9 returned too few correspondences, 1 too few inliers after RANSAC.

| illumination | matcher | inliers | RMSE self (px) | RMSE vs truth (px) | uniformity U | extrapolation p95 (px) |
|---|---|---|---|---|---|---|
| same sun | ASIFT | 11040 | 0.4354 | 0.0115 | 0.987 | 0.035 |
| same sun | SIFT | 680 | 0.2323 | 0.0115 | 0.986 | 0.138 |
| same sun | AKAZE | 555 | 0.1850 | 0.0115 | 0.808 | 0.100 |
| 15° azimuth | ASIFT | 1520 | 1.2519 | 0.0294 | 0.955 | 0.357 |
| 15° azimuth | SIFT | 231 | 1.0247 | 0.0294 | 0.953 | 0.748 |
| 30° azimuth | ASIFT | 125 | 1.3560 | 0.0756 | 0.622 | 2.155 |
| 30° azimuth | SIFT | 27 | 1.0648 | 0.0756 | 0.445 | 4.580 |
| 180° azimuth | all | — | not registered | — | — | — |

(OHRC↔LRO NAC pairing; the TMC-2 and IIRS pairings follow the same pattern.)

## 3. Three findings

**3.1 The illumination cliff is in azimuth, not brightness.** SIFT recovers 228
geometrically correct matches at 15° of azimuth change, 4 at 30°, and 0 at 60°.
Shadow fraction moves independently and does not predict the collapse. Adding
illumination-invariant albedo texture to the scene did not rescue it, because at
grazing sun the shadowed fraction is multiplicative and destroys that texture
too.

**3.2 The refinement stage sets the accuracy floor, not the matcher.** Running
four matchers on the same pair, all four converge to an *identical* final error
(0.011 px at 0°, 0.092 px at 15°, 0.304 px at 30°) despite starting from RANSAC
fits differing by an order of magnitude. The matcher only has to get close
enough for intensity refinement to lock on.

Acting on that: normalising local contrast before the ECC stage cuts the error
**4.8×** at 30° (0.299 → 0.062 px median), winning in 100% of runs over 6 seeds
and 2 matchers once illumination differs. It *loses* by ~0.02 px when
illumination is identical, so the choice is driven from sun-angle metadata.

We also tried to select it automatically from image statistics and **failed** —
normalised cross-correlation falls both for illumination change and for sensor
noise, and the correct response is opposite in each case. That auto-mode is
shipped disabled and documented as defective rather than quietly enabled.

**3.3 RMSE over the matched points is not registration accuracy.** On the same
pairs, the self-residual RMSE and the true error against the known transform
differ by **12.7× to 58.6×** across all 26 registered pairs. Two independent reasons, pulling in opposite directions:

- Where correspondences are dense and noisy, the self-residual is dominated by
  correspondence noise and is *pessimistic* — 0.4354 px reported against 0.0115
  px true.
- Where correspondences are clustered, the self-residual is *optimistic*. Over
  six point layouts holding count and noise fixed, it varies by 4% while the
  true worst-case error varies by **51×**.

## 4. Relationship to Makharia et al. (arXiv:2509.04775)

The closest published work benchmarks SIFT, ASIFT, AKAZE, RIFT2 and SuperGlue on
real Chandrayaan-2 data. We read it in full. Three points matter.

**4.1 Their RMSE uses the definition in §3.3.** Their §4.7.1 defines it over
"matching control points in both the reference image and the transformed warped
image" — the points the transform was fitted from. Their *ranking* of the five
algorithms is sound, since all five were scored identically. Their numbers do
not establish sub-pixel accuracy across the image, and they cannot be placed in
a table beside a truth-based figure. We therefore **do not present a side-by-side
comparison**, and reproduce their table separately in `docs/MAKHARIA_PARITY.md`.

**4.2 Preprocessing parity cannot be confirmed.** Five of their ten steps carry
no parameter values in the text: CLAHE clip limit, CLAHE tile grid, PCA
component count, the dilation structuring element, and the shadow-normalisation
method. Our corresponding parameters were already carried as explicit
placeholders for this reason; reading the paper confirmed the gap rather than
closing it.

**4.3 Their IIRS result changed our architecture.** They matched IIRS against
LRO **WAC** — 80 m/px against 100 m/px, a 1.25× ratio — never against a
high-resolution camera. At that ratio plain SIFT (0.6879 / 1.1066) lands within
0.13 px of SuperGlue (0.5069 / 0.6167), which shows the cross-modal difficulty
had already been removed by the choice of reference. Our own scan independently
flags IIRS↔OHRC at 320× as beyond any direct matcher and proposes TMC-2 as the
bridge. Full reasoning in `docs/CROSS_MODAL_IIRS.md`.

*A caution on their Table 3:* the DFSAR–SELENE Polar row is identical to the
OHRC–NAC Polar row in all three figures to four decimal places (0.9234 / 0.7586
/ 4.643), which is almost certainly a duplicated cell.

## 5. What we add beyond the required metrics

The problem statement asks for RMSE, inlier count and inlier ratio. We report
those, and two more.

**Spatial uniformity** `U = √(coverage × entropy)`, as a descriptive diagnostic.
Stress-testing showed it must not be used as a gate: it *fails* border-only and
hollow-ring layouts that are among the best-conditioned tested (0.109 and 0.213
px true error), and *passes* a sparse lattice that is 3–5× less precise than a
dense grid. Spearman against true error: **−0.52**.

**Extrapolation uncertainty**, in pixels, by bootstrap resampling of the
correspondences. Spearman against true error: **+0.78**. It cannot be gamed by
arranging points to satisfy a grid, since it responds to the geometry the fit
actually sees, and it renders as a map showing *where* a registration is
trustworthy. This is the metric we gate on.

Stated limit: it measures precision, not accuracy. A correlated error — the ECC
illumination bias in §3.2, or a systematic georeferencing offset — leaves it
small while the answer is wrong. It is reported alongside RMSE, never instead.

## 6. Numbers still to produce

- `[INSERT RESULT]` every figure in §2 and §3 recomputed on real OHRC / TMC-2 /
  IIRS products, once PRADAN access clears.
- `[INSERT RESULT]` LightGlue and LoFTR results. Both are implemented; neither
  has run on a GPU, because this machine's NVIDIA kernel module is not loaded
  and the installed PyTorch is a CPU-only build.
- `[INSERT RESULT]` measured VRAM. Current tiling figures are host-RSS proxies;
  the break points (LoFTR fp32 between 1024 and 1152 px, LightGlue between 1536
  and 2048 px) come from an address-space cap, which is stricter than VRAM.
- `[INSERT RESULT]` the georeferencing residual that would turn our pseudo
  ground truth's error budget from a floor (23.09 m) into a total.
- SuperGlue is **not** planned: its weights are noncommercial-research-only, and
  our wrapper refuses to run without explicit acknowledgement. LightGlue
  (Apache-2.0) is the shippable substitute and is a different model, so it would
  not reproduce their headline number in any case.
