# lunar-reg — Illumination-Robust Multi-Sensor Lunar Image Registration

**SIH26166 · ISRO · Team Severed Department, IIIT Bhubaneswar**

Finds correspondence points between a Chandrayaan-2 source image (OHRC, TMC-2, or
IIRS) and a lunar reference image (LRO NAC, SELENE TC), estimates a geometric
transform, and produces a registered product plus the accuracy metrics the
problem statement asks for.

The design constraints that shape everything here:

- **Illumination.** Sun azimuth and elevation differ between acquisitions, so the
  same crater looks different. Handled in `preprocess/` — shadow suppression then
  CLAHE, the combination Makharia et al. found strongest on exactly this data.
- **Scale.** OHRC to TMC-2 is a 20× ratio; OHRC to IIRS is 320×. Handled in
  `preprocess/resample.py` by resampling to a common grid before matching.
- **Modality.** IIRS is a 256-band hyperspectral cube being matched against
  panchromatic optical. This is the genuinely open case — see *Known gaps*.
- **8 GB of VRAM.** Pervasive. See [`docs/VRAM_CONSTRAINTS.md`](docs/VRAM_CONSTRAINTS.md).

---

## Layout

```
src/lunar_reg/
  constants.py     lunar datum, per-sensor GSD/band specs, scale ratios
  device.py        CUDA detection and the VRAM budget model
  cli.py           `lunar-reg env | inspect | register`
  ingest/          PDS4/PDS3 label reading, product manifest, footprint, tiling
    fieldmap.py    label element -> manifest column, with per-field provenance
    pds4.py        Chandrayaan-2 PDS4 labels (OHRC, TMC-2, IIRS cubes)
    lro.py         LRO NAC reference products; format detected, not assumed
    manifest.py    scan products into a pandas/Parquet manifest
    probe.py       dump a real label's structure to replace unverified guesses
    overlap.py     footprint intersection on the lunar sphere, and cropping
  preprocess/      the Makharia et al. pipeline, every step toggleable
    params.py      per-parameter provenance: paper-stated vs our placeholder
    config.py      step toggles + the paper's two per-sensor-pair presets
    pipeline.py    orchestrator; records what ran, what was skipped, and why
    georeference.py / resample.py / radiometric.py / shadow.py / hyperspectral.py
  match/           classical (SIFT/AKAZE) and learned (LoFTR, LightGlue) matchers
  align/           robust transform estimation, sub-pixel refinement, block warp
  eval/            RMSE, inlier count/ratio, and the spatial-uniformity metric
  viz/             match, residual, uniformity, and overlay figures
tests/             synthetic-data suite; no GPU or PDS4 products required
configs/           default.yaml — the validated defaults
data/{raw,processed}/   git-ignored
notebooks/
```

The six pipeline stages live under one `lunar_reg` package rather than as
top-level `src/` packages, so that installing this project does not put names
like `match` and `eval` into the global import namespace.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

**OpenCV is pinned `<5` deliberately.** OpenCV 5 removed AKAZE, KAZE and BRISK
from the main module, and `opencv-contrib-python` 5.0.0 does **not** restore them
(verified — an earlier note in this file said it would; that was wrong). AKAZE is
one of the benchmark paper's four classical baselines, so the pin is
load-bearing. Verified working on 4.14.0: SIFT, ASIFT, AKAZE, KAZE, BRISK, ORB.

```python
from lunar_reg.match.classical import available_detectors, paper_baseline_status
available_detectors()     # ('sift', 'asift', 'akaze', 'kaze', 'orb', 'brisk')
paper_baseline_status()   # which of the paper's four this project can run
```

`torch` is pulled in as a plain CPU build by default. For CUDA on the target
RTX 4060 (Ada, `sm_89`), install it explicitly first:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu124
```

Then confirm what the pipeline thinks it is running on:

```bash
lunar-reg env
```

### Setting up another machine

`data/` is git-ignored, so it travels as an archive. On the machine that has it:

```bash
./scripts/pack_data.sh            # -> dist/chandralipi-data-processed-<date>.tar.zst
```

Then on the new machine, `git clone` and:

```bash
./scripts/setup.sh --data /path/to/that/archive   # venv -> deps -> data -> verify
./scripts/run_dashboard.sh
```

`scripts/README.md` has the options (`--cuda`, `--results-only`, `--full`, …).

## Use

```bash
# What device and tile budget will this machine use?
lunar-reg env

# Summarise a product and show what a naive full load would cost.
lunar-reg inspect data/raw/ch2_ohr_ncp_20210331.xml

# Register a source against a reference and emit a JSON metrics report.
lunar-reg register data/raw/source.xml data/raw/reference.xml \
    --matcher loftr --model homography --output outputs/report.json
```

Library use follows the same stage order:

```python
from lunar_reg.ingest import open_product
from lunar_reg.preprocess import standard_chain
from lunar_reg.match import LoFTRMatcher, TiledMatcher
from lunar_reg.align import estimate_transform, reestimate_on_inliers
from lunar_reg.eval import compute_metrics, compute_uniformity

matcher = TiledMatcher(LoFTRMatcher())          # tile size derived from free VRAM
with open_product(src_label) as src, open_product(ref_label) as ref:
    result = matcher.match_datasets(src, ref, preprocess=standard_chain)

transform, result = estimate_transform(result, "homography", threshold_px=2.0)
transform, result = reestimate_on_inliers(result, threshold_px=1.0)   # sub-pixel pass

print(compute_metrics(result, transform).as_dict())
print(compute_uniformity(result.inliers().src_pts, (src.height, src.width)).as_dict())
```

## Product ingest and the metadata trust boundary

Build one manifest across both archives:

```bash
lunar-reg manifest --chandrayaan2 data/raw/ch2 --lro data/raw/lro \
    --output data/processed/manifest.parquet
```

Both scanners emit the same schema, so the frames concatenate; `archive`
distinguishes them. Columns cover identity, array structure (`lines`, `samples`,
`bands`, `axis_order`, `data_type`), acquisition time, illumination angles, and
a footprint bounding box.

**Not all of those columns are trustworthy yet, and the manifest says which.**
No real Chandrayaan-2 or LRO product has been inspected by this project. The
split is:

| Layer | Status |
|---|---|
| PDS4 array structure — sizes, dtype, axis order, data file name | **Verified.** Documented schema, and cross-checked by hand-writing labels that GDAL's own PDS4 driver reads back correctly. |
| PDS3 keyword parsing for LRO | **Verified** the same way against GDAL's `PDS` driver. Parsing is generic — it captures every keyword rather than looking for invented ones. |
| Time coordinates, identification | Documented PDS4; standard element names, presence per-product not guaranteed. |
| **Sun azimuth/elevation, incidence/emission/phase, footprint corners** | **Unverified guesses.** These live in discipline-dictionary and mission-specific namespaces that vary per mission. |

Every mapped field carries a `Provenance` (`lunar-reg fields` prints the
breakdown), the loader records which candidate path actually matched, and the
manifest carries `geometry_resolved` / `footprint_resolved` / `unresolved_fields`
columns. Filter on `geometry_resolved` before using any sun-angle column, and
never report a sun-angle-conditioned result from rows where it is `False`.

### Replacing the guesses with fact

The moment you have one real product, run:

```bash
lunar-reg probe-label data/raw/ch2/<product>.xml --suggest
```

It dumps the label's actual element tree, groups elements that look like
illumination / coordinate / time values, and emits a ready-to-paste
`GEOMETRY_FIELDS` block using the real paths. Paste it over the UNVERIFIED
section of `ingest/fieldmap.py`; the loader and manifest pick it up with no other
change. Fields genuinely absent from the label are flagged `NOT FOUND` rather
than filled in.

### Two ingest hazards worth knowing

1. **Always open the label, never the `.IMG`.** GDAL maps the `.img` extension to
   the ERDAS `HFA` driver, not to a planetary one. `open_product` and
   `open_lro_product` recover the sibling label if handed a binary.
2. **Never assume a cube's band interleave.** `axis_index_order` plus the
   `Axis_Array` sequence defines it, and reading a band-sequential cube as
   band-interleaved returns wrong pixel values with **no error at all** —
   confirmed against GDAL during development. The loader surfaces `axis_order`
   rather than defaulting.

## Footprint overlap and cropping

Pair products by ground footprint before any pixel work, following the
MoonMetaSync approach — polygon clipping on the lunar sphere via pygeodesy,
driven with the lunar radius rather than an Earth ellipsoid:

```bash
lunar-reg overlap data/processed/manifest.parquet \
    --source-sensor OHRC --reference-sensor TMC2 \
    --output data/processed/pairs.parquet \
    --crop-dir data/processed/crops
```

Matched pairs carry the overlap polygon as WKT (`lon lat` axis order, so it
drops straight into QGIS or shapely), its area in km², and the fraction of each
side covered. Cropping uses a windowed read, so an OHRC strip is never fully
loaded — only the overlap window comes off disk.

### Polar footprints

Every real OHRC product downloaded so far sits at about −85° latitude, where a
lat/lon polygon stops describing the ground: meridians converge, so longitude
bounds lose their meaning and a straight edge in lat/lon is not straight on the
Moon. Above `POLAR_LATITUDE_DEG` (80°) a pair is therefore clipped in a
`PolarFrame` — an azimuthal-equidistant plane centred on the relevant pole, in
which the pole is an ordinary point and there is no antimeridian — and the
result is projected back to lat/lon. **Areas are always measured on the sphere,
never in the plane**, so the projection decides only *which* region is shared.

Measured on the three real OHRC labels, footprint areas come out at 78.89,
78.96 and 79.33 km² (physical expectation for a 3 km × 25 km strip: ~75 km²),
and the three pairwise overlaps at 69.30, 65.97 and 74.22 km². Each was
cross-checked against an independent Monte-Carlo integration on the sphere and
agreed to within its 2σ noise of ~0.16 km².

### Nothing is silently skipped

Every candidate pair is classified, counted, and given a retained sample:

| status | meaning |
|---|---|
| `ok` | usable overlap polygon |
| `disjoint` | clean non-overlap — normal, not flagged |
| `touching_only` | polygons abut but enclose no area |
| `degenerate_empty` | clipper returned fewer than 3 vertices |
| `degenerate_sliver` | negligible area or extreme aspect ratio |
| `polar_extent_unsupported` | a polar pair reaches too far from its pole for the polar frame to be trusted |
| `polar_bbox_unusable` | a polar footprint given only as a lat/lon box whose longitudes wrap — needs corners |
| `antimeridian` | longitude span implies a wrap |
| `invalid_geometry` | non-finite or out-of-range corner |
| `missing_footprint` | no coordinates in the manifest — a *metadata* gap |
| `clip_error` | the clipping library raised |

`intersect()` never raises; it returns a status so the caller can count it. The
report prints on every run, and `lunar-reg overlap` exits non-zero when pairs
were considered but none were usable, so a CI run cannot mistake an
all-degenerate result for success.

`missing_footprint` is called out separately in the report because it is
currently the expected state — the footprint columns come from the unverified
half of the field map. An empty result there means *the metadata has not been
verified yet*, *not* that the products fail to overlap.

### Two things to know before trusting a crop

1. **The pixel mapping is a homography fitted from four corner coordinates.**
   Reasonable for a short TMC-2 frame; an approximation for a 90,000-line OHRC
   pushbroom strip over a curved body, with error growing away from the corners.
   It also depends on corner *ordering*, which is itself unverified — wrong
   ordering yields a mirrored or rotated crop with no error raised.
2. **Windows round outward.** A crop covers every pixel the polygon touches, so
   it may be up to one pixel larger per side than the exact extent. Deliberate:
   carrying a pixel of slop beats silently dropping a row of real overlap.

### A pygeodesy trap worth knowing

`sphericalNvector.areaOf` returns badly wrong values for a **closed** ring (first
vertex repeated at the end) — measured 53× too large for a 10° box and 51,567×
too large for a thin sliver, with the error growing as the polygon shrinks.
`clipFHP4` returns exactly such closed rings, so the obvious composition
`areaOf(clipFHP4(...))` is silently wrong and makes slivers look enormous. This
project strips the closing duplicate *and* uses `sphericalTrigonometry.areaOf`,
which is correct either way. Pinned by `test_area_is_correct_for_closed_rings`.

## Preprocessing (Makharia et al.)

Reproduces the pipeline in arXiv:2509.04775 §4. **The paper's full 27-page text
was read for this**, which changed the design in two ways worth knowing.

**It is not one chain.** The paper applies a common core to everything and then
a *different* specialised set per sensor pair:

| | steps |
|---|---|
| core (§4.1) | georeferencing → resolution resampling → intensity normalisation |
| OHRC/NAC (§4.2 A) | CLAHE, image inversion, morphological dilation, PCA |
| IIRS/WAC (§4.2 B) | band selection, histogram matching, shadow normalisation, log transform |

`ohrc_nac_config()` and `iirs_wac_config()` are those two tracks; mixing steps
across them is allowed but `describe()` will tell you the run is no longer the
paper's configuration for either pair.

```python
from lunar_reg.preprocess import ohrc_nac_config, run_pipeline, PreprocessContext

result = run_pipeline(image, ohrc_nac_config(), PreprocessContext(src_gsd_m=0.25))
print(result.report())        # every step: ran / skipped-and-why / shape / params
```

Every step is independently toggleable, and `ablation_configs()` builds the
leave-one-out sweep:

```bash
lunar-reg preprocess data/raw/ohrc.xml --preset ohrc_nac --src-gsd 0.25 --ablate
```

A step that *cannot* run — georeferencing without a CRS, histogram matching
without a reference — is recorded as skipped **with a reason**, never silently
passed over. A chain that quietly dropped half its steps otherwise looks
identical to one that ran fully.

### Which parameters are actually the paper's

`lunar-reg params` prints this. Short version — the paper specifies the
structure precisely and most numbers not at all:

| stated in the paper | value |
|---|---|
| intensity normalisation target | 8-bit, 0–255 |
| image inversion | exactly `255 - pixel` |
| IIRS → WAC resample target | 100 m/px |
| OHRC → NAC resample target | 0.5–2.0 m/px *(range; 1.0 is our pick)* |
| DFSAR → SELENE resample target | ~9 m/px *(approximation is theirs)* |

**Not stated — placeholders to tune, not paper-matched:** CLAHE clip limit and
tile grid, dilation structuring element shape and size, PCA component count,
shadow method and all its parameters, log transform constant, resampling
interpolation kernel, and which IIRS band is the reference.

`PreprocessResult.uses_placeholders` lists the ones a given run actually
depended on, and `report()` says in as many words that such a run reproduces the
paper's **structure**, not its parameter values. Check it before describing any
result as paper-matched.

### Two things found while implementing shadow normalisation

1. **A percentile threshold overshoots badly on tied values.** Real lunar shadow
   saturates at a handful of low DN values, so a nominal 5th-percentile cut
   selected **9.1%** of pixels on a test scene. `shadow_fraction()` reports what
   the threshold really selected; treat the percentile as a lower bound.
   `estimate_shadow_severity()` uses an absolute darkness level instead, and is
   the right measure for *whether* a scene is an extreme sun-angle case at all.
2. **Normalise within the shadow range, not the full image range.** Doing the
   latter makes the gamma output a tiny fraction of the scale and the step
   *darkens* shadow instead of lifting it — the opposite of the paper's intent.
   The corrected map brightens monotonically and maps the threshold to itself,
   so there is no seam at the shadow boundary for a detector to latch onto.

## Matching, alignment, and metrics

### Classical matchers

`ClassicalMatcher` covers SIFT, ASIFT, AKAZE, KAZE, ORB and BRISK behind the
common `Matcher` interface, so they are interchangeable with the learned matchers
and with `TiledMatcher`. Binary descriptors (AKAZE/ORB/BRISK) are automatically
matched with Hamming distance rather than L2 — using L2 on them doesn't error, it
just silently matches badly.

Measured on a synthetic homography pair (512², 50 craters, 3 px RANSAC):

| detector | matches | inlier ratio | RMSE (px) | time |
|---|---|---|---|---|
| SIFT | 1055 | 0.999 | 0.113 | 0.06 s |
| ASIFT | 9652 | 0.998 | 0.322 | 1.28 s |
| AKAZE | 271 | 0.996 | 0.328 | 0.08 s |
| KAZE | 232 | 0.991 | 0.276 | 0.20 s |
| ORB | 1781 | 0.994 | 0.870 | 0.03 s |
| BRISK | 317 | 0.975 | 0.752 | 0.04 s |

**RIFT2** is a clean-room implementation in `match/rift2/`, built from the papers
because every existing implementation is unlicensed. See below.

### RIFT2 — clean-room, and why

RIFT2 is the fourth classical baseline in Makharia et al. and the most relevant
to the cross-modal OHRC↔IIRS case. Every pre-existing implementation is
unlicensed — the authors' MATLAB (`LJY-RS`, no licence, single commit 2022), a
third-party Python port (`canyagmur`, no licence, single commit 2024, not on
PyPI), and `phasepack` (last release 2016, licence UNKNOWN). No licence means all
rights reserved, so none can be vendored into a submission ISRO may evaluate.

So `match/rift2/` implements it **from the papers only** — arXiv:1804.09493
equations (1)–(17) and arXiv:2303.00319 §III. No unlicensed source was read,
which is what makes this code ours to licence.

The pipeline: log-Gabor bank → per-orientation phase congruency → PC moments
(min = cornerness, max = edges) → Maximum Index Map → RIFT2's dominant-index
recoding → 6×6×6 = 216-d descriptor. All parameters are paper-stated
(`N_o`=6, `N_s`=4, `J`=96, 5000 keypoints, dominant ratio 0.8).

**Why it earns its place.** Under nonlinear radiation distortion, matching a
known homography (probe RMSE against ground truth):

| distortion | SIFT | ASIFT | AKAZE | RIFT2 |
|---|---|---|---|---|
| none | 0.057 | 0.023 | 0.083 | 0.292 |
| **contrast inverted** | **failed to fit** | **797 px** | **329 px** | **0.311** |
| gamma 3.0 | 0.295 | 0.086 | 0.203 | 0.369 |
| non-monotonic map | 0.124 (52 matches) | 0.086 (117) | **failed** | 0.635 (897) |

Under contrast inversion RIFT2 is the *only* matcher that works — the others
don't just degrade, they return confidently wrong transforms. On same-modality
pairs SIFT/ASIFT are more accurate, so use those there; RIFT2 is for the
cross-modal case.

**Validation status.** The dominant-index recoding reproduces the worked
histogram example printed in the RIFT2 paper exactly. Parameters are
paper-stated. The invariance properties are verified by test. But it has **not**
been checked against the authors' MATLAB output — doing so would mean running the
unlicensed code this exists to avoid. Describe results as "RIFT2 as specified in
the papers", never as "reproducing published RIFT2 numbers". One known deviation:
the papers use nearest-neighbour matching plus an outlier filter; this uses a
Lowe ratio test, which neither paper specifies.

### Sub-pixel refinement

`refine_full()` runs the recommended chain: refit on inliers at a tight
threshold, then ECC intensity refinement. Measured against a known homography
with sensor noise, probe error across the image:

| stage | probe RMSE | max |
|---|---|---|
| RANSAC @3 px | 0.0480 | 0.1164 |
| + refit on inliers @1 px | 0.0457 | 0.1032 |
| + ECC | **0.0177** | **0.0547** |

Two findings worth knowing:

1. **Don't run `cornerSubPix` on SIFT/ASIFT/AKAZE/KAZE keypoints.** It made probe
   error *four times worse* (0.0146 → 0.0577). Those detectors already localise
   to sub-pixel precision — 100% of their keypoints have non-integer coordinates,
   versus 0% for FAST. `cornerSubPix` re-localises onto the nearest *corner*, and
   craters are blobs. `refine_matches()` refuses by default for these detectors;
   pass `force=True` to override.
2. **ECC's direction convention is a trap.** Three of the four plausible
   argument arrangements are wrong, two catastrophically (~48 px error), and
   **the returned correlation coefficient does not distinguish them** — a 48 px
   result reported a *higher* `cc` than the correct one. The verified-correct
   arrangement is template = reference, input = source, initial warp =
   `inv(src→ref)`, result inverted.

### The spatial-uniformity metric

**Proposal.** Report `coverage` C, normalised `entropy` H, and Clark–Evans `R`,
with headline score **U = √(C · H)**.

**Why it's needed at all: RMSE cannot see this failure.** Six point layouts, each
with 400 points and identical 0.5 px noise, so only the distribution differs:

| layout | fit RMSE | error at probes | worst case |
|---|---|---|---|
| grid (even) | 0.698 | 0.049 | 0.114 |
| uniform random | 0.699 | 0.071 | 0.142 |
| one quadrant | 0.701 | 0.309 | 0.768 |
| two clusters | 0.705 | 0.390 | 1.092 |
| diagonal band | 0.717 | 0.999 | 2.393 |
| tight blob | 0.724 | 1.653 | **5.861** |

Fit RMSE is essentially constant (0.698–0.724). True error away from the matched
points spans **51×**. A clustered solution reports sub-pixel RMSE while being
~6 px wrong elsewhere in the same image — so RMSE alone cannot substantiate a
whole-image sub-pixel claim. U ranks these layouts in the same order as their
worst-case error (Spearman **−0.83**).

**Why all three components:**

- *Coverage alone fails*: 64 occupied cells with 5000 points in one and 1 in each
  other gives C = 1.0 — looks perfect. Entropy = 0.03 catches it.
- *Entropy alone fails*: four cells at 25% each, 60 empty gives H = 0.33 —
  unalarming. Coverage = 0.06 is emphatic. The two respond sharply to different
  failures, which is why U multiplies them (geometric mean, so a near-zero in
  either drags the score down rather than being averaged away).
- *Both grid metrics are blind inside a cell.* Measured: 512 points as 64 tight
  blobs, one per cell, score C = 1.00, H = 1.00, **U = 1.00** — indistinguishable
  from ideal — while Clark–Evans gives **R = 0.10**, correctly reporting severe
  clustering.

**`R` is reported but deliberately not gated on.** Real detectors always clump at
fine scale, because keypoints concentrate on textured structure — measured inlier
sets gave R = 0.63 (SIFT), 0.29 (ASIFT), 0.32 (AKAZE), 0.24 (RIFT2), all with
healthy coverage. An earlier version folded R into the gate at R < 0.7 and
consequently **rejected every real result**; worse, the pathological blob case
sits at R = 0.20, overlapping real output, so no threshold separates them
cleanly. The actionable signal is *disagreement* — a high U contradicted by a low
R — exposed as `grid_contradicted_by_neighbours`. The gate itself uses U alone,
which is the part validated against extrapolation error.

In practice on the benchmark above: SIFT, ASIFT and RIFT2 pass the gate; AKAZE
fails at U = 0.61 because its coverage is only 0.53 — it leaves half the grid
empty, which is exactly the failure the metric exists to catch.

**Default grid g = 8** gives 64 cells, 8× the 8 degrees of freedom of a
homography — the metric is about transform conditioning, so cell count should
comfortably exceed the parameter count being constrained. `uniformity_profile()`
reports across 4/8/16 because uniformity is scale-dependent.

## Metrics

The problem statement names RMSE, inlier match count, and inlier ratio;
`eval/metrics.py` reports those plus MAE, median, p95, and max residuals. The
p95 matters: a sub-pixel mean with a six-pixel tail is not sub-pixel
registration, and `RegistrationMetrics.is_subpixel` requires both to clear 1 px.

`eval/uniformity.py` adds the spatial-distribution measure the problem statement
asks for but does not define — grid **coverage**, normalised **entropy**, and
**coefficient of variation** of per-cell match counts. All three are reported
because coverage can read 1.0 while the counts are badly skewed, and entropy can
look healthy while a whole quadrant is empty.

## Data

- **CH2Browse** (`chmapbrowse.issdc.gov.in`) — map-based browse and download, no
  PRADAN login step. Confirmed for OHRC; **not yet verified for TMC-2 and IIRS**.
- **PRADAN** (`pradan.issdc.gov.in/ch2`) — the full archive; free registration.
- **LROC PDS** (`pds.lroc.im-ldi.com`) — LRO NAC reference imagery, public.
- **JAXA DARTS** (`darts.isas.jaxa.jp/planet/pdap/selene`) — SELENE TC, an
  independent third reference.

Products are git-ignored. Any report or publication using Chandrayaan-2 data must
carry the ISRO/ISSDC acknowledgement line from the PRADAN Acknowledgement page.

## Known gaps

These are open, not oversights:

1. **IIRS ↔ optical is unsolved here.** `preprocess/hyperspectral.py` reduces the
   cube to one plane by VNIR averaging or band PCA, which is the team's stated
   plan and a reasonable baseline. Published work (XoFTR, MINIMA, MapGlue)
   suggests it will not close the modality gap alone.
2. **No ground-truth correspondences exist for OHRC ↔ IIRS.** RMSE against that
   pair is currently unmeasurable; weak ground truth has to be constructed, via
   independently georeferenced overlap or synthesis, before the number means
   anything.
3. **Polar footprints.** `ingest/footprint.py` intersects axis-aligned lat/lon
   boxes, which is wrong near the poles where longitude wraps — and the poles are
   where the interesting OHRC targets are. Polar pairs need a stereographic
   reprojection first.
4. **Tile pairing uses a translation-only prior.** `TiledMatcher` locates the
   reference window by an offset, so a pair with significant rotation or scale
   residual after resampling needs a coarse whole-image alignment pass first.

## References

Makharia et al., *Comparative Evaluation of Traditional and Deep Learning Feature
Matching Algorithms using Chandrayaan-2 Lunar Data*, arXiv:2509.04775 (2025) —
the benchmark and preprocessing recipe this pipeline follows. Full list in
`context-PS.md` §6.

## Browsing results: the dashboard

Every registered pair is persisted by `lunar_reg.results` and browsable.

```bash
python scripts/build_demo_results.py     # run the pipeline, populate data/processed/results
streamlit run dashboard/app.py           # browse it
python scripts/demo.py --case hard-30deg --matcher asift   # single-pair demo + figures
```

The dashboard shows, per pair: the correspondence lines with inliers and
RANSAC-rejected matches distinguished; RMSE, inlier count, inlier ratio and both
extra metrics; a checkerboard / blend / anaglyph overlay toggle; and a map of
where the registration is actually constrained. Filter and sort by sensor,
matcher, or any metric threshold.

### Storage schema

```
data/processed/results/
  index.parquet          one flat row per pair: ids, sensors, matcher, every metric
  pairs/<pair_id>.npz    float64 points, inlier mask, transform, preview images
```

Metric groups are prefixed in the index (`m_` accuracy, `u_` uniformity,
`c_` conditioning, `x_` caller extras) because `rmse_px` and conditioning's
`p95_px` mean different things and a merge would silently overwrite one.

Point coordinates are stored float64 and never rounded — the whole project is
about sub-pixel accuracy, so storing pixel indices would discard the answer.
Preview images are downscaled for storage and the scale factor is stored beside
them; a viewer that ignored it would draw every point in the wrong place, and
the bug would look like a registration failure.

**Results carry a `synthetic` flag, and the dashboard displays it prominently.**
No Chandrayaan-2 product has been available to this project, so the shipped
result set was computed on generated scenes. The pipeline is real; the lunar
surface is not, and the tool says so rather than letting a viewer assume.

## Two metrics beyond the problem statement's list

The statement asks for RMSE, inlier count and inlier ratio. Measurement showed
those are not sufficient to support its own sub-pixel-across-the-image
requirement.

**Spatial uniformity** `U = sqrt(coverage x entropy)` — a descriptive
diagnostic, deliberately **not** a gate. Stress testing found it wrong in both
directions: it fails border-only and hollow-ring layouts that are among the
best-conditioned tested, and passes a sparse lattice several times less precise
than a dense grid. Spearman against true error: **-0.52**.

**Extrapolation uncertainty**, in pixels (`lunar_reg.eval.conditioning`) —
bootstrap the correspondences, refit, and measure how far the predictions
wander. Spearman against true error: **+0.78**. Not gameable by arranging points
to satisfy a grid, and it renders as a map of where the answer can be trusted.
This is what the pipeline gates on. It measures precision, not accuracy: a
correlated error leaves it small while the answer is wrong, so it is reported
alongside RMSE, never instead of it.

Full stress-test results and the layouts that motivated the change are in
`src/lunar_reg/eval/conditioning.py` and `tests/test_conditioning.py`.

## Further reading

| Document | What it covers |
|---|---|
| `docs/CROSS_MODAL_IIRS.md` | Matching IIRS against panchromatic imagery: architecture, training plan for one RTX 4060, and what is genuinely unsolved. Every claim tagged PAPER / MEASURED / EXTRAPOLATION / UNVERIFIED. |
| `docs/MAKHARIA_PARITY.md` | Why our numbers cannot be placed beside arXiv:2509.04775's, which of their parameters are unspecified, and their IIRS finding that changed our architecture. |
| `docs/REPORT_SECTION.md` | Draft results section for the internal round. |
| `docs/DEMO_SCRIPT.md` | 2-3 minute video narration and shot list. |
| `docs/VRAM_CONSTRAINTS.md` | Measured tiling limits and where dense matching breaks down. |

## Chandralipi — showcase site

A separate React / React Three Fiber front end lives in `web/` — a 3D Moon
homepage, HLD and LLD architecture diagrams, the measured findings with the
papers behind each one, and a browsable view of every registered pair. Its
visual system is documented in `web/DESIGN.md`.

```bash
cd web && npm install && npm run dev
```

It is deliberately outside the Python package: nothing in `src/lunar_reg/`
imports from it, and the pipeline, its tests and the Streamlit tool all run
without Node installed. The Streamlit app remains the live tool; the site reads
a static export refreshed with `scripts/export_web_data.py`. See `web/README.md`.

Soy Pritom Paul de la Durgapur.
