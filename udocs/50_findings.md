# 50 · What we actually measured

Every number here came from a run. Nothing is projected, rounded up, or
borrowed from a paper. Where a number does not exist yet, the row says so
instead of estimating.

Three labels are used throughout:

- **Measured** — this project produced it from a run, and the module is named.
- **Documented** — it comes from a paper or standard we read.
- **Unverified / Unknown** — nobody has checked it. Said out loud.

---

## The headline results

### 1 · RMSE cannot substantiate the requirement it is asked to substantiate

Six point layouts, all with 400 points and identical 0.5 px noise. Only the
spatial distribution differs.

| layout | fit RMSE | true worst-case error |
|---|---|---|
| even grid | 0.698 | 0.114 px |
| **tight blob** | **0.724** | **5.861 px** |

RMSE moves by 4%. True error moves by **51×**. A clustered solution reports
sub-pixel RMSE while being nearly six pixels wrong elsewhere in the same image.

**Measured** — `eval/uniformity.py`, synthetic homography benchmark.
This is the project's central argument. Doc 23 has the full table.

### 2 · Classical descriptors collapse under sun-angle change

| sun azimuth difference | SIFT geometrically-correct matches |
|---|---|
| 15° | 228 |
| 30° | 4 |
| **60°** | **0** |

A cliff, not a slope. **Measured** — `eval/error_budget.py` on synthetic scenes
with a known transform.

### 3 · A four-corner homography is wrong by 639 metres

Fitting one perspective transform to an OHRC strip's four corners, then comparing
against the per-pixel geometry grid ISRO ships with the product:

> **median disagreement 2554.6 px = 639 m** at 0.25 m/px

**Measured** — `ingest/geometry_grid.py`, and reproduced independently straight
from the raw CSV with none of the project's own code involved. Cause: a
pushbroom sensor has no single viewpoint, so no single perspective transform
describes it (docs 13 and 20).

### 4 · Bounding boxes inflate footprint area up to 4.2×

| sensor | inflation |
|---|---|
| OHRC | **3.9–4.2×** (78.9 km² → 309.0 km²) |
| TMC-2 | **2.2–2.3×** |

**Measured** on real products, on the production code path. This was a live bug
in `ingest/manifest.py`, found and fixed during this work. Doc 12.

### 5 · The first real overlaps

| pair | shared area | share of source |
|---|---|---|
| A ↔ B | 69.30 km² | 88% |
| A ↔ C | 65.97 km² | 84% |
| B ↔ C | 74.22 km² | 94% |

**Measured** on real Chandrayaan-2 OHRC products, and reproduced independently
rather than taken on trust. The project's first real overlap detection.

### 6 · Zero usable cross-sensor pairs

```
cross-sensor usable pairs: 0
OHRC × TMC-2:  disjoint = 9
```

All nine correctly classified **disjoint** — not failed, not skipped. Our OHRC
products are at latitude −85° near the south pole; our TMC-2 products are at
142° east near the equator. They are pictures of different places.

**This is the project's real blocker,** and it is a data-selection problem, not a
code problem. It needs a human to choose a target region and re-download. No
algorithm fixes two images of different places. Doc 12.

### 7 · Synthetic ground truth has a 23.09 m floor

`ingest/pseudo_gt.py` manufactures weak correspondences from independently
georeferenced overlap, and reports its own confidence rather than presenting the
output as reliable.

> **floor: 23.09 m** — about **92 pixels** at OHRC's 0.25 m/px

Enough for coarse-stage supervision; **not** enough for a sub-pixel claim, and
not enough to train a fine-stage matcher (doc 61).

The confidence object deliberately returns `None` for its total while any term is
`UNKNOWN`, rather than summing the known terms and presenting a partial sum as
the total. A floor labelled as a floor is useful; a partial sum labelled as a
total is not.

---

## Findings from the archive itself

**22 of 25 label fields resolved** against a real OHRC label — **12 VERIFIED,
5 DOCUMENTED, 6 UNVERIFIED**.

**ISRO does not use the obvious element names.** The solar incidence angle is
`solar_incidence`, not `incidence_angle`. The original guess found nothing,
silently. The observed value, **83.270815°**, is exactly 90° minus the sun
elevation on the same label — an internal consistency check.

**Two fields are simply absent.** `emission_angle` and `phase_angle` do not
appear in the reference OHRC label, and stay `UNVERIFIED` with a test pinning
that.

**The binary layout was cross-validated, not assumed.**
`101,074 × 12,000 × 1 byte = 1,212,888,000`, exactly the `.img` file length.

**TMC-2 tri-stereo confirmed from data, not from filenames.** All three of `nca`,
`ncf`, `ncn` carry an identical `sun_elevation` of **50.935114°**. Identical
solar geometry does not happen across separate passes.

**Corner numbering is not ring order.** ISRO's corners are
upper-left / upper-right / lower-left / lower-right, so the polygon must be
traversed **1, 2, 4, 3**. The pipeline was already doing this correctly.

---

## Things that did not work, kept because they are informative

### The ECC auto-prefilter is defective and ships disabled

The `auto` mode was meant to detect "same illumination" from a correlation score
and pick a prefilter. It cannot: sensor noise and illumination change both lower
the score, and it has no way to tell them apart. On a deliberately noisy test
pair it scored **0.917**, missed the 0.97 threshold, and chose wrong.

Shipped disabled and documented as a known defect rather than tuned until the
test passed. Tuning would have hidden the real problem — the *statistic* is
insufficient, so no threshold on it can work.

### I reported a critical bug that did not exist

I claimed a **1201× corner-ordering error** in the production code. It was not
real. `footprint_from_row` was already traversing `1, 2, 4, 3` correctly; my
throwaway test had bypassed the pipeline and assembled the ring by hand in naive
order. The bug was in my test.

Retracted explicitly in `CONTEXT_HANDOFF.md` §1.1 and left in place rather than
deleted, because a later reader needs to know the claim was made and withdrawn.
Lesson: when a test reports a spectacular number, suspect the test first.

### A delegated agent's "pre-existing failures" claim was wrong

An agent reported two pre-existing test failures. File modification times showed
they were another concurrently-running worker's in-flight edits — `overlap.py`
modified 17 seconds earlier, `test_overlap.py` 11 seconds earlier. The agent had
correctly ruled out its own files but could not see a concurrent worker.
Verify a delegated result against the repository, not against the report.

### A quoted ratio was product-specific and I generalised it

An agent measured affine-versus-homography difference at "~20×". That was TMC-2.
On OHRC it is **2.4×**. Product-dependent, corrected, and now always stated with
the product named.

---

## What is measured but must not be quoted as VRAM

The memory scaling study was run on a machine with **no working CUDA device** —
the nvidia kernel module is not loaded and the installed PyTorch is a CPU-only
build.

| finding | value |
|---|---|
| global activation scaling exponent | **2.13** |
| local exponent, small → large tiles | **1.83 → 3.69** |
| backbone cost | **3203 bytes per pixel** (measured) |
| fp16 saving factor | **0.6** — **ESTIMATED, NOT MEASURED** |
| hard dense tile cap | **1408 px** |

The rising local exponent is the `S⁴` comparison-table term overtaking the `S²`
CNN term — real, and the shape is trustworthy. **The absolute byte figures are
not VRAM** and `match/memory.py` says so on every run. They must be re-measured
on the RTX 4060 before anyone plans capacity against them.

An earlier version of this study reported a scaling exponent of **0.96**, which
was wrong: host memory included a fixed ~0.43 GB baseline that flattened the
curve. Fitting on peak-minus-baseline gives 2.13. The fix was to report the
baseline separately, not to adjust the conclusion.

Also unmeasurable here: **CPU bf16 autocast never completes** — killed after 15
minutes on a 512 px tile. Reported as unmeasurable rather than replaced with a
guess.

---

## Still empty, and honestly so

| what | status |
|---|---|
| any run on a GPU | **never happened** |
| LRO NAC/WAC reference data | **never downloaded** — mirrors confirmed reachable, no login needed |
| cross-sensor registration result | **none** — 0 usable pairs, see finding 6 |
| IIRS↔OHRC matching result | **none** — blocked on ground truth quality |
| end-to-end sub-pixel accuracy on real data | **none** — synthetic only so far |

Every one of these is a `[INSERT RESULT]` in the report drafts rather than a
plausible number. That is deliberate and non-negotiable: a results table filled
with reasonable-looking figures that no run produced is the one failure mode from
which a project cannot recover its credibility.

---

## Open decisions that belong to a human

1. **Wire the geometry grid into `overlap.py`** in place of the four-corner
   homography. Justification is measured (639 m). Not done, because it changes
   **every crop the pipeline produces** and should be deliberate.
2. **Pick a target lunar region and re-download.** Blocks everything
   cross-sensor. See finding 6.
3. **Resolve the datum question.** The label says "selenographic" with no unit
   and no coordinate-system element. Cancels out within Chandrayaan-2; stops
   cancelling the moment LRO is introduced.
4. **Accept or reject the 23.09 m pseudo-GT floor** as a basis for anything.
5. **SuperGlue's noncommercial licence** — run it for comparison only, or drop it.
6. **Standardise the 11 placeholder preprocessing parameters.**
7. **Whether synthetic-only results are acceptable** for the internal round.
