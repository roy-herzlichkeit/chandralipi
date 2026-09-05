# Benchmark reconciliation against Makharia et al. (arXiv:2509.04775)

*Comparative Evaluation of Traditional and Deep Learning Feature Matching
Algorithms using Chandrayaan-2 Lunar Data.* Read in full (PDF, 906 lines of
extracted text) on 2026-09-05.

## Bottom line

**We cannot compare our numbers to theirs, and the obstacle is not missing data
on our side — it is that their RMSE measures a different quantity than ours.**
Their RMSE is the residual of the fitted transform on the same correspondences
that produced it. Ours is measured against an independent truth. Those two
numbers can differ by more than an order of magnitude on identical data, so
placing them in one table would be misleading even once we have real products.

This shares a root cause with Task 1 and Task 3, and it is the same root cause:
*a fit's residual on its own points is nearly blind to how those points are
distributed, and therefore to how wrong the transform is elsewhere in the image.*

## What their RMSE actually is

Section 4.7.1, verbatim:

> - Identifying matching control points in both the reference image and the
>   transformed warped image
> - Applying the derived perspective transformation to align the control points
> - Calculating the Euclidean distance between each pair of corresponding points
> - Computing the square root of the average of these squared distances

The control points are the matched points. The transformation was estimated from
those matched points. So this is the fit's own residual — in our code, the
`matches: RANSAC inliers` row of `lunar_reg.eval.error_budget`, not the
`transform: after refinement` row.

Measured in this project on six point layouts holding point count and
correspondence noise fixed, so that **only the spatial distribution changed**:

| layout         | fit residual RMSE | true error at probes | worst case |
|----------------|-------------------|----------------------|------------|
| grid (even)    | 0.698             | 0.049                | 0.114      |
| uniform random | 0.699             | 0.071                | 0.142      |
| one quadrant   | 0.701             | 0.309                | 0.768      |
| two clusters   | 0.705             | 0.390                | 1.092      |
| diagonal band  | 0.717             | 0.999                | 2.393      |
| tight blob     | 0.724             | 1.653                | 5.861      |

The fit residual moves by 4%. The true worst-case error moves by 51x. A
clustered solution reports a sub-pixel residual while being nearly six pixels
wrong elsewhere in the same frame.

**Consequence for their headline claim.** SuperGlue's 0.6249 / 0.5718 px on
OHRC-NAC Equatorial is a genuine result about SuperGlue producing
self-consistent correspondences, and their ranking of the five algorithms is
probably sound, because all five were scored the same way. What the number does
*not* establish is sub-pixel registration accuracy across the image, which is
what the problem statement actually asks for. Nothing in the paper reports the
spatial distribution of the matches, so the gap cannot be estimated from the
published numbers.

## Preprocessing parity: not confirmable

The paper names every step and quantifies none of them.

| Step | Stated | Parameter values given? |
|---|---|---|
| Georeferencing | Selenographic -> Equirectangular Moon | n/a |
| Resolution resampling | yes, per sensor pair | target GSDs given, interpolation method **not** stated |
| Intensity normalisation | to 8-bit 0-255 | **no** percentiles or clipping stated |
| CLAHE | yes, tiles + histogram clipping + bilinear interpolation | **no clip limit, no tile grid size** |
| Image inversion | `255 - pixel` | fully specified |
| Morphological dilation | yes, "a defined structuring element" | **no kernel shape or size** |
| PCA | yes | **no component count or variance threshold** |
| Histogram matching | IIRS -> WAC | fully specified in principle |
| Shadow normalisation | yes | **no method, no parameters** |
| Log transformation | yes | **no scale constant** |

Five of the ten steps cannot be reproduced from the text. This vindicates the
`ParamSource.PLACEHOLDER` markers already carried in
`lunar_reg.preprocess.params`: those were applied on the assumption that the
paper would not specify the values, and reading it confirms it does not.

**Their pipeline is also not one pipeline.** It branches by sensor pair, which
our ablation-oriented design happens to accommodate but our defaults do not
reproduce:

- OHRC <-> NAC: CLAHE, inversion, morphological dilation, PCA
- IIRS <-> WAC: histogram matching, shadow normalisation, log transformation
- DFSAR <-> SELENE: not described in the preprocessing section

Parity therefore has to be assessed per pair, not once.

## Data subset differences

| | Makharia et al. | This project |
|---|---|---|
| Source products | OHRC, IIRS, DFSAR | OHRC, TMC-2, IIRS |
| Reference products | LRO NAC, LRO WAC, SELENE | LRO NAC (planned) |
| **TMC-2** | **not used at all** | central to our overlap stage |
| **DFSAR** | used | out of scope (not an optical payload) |
| Regions | equatorial and polar | not yet selected |
| Pair count | **not stated** | n/a |
| Image dimensions | **not stated** | n/a |
| Sun-angle range | **not stated** | n/a |

The absence of a stated pair count matters more than it looks: Table 3 reports a
single RMSE per algorithm per dataset with no spread, so it is not possible to
tell whether each cell is one pair or an average over many, and no variance is
available to judge whether differences between algorithms are significant.

## The IIRS finding, which changes our cross-modal plan

Their IIRS work is the most directly useful part of the paper for us, and it
settles a question we had open.

They matched **IIRS against LRO WAC**, not against a high-resolution camera.
Section 4.1.2: IIRS at ~80 m/px was resampled to WAC's 100 m/px. That is a
**1.25x scale ratio**. Our own scan flags IIRS <-> OHRC at 320x as beyond any
direct matcher (`lunar_reg.ingest.pseudo_gt.MAX_DIRECT_SCALE_RATIO`), and the
paper never attempts it.

So the tractability of IIRS here comes from choosing a *reference at IIRS's own
scale*, not from a cleverer matcher. Their results bear that out — on IIRS-WAC
Equatorial, plain SIFT (0.6879 / 1.1066) and AKAZE (0.5551 / 1.0841) land close
to SuperGlue (0.5069 / 0.6167). The cross-modal problem largely dissolves once
the scale gap does.

They also reduced the cube by **selecting "a single, visually clear band"** and
applying the resulting transform to all other bands — not by PCA. PCA appears
only in the OHRC-NAC branch. This is evidence for band selection over PCA as the
IIRS default, which is the direction we had reasoned toward on physical grounds.

## Table 3, reproduced, with one caution

RMSE in pixels, time in seconds. `NA` as printed in the paper.

| Dataset | Algorithm | RMSE X | RMSE Y | Time |
|---|---|---|---|---|
| OHRC-NAC Equatorial | AKAZE | 3.1189 | 4.7096 | 737.1722 |
| | ASIFT | 1.9946 | 1.6345 | 809.8209 |
| | RIFT2 | 1.5033 | 1.1888 | 36.881 |
| | SIFT | 3.6096 | 5.9558 | 678.1992 |
| | SuperGlue | 0.6249 | 0.5718 | 3.809 |
| OHRC-NAC Polar | SuperGlue | 0.9234 | 0.7586 | 4.643 |
| | others | NA | NA | NA |
| IIRS-WAC Equatorial | AKAZE | 0.5551 | 1.0841 | 0.1634 |
| | ASIFT | 0.5578 | 1.0990 | 1.6407 |
| | RIFT2 | 1.4056 | 1.3579 | 7.3894 |
| | SIFT | 0.6879 | 1.1066 | 0.1207 |
| | SuperGlue | 0.5069 | 0.6167 | 0.818 |
| IIRS-WAC Polar | AKAZE | 0.4595 | 1.3891 | 0.2287 |
| | ASIFT | 0.9837 | 0.4501 | 2.0922 |
| | RIFT2 | 0.7529 | 1.1054 | 12.716 |
| | SIFT | 2.0085 | 0.4050 | 0.1607 |
| | SuperGlue | 0.7681 | 0.9267 | 0.774 |
| DFSAR-SELENE Equatorial | SuperGlue | 0.3851 | 0.8432 | 0.745 |
| DFSAR-SELENE Polar | SuperGlue | 0.9234 | 0.7586 | 4.643 |

**Caution.** The DFSAR-SELENE Polar row is identical to the OHRC-NAC Polar row
in all three figures to four decimal places (0.9234 / 0.7586 / 4.643). Two
independent registrations of different sensor pairs agreeing to that precision
is not plausible; this is almost certainly a duplicated cell in Table 3. It does
not affect the OHRC or IIRS conclusions, but it is a reason to treat individual
cells as indicative rather than exact.

Note also that RMSE is decomposed into X and Y rather than reported as a
Euclidean magnitude. Our `RegistrationMetrics.rmse_px` is Euclidean. For a rough
comparison, `sqrt(X^2 + Y^2)` — SuperGlue on OHRC-NAC Equatorial becomes 0.847
px — but the paper does not state whether X and Y were computed over the same
point set, so even this conversion is an assumption.

## What we would need to make a real comparison

1. **Real PDS4 products.** No Chandrayaan-2 product has been inspected by this
   project; every footprint and sun-angle field remains UNVERIFIED. This alone
   blocks the comparison.
2. **A licence decision on SuperGlue.** SuperGlue's weights are released for
   noncommercial research only, and `lunar_reg.match.superglue.SuperGlueMatcher`
   refuses to run without an explicit acknowledgement. Reproducing their headline
   result means accepting that term; LightGlue (Apache-2.0) is the shippable
   substitute but is a different model and would not reproduce their numbers.
3. **Their exact products.** The paper names no product identifiers, so even with
   PRADAN access we would be matching a different subset of the archive.
4. **A stated pair count and spread**, without which no significance test is
   possible.

Items 3 and 4 are not obtainable from the publication. The honest position for
our own report is therefore to present our numbers with our own definition
stated explicitly, reproduce their table as published, and say plainly that the
two are not the same measurement — rather than to place them side by side.
