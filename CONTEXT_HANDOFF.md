# Chandralipi — context handoff

**For a reader with no prior exposure to this project or its conversation.**
Written 2026-09-05. Every number below either cites the run that produced it or
is marked as not-yet-measured. Nothing here is estimated silently.

---

## 0. State of the repo, in one paragraph

Chandralipi is a lunar image-registration pipeline for Smart India Hackathon
2026 problem SIH26166 (ISRO): find corresponding points between Chandrayaan-2's
optical payloads (OHRC 0.25 m/px, TMC-2 5 m/px, IIRS 80 m/px hyperspectral) and
a lunar reference (LRO NAC/WAC), to sub-pixel accuracy, with matches spread
evenly across the frame. The Python package `src/lunar_reg/` is complete and
tested end to end — ingest, footprint overlap, preprocessing, classical and
learned matchers, robust fitting with sub-pixel refinement, evaluation, per-pair
result persistence — plus a Streamlit tool and a separate React showcase site in
`web/`. **Until roughly one hour before this document was written, the entire
pipeline had never seen a real Chandrayaan-2 product**; every result in the repo
was produced on synthetic scenes. Real products have now begun arriving, the
metadata field map has been verified against one of them, and that verification
immediately exposed a critical bug (§1.1). The correct summary of the project's
maturity is: *the machinery is built and internally validated; its contact with
real data is one hour old and has already found one serious defect.*

---

## 1. Data quality issues

### 1.1 RETRACTED — the corner-ordering "bug" was a measurement error of mine

**Traces to:** nothing. `src/lunar_reg/ingest/overlap.py` is correct.

An earlier draft of this document reported a critical 1201× footprint-area bug
from corner ordering. **That was wrong and is retracted.** The error was in the
throwaway check, not in the pipeline: it built the ring by hand from
`corner1..corner4` in numeric order, which does describe a bow-tie, but
`footprint_from_row` never does that — it already traverses **1, 2, 4, 3**
precisely to avoid it, and always has.

Verified through the real code path on the real label: **78.89 km²**, against a
physical expectation of ~75 km² for a 3 km × 25 km OHRC strip. Correct.

The underlying fact is still worth knowing and is now pinned by a test
(`test_corner_numbering_is_not_ring_order`): ISRO's corners are named UL, UR,
**LL**, **LR**, so numeric order is *not* ring order, and the 1,2,4,3 traversal
must never be "simplified" away. Numeric order really would give 0.07 km².

Recorded rather than deleted because a retraction that vanishes is worse than
one that stays visible — anyone reading the transcript alongside this document
will see the original claim.

### 1.1b RESOLVED — every real OHRC product was rejected as polar

**Traces to:** `src/lunar_reg/ingest/overlap.py`, `POLAR_LATITUDE_DEG = 80.0`.

This is the actual blocker that the false alarm above was concealing. Measured
on all three complete real OHRC products:

| product | latitude range | area | `validate()` |
|---|---|---|---|
| `ch2_ohr_ncp_20260103T0609041371` | −85.37 … −84.55 | 78.89 km² | was **POLAR — rejected**, now `ok` |
| `ch2_ohr_ncp_20260103T1005176450` | −85.33 … −84.52 | 78.96 km² | was **POLAR — rejected**, now `ok` |
| `ch2_ohr_ncp_20260103T1203563771` | −85.33 … −84.53 | 79.33 km² | was **POLAR — rejected**, now `ok` |

The footprints were computed *correctly* — the areas are right — and then
discarded, because any footprint touching |lat| ≥ 80° was classified `POLAR` and
excluded from overlap detection.

The guard is defensible in itself: a lat/lon polygon genuinely misbehaves near a
pole, where longitude converges and a planar clip is wrong. But the problem
statement explicitly concerns polar regions, the benchmark paper has polar
datasets, and ISRO is evidently distributing polar OHRC. **100% of real OHRC
data reached the pipeline and was thrown away.**

**Status: RESOLVED 2026-09-05.** Polar pairs are now clipped in a `PolarFrame`
— an azimuthal-equidistant plane centred on the relevant pole, in degrees of arc
— and projected back to lat/lon; areas are still measured on the sphere. The
guard was not removed, it was replaced by a working path. All three products now
`validate()` as `ok` at 78.89 / 78.96 / 79.33 km², and the three pairwise
overlaps between them come out at 69.30 / 65.97 / 74.22 km² (83–94% of each
strip). Each figure was cross-checked against an independent Monte-Carlo
integration on the sphere — uniform in (lon, sin lat), great-circle
point-in-polygon, sharing no code with the clipper — and agreed to within its
2σ noise of ~0.16 km²; the lat/lon clip, for comparison, is off by +0.76%,
+0.32% and −0.40% on the same three pairs.

Two further defects were found and fixed in the course of it, both of which
produced *silently wrong* numbers rather than errors:

- `polygon_area_m2` returned exactly 0 m² for any longitude outside ±180,
  because `ST.LatLon` raises `RangeError` there and the raise was caught and
  swallowed at debug level. A 0..360 east longitude is a convention a PDS label
  is entitled to, and `validate()` accepts it. Longitudes are now folded first.
- A polar footprint given only as a lat/lon **bounding box** whose longitudes
  wrap describes a cap most of the way round the pole, not the product. It is
  now refused as `polar_bbox_unusable` rather than clipped confidently.

Still open, and left as a decision rather than taken silently: `manifest.py`
carries no `cornerN_*` columns, only the bounding box derived from them, so
`find_overlapping_pairs` on a real manifest sees 309 / 324 / 333 km² for these
three products instead of 79 km². Adding the corner columns would fix it and
would also change every non-polar area in the table, so it is not a change to
make without a decision.

### 1.1c The downloaded OHRC, TMC-2 and IIRS products do not overlap each other

**Traces to:** operational. **Updated 2026-09-05**, re-checked directly against
a larger, still-growing download (labels read from the zip archives without
full extraction — `unzip -p <zip> <label.xml>`).

As of this check, 8 OHRC products, 11 TMC-2 products (two fore/nadir/aft
tri-stereo triples plus a partial third), and 2 IIRS products had downloaded.
Every product's four-corner footprint, read directly from its label:

| instrument | latitude range | longitude range |
|---|---|---|
| OHRC (8 products) | −83.9° … −85.5° | 22.8° … 35.9°E |
| TMC-2 (11 products, 2 triples) | −1.9° … −29.6° | 138.6° … 143.0°E |
| IIRS (1 readable product; 1 still mid-download) | −3.9° … 31.4° | 100.0° … 101.4°E |

**Three disjoint regions of the Moon, none closer than roughly 65° of
longitude to either of the others.** Zero cross-instrument overlap is possible
at any pairing with what has been fetched so far — not a bug, a fact about
which orbits were selected.

**The cart itself is the reason, and it is now confirmed rather than inferred.**
The three `.sh` download scripts in `~/Downloads` each list **500 unique
product files** spanning the mission's full date range (2019–2026 for OHRC).
This is not a region-filtered query — it reads as an unfiltered "every archived
product of this instrument" pull. Downloading further items from the same three
carts adds more independently-selected orbits; it does not converge toward
overlap, because nothing about the selection targets a shared location.

**Measured download rate at the time of this check: ≈2.6 MB/s combined across
three simultaneous transfers** (sampled over 12.4s on the three then-active
`wget` processes). At that rate, and with the carts at 500 files each while only
21 have completed (≈16 GB), completing the existing carts is a multi-day,
multi-terabyte transfer with **821 GB of free disk** against a plausible total
in the 1–2 TB range extrapolated from the file sizes seen so far (OHRC ≈750 MB,
TMC-2 ≈500 MB, IIRS 0.75–5.5 GB per product, wildly variable) — it will not
finish before the disk fills even if left running.

**Recommendation, given to the user directly when asked "does this suffice":**
stop pulling from these three carts. They cannot produce a usable cross-sensor
pair regardless of how many more files complete. The fix is a new, targeted
search on PRADAN filtered by a shared ground footprint (a lat/lon or orbit-path
filter) across OHRC, TMC-2 and IIRS, then a cart built from that small
intersecting set — likely single digits to low tens of files per instrument,
not 500.

### 1.2 Field map: 22 of 25 fields verified, 3 still unresolved

**Traces to:** `src/lunar_reg/ingest/fieldmap.py`, `ingest/pds4.py`.

Before today, 10 of 25 fields were marked `Provenance.UNVERIFIED` — guessed from
the documented PDS4 schema, never checked against a product. Running
`lunar-reg probe-label` and then `read_label()` against a real OHRC label
resolved **22 of 25**, including all eight corner coordinates, both sun angles,
and the acquisition times.

Still unresolved, and their real names in the label:

| our field | present in label? |
|---|---|
| `incidence_angle_deg` | **name mismatch** — the label calls it `solar_incidence` (value 83.27) |
| `emission_angle_deg` | not found in this label |
| `phase_angle_deg` | not found in this label |

The `incidence_angle_deg` mismatch is a one-line fix. Whether emission and phase
angles exist in *any* Chandrayaan-2 product is unknown — one label is not
evidence of absence.

**Verified independently:** the declared array is 101,074 lines × 12,000 samples
of `UnsignedByte`, and 101074 × 12000 = 1,212,888,000, which is exactly the
`.img` byte length in the archive. The binary layout interpretation is therefore
cross-validated, not assumed.

### 1.3 RESOLVED — the geometry product is a real coordinate grid, and the
### four-corner homography it replaces was wrong by 639 m

**Traces to:** new `src/lunar_reg/ingest/geometry_grid.py`;
`ingest/overlap.py::geographic_to_pixel_transform` is the thing it supersedes.

Each product bundles `<product>_g_grd_d18.csv` (4.26 MB OHRC, 2.11 MB TMC-2).
Read from its own PDS4 label rather than inferred, it is a `Table_Delimited`
with fields `Longitude, Latitude, Pixel, Scan` — a rectangular grid sampled every
100 pixels and every 100 scan lines, with the final index forced onto the true
image edge. Row counts match the label's declared `records` exactly on all three
products (122,452 / 122,452 / 60,803), and `max(Scan) == lines-1`.

Decisive check: the grid's four extreme corners reproduce the *image* label's
`Refined_Corner_Coordinates` exactly. The four corners the old code fits a
homography to are literally four of these 122,452 points, so the grid is a strict
superset.

**How wrong the old transform was, measured against every real grid point:**

| product | homography median error | in ground distance |
|---|---|---|
| OHRC `…0609041371` | **2554.6 px** (max 3412.8) | **639 m** at 0.25 m/px |
| TMC-2 nadir | 2527.3 px (max 3372.9) | 18.5 km at 5.48 m/px |

The OHRC figure was reproduced independently from the raw CSV with no project
code: 2554.6 px, identical.

The cause is mostly *not* the ground-track bow the old docstring blamed (~106 px
on TMC-2). The footprint is a trapezoid, so `getPerspectiveTransform` invents an
along-track foreshortening that a constant-line-period pushbroom does not have.
A plain least-squares affine on the *same four corners* is better: 2.4× on OHRC
(1082 px), and ~20× on TMC-2 per the implementing agent. **The advantage is
product-dependent; the 20× figure should not be quoted as general.**

`geometry_grid.py` provides `lonlat_to_pixel` as a drop-in. It deliberately
cannot return a 3×3 matrix — the true mapping is not projective — and returns
per-point line/sample with an `inside` mask instead. Points outside the footprint
are reported, never extrapolated. `overlap.py` is untouched; **wiring it in is
still an open decision.**

Still unverified, and marked in the code where it matters:

- **Datum and longitude convention.** The label says "selenographic coordinates"
  with no `unit` element and no coordinate-system element. Planetocentric vs
  planetographic, and the reference radius, are not stated. This matters
  specifically for mixing these with LRO products.
- **The bilinear within-cell interpolation model** is a choice, not documented.
  Round-trip error of 2e-9 px at nodes measures self-consistency, not agreement
  with the true optical geometry between nodes. No ground truth exists to
  measure that against.
- Antimeridian wrap has never executed on real data (no inspected product wraps).

**Bug found in ISRO's own data:** the TMC-2 geometry label declares
`file_size 2111975` while the file is 2111886 bytes — and its `md5_checksum`
matches. The size field is wrong, the data is fine. Diagnostics report it without
treating it as corruption.

### 1.3b FIXED — the manifest discarded the real corners

**Traces to:** `src/lunar_reg/ingest/manifest.py::COLUMNS`.

Found while verifying the polar fix. `read_label` resolved all eight corner
coordinates correctly, and then the manifest reduced them to a lat/lon bounding
box and dropped them. `footprint_from_row` therefore took its bbox fallback on
every real product, and a rotated pushbroom strip does not fit its box:

| product | from corners | from bbox | inflation |
|---|---|---|---|
| OHRC ×3 | 78.89 / 78.96 / 79.33 km² | 308.99 / 323.57 / 333.45 km² | **3.9–4.2×** |
| TMC-2 ×3 | 16,041 / 17,805 / 17,843 km² | 37,137 / 38,891 / 39,067 km² | **2.2–2.3×** |

So every overlap area computed from a manifest — the production path — was two
to four times too large. The corners are now carried through as
`corner1_lat … corner4_lon`; the box is retained because it is still the only
geometry available when a label resolves no corners. Suite stayed green.

### 1.4 The download will not fit on disk

**Traces to:** operational, not a module.

PRADAN issues download *scripts* carrying a live session cookie, not data. Four
were generated, each listing **500 products**:

| cart | products | observed size per product |
|---|---|---|
| `ohrc_*.sh` | 500 | ~591 MB zipped, 1.21 GB extracted |
| `tmc2_*.sh` | 500 | ~245–375 MB zipped, 1.18 GB extracted |
| `iirs_*.sh` | 500 | ≥927 MB zipped (never completed one) |
| `iirs_*.py` | 500 | **byte-identical product list to the `.sh`** (500/500 paths match) |

Rough total for the three distinct carts: **~975 GB zipped** against **830 GB
free**, before extraction, which roughly doubles it. It cannot complete.

**Current actual state:** downloads have stopped (no `wget` processes running).
6.6 GB fetched: **5 complete products** (2 OHRC, 3 TMC-2) and 3 partial. No IIRS
product completed. Whether they stopped from session expiry, rate limiting, or
the system's out-of-memory killer is **not established** — the OOM killer did
take the Streamlit and Vite servers during this period.

### 1.5 TMC-2 "products" are not distinct scenes

**Traces to:** would affect `ingest/overlap.py` pair counting.

The TMC-2 filenames carry a camera code: `ch2_tmc_nca_…`, `ncf`, `ncn`, `nrn`
appear for the *same* timestamp `20260813T0627378557`. TMC-2 is a tri-stereo
instrument (fore/nadir/aft). So `nca`/`ncf`/`ncn` are almost certainly
aft/fore/nadir looks at one scene and `nrn` a raw counterpart.

**CONFIRMED from the labels, no longer inference.** All three downloaded TMC-2
products report an identical `sun_elevation` of 50.935114 and near-identical
corner longitudes (142.69–142.80), i.e. one scene viewed three ways. So 500
TMC-2 "products" is nearer 125 scenes, and any coverage count computed
per-product overstates distinct coverage by roughly 4×.

### 1.6 No LRO reference data has been fetched

**Traces to:** `src/lunar_reg/ingest/lro.py` — written, never run on a real product.

The LRO NAC/WAC PDS archive is public and needs no login; three mirrors were
confirmed reachable today (HTTP 200). Nothing has been downloaded. **Every
"registration" the project has performed is Chandrayaan-2-shaped synthetic data
against Chandrayaan-2-shaped synthetic data** — the cross-mission case the
problem statement actually asks for has never been exercised.

### 1.7 IIRS has never been touched by any real data path

`src/lunar_reg/preprocess/hyperspectral.py` and the band-reduction design in
`docs/CROSS_MODAL_IIRS.md` have never seen a cube. No IIRS product finished
downloading. Everything about IIRS in this repo is design, not result.

---

## 2. Result issues

### 2.1 Every headline number is synthetic

**Traces to:** `src/lunar_reg/eval/scenes.py`, `scripts/build_demo_results.py`.

All 26 registered pairs in `data/processed/results/` were produced on generated
terrain: a fractal height field with stamped craters, rendered under controlled
sun angles with ray-marched cast shadows. The results carry `synthetic=True` and
both the Streamlit tool and the website display that prominently.

What the synthetic scenes deliberately omit: real lunar photometry (the Moon is
strongly backscattering, closer to Hapke than the Lambertian model used), the
opposition surge, albedo independent of topography, detector noise and MTF, and
pushbroom geometry. **Rankings between methods should transfer; absolute numbers
should not be quoted as lunar performance.**

### 2.2 The conventional RMSE is not registration accuracy — by 12.7× to 58.6×

**Traces to:** `src/lunar_reg/eval/metrics.py` vs `eval/error_budget.py`.

Across all 26 pairs, the self-residual RMSE (the fit's residual on the same
points that produced it) and the true error against the known transform disagree
by **12.7× to 58.6×**. On one same-illumination ASIFT pair: 0.4354 px reported,
0.0115 px true.

This matters beyond our own reporting — see §2.3.

### 2.3 Makharia et al. cannot be compared against, and this is unresolved

**Traces to:** `docs/MAKHARIA_PARITY.md`.

arXiv:2509.04775 is the closest published work and benchmarks the same
algorithms on real Chandrayaan-2 data. Its §4.7.1 defines RMSE over "matching
control points in both the reference image and the transformed warped image" —
the points the transform was fitted from. That is the self-residual of §2.2.

Their *ranking* of five algorithms is sound. Their numbers are not comparable
with a truth-based figure, so this repo deliberately does **not** place them
side by side. Additionally, 5 of their 10 preprocessing steps carry no parameter
values in the paper (CLAHE clip limit, CLAHE tile grid, PCA components, dilation
kernel, shadow-normalisation method), so parity cannot be established even in
principle from the publication.

**One caution about their data:** their Table 3 row for DFSAR–SELENE Polar is
identical to OHRC–NAC Polar in all three figures to four decimal places
(0.9234 / 0.7586 / 4.643). That is almost certainly a duplicated cell.

### 2.4 Synthetic ground truth refuses to produce a confidence total, correctly

**Traces to:** `src/lunar_reg/ingest/pseudo_gt.py` (`estimate_confidence`).

Correspondences can be generated for any overlapping pair from georeferencing
alone, uniformly distributed by construction. The error budget deliberately
returns **`None`** for the total rather than a number, because three terms are
unestablished: absolute pointing accuracy, corner-transform model error, and
corner ordering.

Known floor from pixel quantisation alone: **23.09 m**, which is **92 OHRC
pixels**. Even if the three unknown terms were zero, this ground truth is two
orders of magnitude away from the sub-pixel requirement. It is usable as a
training or initialisation signal, never as an evaluation reference.

**Note:** one of those three unknown terms — corner ordering — is no longer
unknown as of §1.1. It is wrong. The budget has not been updated to reflect that.

A trap is guarded explicitly: `loop_closure_residual_m` is tautologically zero,
because correspondences are defined *through* lat/lon so any check routed through
lat/lon closes perfectly regardless of georeferencing error. There is a test
asserting it stays near zero with both footprints displaced 5 km, so it can never
be misread as validation.

### 2.5 The uniformity metric is a weak proxy and was demoted

**Traces to:** `src/lunar_reg/eval/uniformity.py`, `eval/conditioning.py`.

`U = √(coverage × entropy)` correlates with true extrapolation error at Spearman
**−0.52**, and fails in both directions on realistic layouts: it *rejects*
border-only (U 0.590) and hollow-ring (U 0.621) layouts that are among the
best-conditioned tested (0.109 and 0.213 px true error), and *passes* a sparse
lattice at a perfect U 1.000 that is 3–5× less precise than a dense grid.

A bootstrap conditioning measure correlates at **+0.78** and is what the pipeline
now gates on. U is retained as a descriptive diagnostic only.

**Stated limitation:** conditioning measures precision, not accuracy. A
correlated error — the ECC illumination bias in §2.6, or a systematic
georeferencing offset — leaves it small while the answer is wrong.

### 2.6 The refinement stage, not the matcher, sets the accuracy floor

**Traces to:** `src/lunar_reg/align/refine.py`.

Four different matchers on one pair converge to an *identical* final error
(0.011 px at 0° sun azimuth difference, 0.092 px at 15°, 0.304 px at 30°)
despite starting from RANSAC fits differing by an order of magnitude.

Local-contrast normalisation before ECC cuts the 30° error **4.8×** (0.299 →
0.062 px median), winning 100% of runs over 6 seeds × 2 matchers once
illumination differs — but *losing* by ~0.02 px when it does not.

**Unresolved:** selecting the prefilter automatically from image statistics
**failed**. Normalised cross-correlation falls both for illumination change and
for sensor noise, and the correct response is opposite in each case; it chose
wrongly on a same-illumination noisy pair (NCC 0.917, prefiltered, 0.0498 px
where plain intensity reached 0.0175 px). The `"auto"` mode ships **disabled and
documented as defective**. Selection currently requires sun-angle metadata.

### 2.7 Classical matchers fail outright past ~30° of sun azimuth change

**Traces to:** `src/lunar_reg/eval/error_budget.py`, `eval/scenes.py`.

SIFT recovers 228 geometrically correct matches at 15° azimuth difference, **4 at
30°, and 0 at 60°**. Shadow fraction moves independently and does not predict the
collapse. Adding illumination-invariant albedo texture did not rescue it.

10 of 36 pipeline runs did not register at all: 9 returned too few
correspondences, 1 too few inliers after RANSAC. These are classified outcomes,
not crashes.

### 2.8 VRAM figures are host-memory proxies, not device measurements

**Traces to:** `src/lunar_reg/match/benchmark.py`, `match/memory.py`, `device.py`.

LoFTR fp32 breaks between 1024 and 1152 px; LightGlue between 1536 and 2048 px.
The failing allocation at 1152 px is 1,719,926,784 bytes, and ((1152/8)²)² × 4 is
1,719,926,784 exactly — the coarse score matrix, confirmed rather than assumed.

**But:** this machine's NVIDIA kernel module is not loaded and PyTorch is a
CPU-only build, so these are host RSS figures. The break points come from an
address-space cap, which is stricter than VRAM. Absolute RTX 4060 headroom is
**unmeasured**. The fp16 factor is likewise **not measured** — CPU bf16 autocast
is emulated on this host and did not complete a single 512 px pass in 15 minutes.

Correcting the model was itself a finding: an earlier pure-S⁴ cost model
underestimated 1024 px by ~4× and would have handed out tile sizes that OOM.

### 2.9 No learned matcher has ever run on a GPU

LoFTR, LightGlue and the SuperGlue wrapper are implemented and load correctly on
CPU. None has produced a result on a GPU. SuperGlue additionally **cannot ship**:
its weights are noncommercial-research-only and
`match/superglue.py` raises `PermissionError` unless explicitly acknowledged.
LightGlue (Apache-2.0) is the shippable substitute and is a different model, so
it would not reproduce Makharia et al.'s headline number in any case.

### 2.10 Test suite could not be re-verified in this session

378 tests passed on the last successful full run. Today's run was **killed by the
out-of-memory killer** (exit 137) while three concurrent downloads were active.
The 378 figure is carried forward from the previous run, not re-confirmed.

---

## 3. Decisions that need a human

These are judgment calls, not implementation choices. Each is genuinely open.

1. **How much archive data to actually pull.** ~975 GB will not fit in 830 GB
   (§1.4), and 500 arbitrary products per instrument is not obviously what the
   project needs — overlap is decided by footprint, not by count. A targeted pull
   over one region would likely serve better. This is a scope and cost decision.

2. **Whether to keep the raw zips after extraction.** Extraction roughly doubles
   footprint (591 MB → 1.21 GB for OHRC). Deleting zips saves half but forfeits
   re-extraction without re-downloading through an expiring session.

3. **Whether the 23.09 m pseudo-ground-truth floor is acceptable** for its
   intended use (§2.4). It is 92 OHRC pixels. Using it to pre-train or initialise
   is defensible; using it to *evaluate* is not. Where the line sits is a
   research-standards call.

4. **Whether to ship with `incidence_angle_deg` / `emission_angle_deg` /
   `phase_angle_deg` unresolved** (§1.2), or hold for a product that carries
   them. They are not currently used by any matcher, so this may be acceptable.

5. **Whether to invest in parsing the geometry CSV** (§1.3). It could replace the
   four-corner homography approximation with real per-line geometry — likely the
   single largest available accuracy improvement — but it is unscoped work
   against an unexamined format.

6. **Whether to accept SuperGlue's noncommercial licence** to reproduce Makharia
   et al.'s comparison (§2.9), or stay with LightGlue and forgo direct
   comparability. This has implications for what can be claimed and shipped.

7. **Which preprocessing parameter set to standardise on.** 11 of 14 parameters
   in `preprocess/params.py` are `PLACEHOLDER` — reasonable defaults, not
   paper-matched, because the paper does not state them (§2.3). Tuning them on
   synthetic data risks overfitting to a shading model that is not the Moon.

8. **Whether the synthetic-only result set is acceptable for the internal
   round**, or whether submission should wait for real registered pairs.

---

## 4. Current key metrics

| Metric | Value | Provenance |
|---|---|---|
| Tests passing | **431** (1 skipped) | verified on the combined tree, lint clean |
| Pipeline pairs registered | 26 of 36 | `scripts/build_demo_results.py`, synthetic |
| Classified failures | 9 too-few-matches, 1 too-few-inliers | same run |
| Self-residual vs true RMSE | 12.7× – 58.6× | 26 pairs, synthetic |
| Best true RMSE | 0.0115 px | same-illumination ASIFT, 11,040 inliers, synthetic |
| Uniformity U vs true error | Spearman −0.52 | 11 synthetic layouts |
| Bootstrap conditioning vs true error | Spearman +0.78 | same 11 layouts |
| ECC prefilter gain at 30° azimuth | 4.8× (0.299 → 0.062 px) | 6 seeds × 2 matchers, synthetic |
| SIFT correct matches vs azimuth | 228 @ 15°, 4 @ 30°, 0 @ 60° | synthetic |
| LoFTR fp32 tile break | between 1024 and 1152 px | host RSS under 8 GB address cap |
| LightGlue tile break | between 1536 and 2048 px | same |
| Pseudo-GT error floor | 23.09 m = 92 OHRC px | computed; total refuses to resolve |
| Field map resolution | 22 of 25 | **one real OHRC label** |
| Geometry fields promoted to VERIFIED | 11 of 13 | same label; 2 genuinely absent |
| Real OHRC footprints rejected as POLAR | **0 of 3** (was 3 of 3) | fixed by the polar frame, §1.1b |
| Real OHRC pairwise overlap area | 69.30 / 65.97 / 74.22 km² | Monte-Carlo agreed within 2σ = 0.16 km² |
| Real OHRC footprint area | 78.89 / 78.96 / 79.33 km² | matches ~75 km² expectation |
| Real TMC-2 footprint area | 16,041 / 17,805 / 17,843 km² | mid-latitude, `ok` status |
| Real products complete | 5 (2 OHRC, 3 TMC-2) | 6.6 GB on disk |
| Real IIRS products | 0 | none completed |
| Real LRO products | 0 | never fetched |

---

## 5. What exists

**Python package** `src/lunar_reg/` — `ingest/` (PDS4 label reading, field map
with per-field provenance, footprint overlap on the lunar sphere, pseudo ground
truth, a `probe-label` introspection command), `preprocess/` (ablatable
Makharia-style chain), `match/` (SIFT/ASIFT/AKAZE, a clean-room RIFT2, LoFTR,
LightGlue, a licence-gated SuperGlue, tiled inference with overlap-aware
stitching), `align/` (MAGSAC++, inlier refit, ECC with the local-contrast
prefilter), `eval/` (metrics, uniformity, bootstrap conditioning, stage-by-stage
error attribution, synthetic scene generator), plus `results.py` per-pair
persistence and `pipeline.py` end-to-end runner.

**Streamlit tool** `dashboard/app.py` — the live instrument, reads the result
store directly.

**Showcase site** `web/` — React Three Fiber + Motion, four pages, light/dark
themes, background traced from real LOLA lunar elevation data. Design system
documented in `web/DESIGN.md`. Deliberately outside the Python package.

**Documents** — `docs/CROSS_MODAL_IIRS.md` (IIRS architecture, every claim tagged
paper / measured / extrapolation / unverified), `docs/MAKHARIA_PARITY.md`,
`docs/REPORT_SECTION.md`, `docs/DEMO_SCRIPT.md`, `docs/VRAM_CONSTRAINTS.md`.

## 6. Immediate next actions, in dependency order

Done since this document was first drafted:

- ~~Fix corner ordering~~ — retracted, there was no bug (§1.1); a regression test
  now pins the traversal so it cannot be broken later.
- ~~Rename `incidence_angle_deg`~~ — done. ISRO calls it `solar_incidence`; the
  original guess silently resolved to `None`.
- ~~Promote verified fields~~ — done. 11 of 13 geometry fields are now
  `VERIFIED`; the provenance guard test was inverted rather than deleted, so it
  still fails on an unjustified promotion *or* an unexplained demotion.
- ~~Resolve the corner-ordering term in the pseudo-GT error budget~~ — done.
  Down from three UNKNOWN terms to two; the total still correctly refuses to
  resolve.

Outstanding:

- ~~Polar footprint handling~~ — **done** (§1.1b). All three real OHRC products
  now validate `ok` and produce correct overlaps.
- ~~Parse the geometry CSV~~ — **done** (§1.3), and it exposed a 639 m error in
  the transform it replaces.
- ~~Build the first real manifest~~ — **done**. 6 real products, all footprints
  resolved, first real overlap run complete (§4).

Outstanding:

1. **Wire `geometry_grid.lonlat_to_pixel` into `overlap.py`** in place of the
   four-corner homography. The measurement justifying it exists (§1.3); the
   change itself has not been made, because it alters every crop the pipeline
   produces and should be a deliberate call.
2. **Select a target region and re-download against it** (§1.1c, §1.4). Requires
   a human decision on scope, and blocks everything cross-sensor.
3. **Fetch matching LRO NAC coverage** for that region. Public, no credentials,
   three mirrors confirmed reachable.
4. **Decide the datum question** (§1.3) before mixing Chandrayaan-2 geometry with
   LRO products.
5. Minor: a same-sensor overlap scan compares each product with itself and
   counts each pair twice (3 products gave 9 "pairs": 3 self-pairs + 3 real pairs
   in both orderings). Harmless for reporting, wrong for any count of distinct
   overlaps.
