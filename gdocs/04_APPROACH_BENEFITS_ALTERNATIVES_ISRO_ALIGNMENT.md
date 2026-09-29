# 04 · Our approach, its benefits, the alternatives, and alignment with ISRO's requirement

*Audience: a teammate with a CS background, no remote-sensing background. Every
term is defined at first use. Read docs 01 and 02 first.*

**Evidence labels used in this doc.** Because our standing rule is that a cited
result and our own extrapolation must never be stated with the same confidence,
claims below are tagged:

- **[MEASURED]** — a real run in this repository produced this; the module is named.
- **[PAPER]** — demonstrated in a cited external work.
- **[EXTRAPOLATION]** — our reasoning applied to our case; **not tested**.
- **[DOCUMENTED]** — from a standard or mission document we read.
- **[INSERT RESULT]** — a number that a real run has not yet produced. Not guessed.

**New words in this doc**

| word | plain meaning |
|---|---|
| **ingest** | the software step that reads a raw data product from disk and turns it into objects the rest of the pipeline can use. |
| **footprint** | the polygon on the Moon's surface that an image actually covers. Two images can only be registered if their footprints overlap. |
| **preprocessing** | image clean-up applied before matching: contrast adjustment, shadow handling, resampling to a common scale, etc. |
| **homography** | a specific kind of geometric transform — the one that relates two photos of a flat scene taken from different viewpoints. 8 numbers. Wrong model for a pushbroom strip, but a common default. |
| **affine transform** | a simpler transform: rotate, scale, shear, shift. 6 numbers. No perspective. |
| **ECC (Enhanced Correlation Coefficient)** | an algorithm that fine-tunes a transform by directly maximising how well the two images' brightness patterns line up, rather than using discrete match points. This is our sub-pixel refinement step. |
| **ablation** | turning one component off to measure how much it was contributing. Our preprocessing is built so every step can be individually disabled for this. |
| **tiling** | cutting a large image into smaller overlapping squares, processing each, and stitching the results — needed because neural matchers cannot fit a whole strip in GPU memory at once. |
| **VRAM** | the memory on a graphics card. Our target hardware has 8 GB, which constrains tile size. |
| **CNN / transformer** | two neural-network architectures. A CNN slides small learned filters over an image ("what does this patch look like"). A transformer lets every location attend to every other location ("which patch over there matches this patch here"). |
| **pseudo ground truth** | approximate correct match points manufactured from the images' own georeferencing metadata, used as a weak training/initialisation signal when real ground truth does not exist. |

---

## 1. Our approach: one configurable pipeline, classical and neural side by side

The pipeline is a chain of stages. Each stage's output feeds the next, and each
stage is independently configurable.

```
  ingest          read the PDS4 label (never the raw image directly — see §5),
                  extract corner coordinates, sun angles, scale, with a
                  provenance tag on every field

  overlap         compute each image's footprint polygon on the lunar sphere,
                  find which pairs actually overlap, classify the ones that
                  don't (disjoint / touching / metadata missing) — never skip

  preprocess      the Makharia et al. clean-up chain (contrast, shadow handling,
                  inversion, resampling), every step individually toggleable

  match           run one or more matchers to get correspondences:
                    classical:  SIFT, ASIFT, AKAZE, clean-room RIFT2
                    neural:     LoFTR, LightGlue (both pretrained, zero-shot)
                  large images are tiled, matched per tile, and de-duplicated
                  across tile seams

  align           fit a transform to the correspondences with MAGSAC++ (a
                  modern RANSAC variant that is robust to wrong matches),
                  then refit to the inliers only

  refine          sub-pixel refinement with ECC, with a local-contrast
                  pre-filter switched on from sun-angle metadata when the two
                  images' illumination differs

  eval            compute RMSE, inlier count, inlier ratio, spatial uniformity,
                  and bootstrap extrapolation uncertainty; attribute error to a
                  stage using synthetic scenes with known ground truth

  results         save the registered product, the match points, and every
                  metric, per image pair, so a run can be browsed afterwards
```

Two design decisions define the approach:

**(a) Classical and neural matchers are both first-class.** We do not treat the
classical ones as a legacy fallback. The comparison between them *is* scientific
content: it is what turns "neural matchers are better under illumination change"
from an assertion into a measurement. **[MEASURED — `eval/error_budget.py`]** SIFT
drops from 228 correct matches to 0 as the sun moves 60°; that measured collapse
is the argument for the neural path.

**(b) The refinement stage, not the matcher, sets the final accuracy.**
**[MEASURED — `eval/error_budget.py`]** Running four different matchers on the
same image pair, all four converge to an *identical* final error after ECC
refinement (0.011 px at matched sun angle, 0.092 px at 15° difference, 0.304 px
at 30°), even though their raw RANSAC fits differed by an order of magnitude. The
matcher only has to get *close enough* for intensity-based refinement to lock on.
Acting on that: **[MEASURED — `eval/error_budget.py`]** normalising local contrast
before ECC cuts the 30°-sun-difference error **4.8×** (0.30 → 0.06 px median) and
wins in 100% of runs once illumination differs.

---

## 2. Benefits of this approach

| benefit | why it holds |
|---|---|
| **Generic by construction** | matcher, preprocessing steps, and reference target are all configuration. Adding a new matcher is implementing one interface. |
| **Honest about accuracy** | reports *where* in the frame the registration can be trusted (extrapolation uncertainty, rendered as a map), not just an aggregate number that can be gamed by clustering match points. This directly answers the "uniform distribution" clause. **[MEASURED — `eval/uniformity.py`]** |
| **Runs on one consumer GPU** | neural matchers are used pretrained / zero-shot, no training loop. **[MEASURED — `match/memory.py`]** VRAM break points are characterised (dense-tile cap ~1408 px under an 8 GB budget) so tile sizes are derived, not guessed. |
| **Fails loudly** | non-overlapping or unmatchable pairs are classified, counted, and sampled — the operator can tell a data problem from a bug. **[MEASURED — `ingest/overlap.py`]** 9 cross-sensor pairs correctly classified `disjoint`, not silently dropped. |
| **Distrusts its own inputs** | every metadata field and parameter carries a provenance tag; the loader reads the label not the raw image; the pushbroom geometry grid is read from ISRO's shipped file rather than approximated. This caught a 639 m error, a 100%-data-loss polar filter bug, and 4.2× footprint inflation on first contact with real data. **[MEASURED — `ingest/geometry_grid.py`, `ingest/overlap.py`, `ingest/manifest.py`]** |
| **Reproducible and tested** | 431 automated tests, linter clean; every result traceable to a named module and a dated run. |

---

## 3. Other approaches, and why we did not adopt them exclusively

### 3.1 Pure classical (SIFT / ASIFT / AKAZE only)

The simplest option, and the baseline in the closest published work.
**[MEASURED — `eval/error_budget.py`]** It collapses under sun-angle change: 228
correct matches at 15° azimuth difference, 4 at 30°, 0 at 60°. On the Moon,
matched sun angles between two arbitrary archive images are the exception. We keep
these as baselines — the comparison is the point — but a classical-only pipeline
does not meet the requirement.

### 3.2 Pure end-to-end deep learning, trained on lunar data

Attractive on paper. Blocked by two hard facts:

- **[EXTRAPOLATION]** No public dataset of known-correct Chandrayaan-2 ↔ reference
  correspondences exists to train on. **[MEASURED — `ingest/pseudo_gt.py`]** The
  weak substitute we can manufacture from metadata has a **23.09 m** error floor —
  about 92 OHRC pixels — which is fine to *initialise* a coarse matcher but
  cannot supervise sub-pixel accuracy.
- **[MEASURED — `match/benchmark.py`]** / **[EXTRAPOLATION]** Training a
  LoFTR-family model needs roughly 3–4× the memory of inference; on an 8 GB card
  that caps a training tile near 512 px at batch 1–2. Comparable published
  fine-tunes used 8× datacentre GPUs for a day. On our hardware the equivalent is
  weeks. Not on the table for this timeframe.

So we use neural matchers **pretrained and zero-shot**, and treat lunar-specific
training as future work (§3.6).

### 3.3 Commercial / GIS auto-registration (e.g. ArcGIS, ENVI image-to-image)

These tools do exist and do auto-register. Reasons they do not answer SIH26166:

- **[EXTRAPOLATION]** They are tuned for Earth-observation imagery — similar
  modalities, moderate scale ratios, soft atmospheric shadows. Lunar hard-shadow
  inversion and 320× cross-instrument scale gaps are outside their operating
  envelope.
- They are closed and licensed; ISRO asked for a *generic software solution* they
  can run and extend, delivered with the method.
- Their quality reporting is the fitted-points RMSE — the metric doc 02 §4 shows
  is insufficient for the "across the image" requirement.

### 3.4 Crater-based matching (CNSF)

**[PAPER — Remote Sensing 2025, 17(13), 2302]** Detect crater rims, describe the
local *arrangement* of neighbouring craters, and match on that structure. A
crater rim has a physical diameter, so its identity survives both illumination
inversion and scale change — genuinely appealing for our hardest cases.

Why it is roadmap, not core: **[PAPER]** the crater *detector* is a trained
neural network (the paper is not training-free, contrary to how it was first
described to us), so it needs a lunar crater-detection model. **[PAPER]** it was
demonstrated on *same-instrument, multi-illumination* pairs — not cross-scale,
not cross-modal. **[EXTRAPOLATION]** Treating its published success as evidence
for our 16×–320× case would be exactly the overreach our evidence-labelling rule
exists to prevent. **[UNVERIFIED]** whether crater density at 80 m/pixel is even
sufficient. We present it as a prototype path, clearly labelled untested.

### 3.5 Visible-to-thermal neural matchers (XoFTR) and synthetic-modality training (MINIMA)

**[PAPER — arXiv:2404.09692 (XoFTR), arXiv:2412.19412 (MINIMA)]** Both target the
cross-modality problem that IIRS's thermal bands pose. XoFTR reaches an 8.4×
improvement over LoFTR **for terrestrial visible↔thermal scenes**. MINIMA
generates the hard modality from labelled RGB data so training labels come free.

Why roadmap: **[EXTRAPOLATION]** transfer to lunar IIRS thermal bands is untested
by anyone — the Moon has no atmosphere and no vegetation, and IIRS's thermal
bands are far narrower than a terrestrial thermal camera. **[PAPER]** both rely on
datasets with noncommercial licences. **[EXTRAPOLATION — our proposed
contribution]** for IIRS we could do better than MINIMA's generative approach by
using *physics* as the forward model (degrade a TMC-2 frame by IIRS's optics and
sampling), but that is a proposal with no result yet.

### 3.6 What learning would add, ranked by honesty

**[EXTRAPOLATION — all of this section; none implemented or measured]**

1. **An illumination-normalising front-end trained on synthetic scenes.** The
   strongest idea, because **[MEASURED — `eval/scenes.py`]** we already have exact
   ground truth for it: our scene generator emits the same terrain under two sun
   angles with the transform known perfectly. Train a small CNN to map both views
   to the same representation. It attacks the headline challenge directly,
   trains in minutes, and *replaces* a component (`align/refine.py`'s
   illumination heuristic) that is currently documented as defective and ships
   disabled. Risk to state: a number that only holds on synthetic scenes is a
   synthetic number.
2. **LoRA-style fine-tuning of LoFTR's coarse stage** on pseudo ground truth —
   teaches lunar appearance statistics, not lunar geometry. Expect fewer spurious
   matches on repetitive crater fields; do not expect better sub-pixel accuracy.
3. **A learned per-match confidence gate** before RANSAC. Training labels come
   free from existing runs. Cutting the outlier rate before RANSAC is worth more
   than tuning RANSAC.

---

## 4. Alignment with ISRO's stated requirement

Mapping the problem statement clause by clause to what the pipeline does.

| ISRO's requirement | How our approach meets it | Evidence |
|---|---|---|
| "Generic software solution" | one configurable pipeline; matcher / preprocessing / reference all settings; new matcher = one interface | design; 431 tests |
| "finding correspondence between Chandrayaan-2 acquired optical images and Lunar reference images" | ingest handles OHRC / TMC-2 / IIRS PDS4 products; reference target is LRO NAC (2×, matchable) or WAC (for IIRS at 1.25×) | **[MEASURED]** real OHRC products ingested; 22/25 label fields verified |
| "sub-pixel accuracy" | ECC intensity-based refinement after robust fitting; sub-pixel by construction | **[MEASURED]** 0.011–0.304 px true error on synthetic scenes vs known transform |
| "of source image" | the source (Chandrayaan-2) is the moving image; it is warped onto the fixed reference and written out | design |
| "maintaining uniform distribution across the images" | tiled matching spreads correspondences across the frame; **extrapolation-uncertainty map** reports where coverage is thin and the fit is unsupported; spatial-uniformity `U` reported as a diagnostic | **[MEASURED — `eval/uniformity.py`, `eval/conditioning.py`]** |
| Deliverable: "registered product with corresponding match points" | both saved per pair (`results.py`) | design |
| Deliverable: evaluation metrics — "RMSE, inlier match count, inlier ratio" | all three, plus spatial uniformity and extrapolation uncertainty, because **[MEASURED — `eval/uniformity.py`]** the three alone cannot substantiate "sub-pixel across the image" (fitted-RMSE moves 4% while true worst-case error moves 51×) | **[MEASURED]** |
| Title: "Multi-modal ... using OHRC, TMC and IIRS" | scale-aware routing: direct match when the ratio is under 8×, bridge through an intermediate instrument when it is not (IIRS→OHRC at 320× is refused and routed IIRS→TMC-2→OHRC) | **[MEASURED — `ingest/pseudo_gt.py`]** |
| Title: "Sun angle ... invariant" | neural matchers (illumination-robust) + local-contrast ECC pre-filter driven from sun-angle metadata | **[MEASURED]** 4.8× error reduction at 30° sun difference |
| Title: "scale invariant" | see multi-modal routing above; plus resampling to a common GSD in preprocessing | design |

**ISRO conventions we deliberately respect:**

- **[DOCUMENTED / MEASURED]** We read the **PDS4 label**, never the raw `.img`
  file directly — a common GIS library silently maps `.img` to the wrong driver
  and returns plausible wrong pixels.
- **[MEASURED — `ingest/geometry_grid.py`]** We use **ISRO's per-product geometry
  grid** (the `_g_grd` file, ~122,000 measured points) for pushbroom geometry
  rather than fitting our own four-corner homography, which we measured at **639 m
  median error** on a real strip.
- **[MEASURED]** We traverse ISRO's corner numbering in their order
  (upper-left, upper-right, lower-left, lower-right → polygon order 1, 2, 4, 3),
  confirmed against a real label.

---

## 5. Honest status of the approach

**[MEASURED]** The pipeline is complete and internally validated on synthetic
scenes. Its contact with real Chandrayaan-2 data is recent: five real products
processed, which immediately verified 22 of 25 metadata fields and exposed three
wrong assumptions (the 639 m homography error, the polar-rejection data-loss bug,
the footprint inflation). **[INSERT RESULT]** every headline accuracy figure
recomputed on real OHRC / TMC-2 / IIRS products, once a target region is selected
and matching LRO reference coverage is downloaded. **[INSERT RESULT]** LightGlue
and LoFTR results on a real GPU — both are implemented; neither has run on a GPU
because the current development machine has no working CUDA device.
