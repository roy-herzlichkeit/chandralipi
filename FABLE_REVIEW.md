# Review brief for Fable

You are being asked for an **adversarial second pass** on Chandralipi, a
submission for Smart India Hackathon 2026 problem SIH26166 (ISRO): multi-modal,
sun-angle and scale invariant image correspondence across Chandrayaan-2 optical
payloads.

You have no shared context with the session that built this. Everything you need
is in the repository. This document lists the ten things I am **actually
uncertain about**, with the code path and what a useful answer looks like for
each — and then, because this pass has a hard budget, names the four you should
actually do.

I am not asking you to find typos or to restyle code. I am asking you to try to
break the claims — especially the ones the project intends to defend in front of
a panel.


---

## Budget: four credits. Read this before starting.

**This review must complete within roughly four credits.** That is the binding
constraint, and it is tighter than the ten questions below deserve. Scope
accordingly rather than starting at Q1 and running out.

**Do these four, in this order. They are the review.**

| | question | rough cost | why it earns the spend |
|---|---|---|---|
| 1 | **Q1** — is the uniformity metric's validation strong enough? | ~1 credit | it is the project's defensible novelty, and its gate is fitted to its own validation set |
| 2 | **Q3** — is bootstrap conditioning circular? | ~1 credit | a real methodological doubt with a cheap, decisive experiment |
| 3 | **Q4** — is the 639 m claim measured against a strawman? | ~1 credit | decides whether the headline geometric claim is honestly framed |
| 4 | **Q10** — provenance audit | ~0.5 credit | cheap, mechanical, and protects every other claim from an easy attack |

That leaves headroom. **Spend it on writing up properly, not on Q5–Q9.**

**Q2, Q5, Q6, Q7, Q8, Q9 are out of scope for this pass.** They are documented
below because they are real and because a later reviewer should have them, not
because you should attempt them now. If one of the four above collapses quickly
and you have a full credit spare, take **Q8** — it is the cheapest and I
specifically want a second pair of eyes on it.

**Cost discipline:**

- Run `pytest` **once**, at the start, to confirm the tree is sound. Do not
  re-run the full suite after each investigation; run the single relevant test.
- Q1 and Q3 both need a small experiment script. Write **one** script that
  covers both — they share the synthetic-benchmark setup — rather than two.
- Do not read the whole repository. The four questions name their files.
- Do not attempt anything requiring a GPU, a download, or a paywalled paper.
  Mark it `COULD NOT CHECK` and move on. That is a valid, useful outcome.
- **If you are running low, stop and write up what you have.** Four questions
  answered well beats ten started. A partial review that says clearly where it
  stopped is worth more than a complete one that had to rush its evidence.

---

## Rules of engagement

These are not preferences. Violating them has caused real damage in this project
before, and the whole point of a second pass is to hold the line harder, not
softer.

1. **Never state a number that a run did not produce.** If you need a figure and
   cannot produce it, write `[NOT MEASURED]` and say what would produce it. Do
   not estimate, interpolate, or recall a plausible value.
2. **Label every claim by its evidence.** *Measured* (this repo produced it from
   a run — name the module), *Documented* (a paper or standard you actually
   read — quote it), *Extrapolation* (your inference). Never present an
   extrapolation with the same confidence as a cited result. If you cite a
   paper, read the paper; an abstract does not contain parameters or results.
3. **Never invent external-format field names or binary layouts.** If you need to
   know what an ISRO PDS4 label contains, run `lunar-reg probe-label` against a
   real file or say you could not check it. Guessed field names fail silently:
   a wrong element name returns `None`, which is indistinguishable in a table
   from a value genuinely absent from the product.
4. **Surface what you could not check**, with the reason, as a first-class part
   of your output. A short review that says clearly what it did not reach is
   more useful than a long one that papers over it.
5. **Do not fix things in this pass unless the finding is trivial and certain.**
   Several items below touch code paths that change every crop the pipeline
   produces. Diagnose, quantify, recommend. Let a human decide.
6. **Distrust confident-sounding prior findings, including mine.** One of the
   items below exists specifically because I reported a catastrophic bug that
   did not exist. The retraction is preserved in `CONTEXT_HANDOFF.md` §1.1.

---

## Getting oriented (about fifteen minutes)

```bash
pip install -e ".[dev]"
pytest                      # expect 431 passed, 1 skipped (the skip needs a GPU)
ruff check src tests scripts
```

Read in this order:

| file | why |
|---|---|
| `CONTEXT.md` | one page, the whole shape |
| `CONTEXT_HANDOFF.md` | the detailed status review — known issues, open decisions |
| `udocs/50_findings.md` | every measured number in one place, with its module |
| `udocs/23_PRIMER_metrics.md` | the headline claim, explained at length |

Two things to internalise before you start:

- **Almost every headline number is from synthetic scenes.** The pipeline's
  contact with real Chandrayaan-2 data is recent and partial. Five real products
  have been processed. No learned matcher has ever run on a GPU in this project.
- **`docs/` is the deliverable. `udocs/` is gitignored personal learning notes.
  `web/` is a separate showcase site that reads a static JSON export and cannot
  affect a result.**

---

# The questions

Ten are documented. **Four are in scope for this pass** — see the Budget section
above. The rest are recorded so a later reviewer inherits them rather than
rediscovering them.

## Q1 — Is the uniformity metric's validation strong enough to defend? **(highest priority)**

**The claim.** `U = sqrt(C · H)` — geometric mean of grid coverage and
normalised per-cell entropy — is proposed as the metric for the problem
statement's "uniform distribution across the images" requirement, which the
statement itself names no metric for. It is validated by: *"`U` ranks the six
layouts in the same order as their worst-case error, Spearman −0.83."* And
`UNIFORMITY_GATE = 0.7` is described as *"calibrated against the benchmark:
the layouts scoring under it had worst-case errors of 0.77 px and up, versus
0.14 px for those above."*

**Where.** `src/lunar_reg/eval/uniformity.py`, module docstring and constants.

**Why I am uncertain.** Two things bother me and I could not resolve either from
inside the work.

- **n = 6.** Six hand-chosen layouts. Spearman −0.83 on n=6 is around p ≈ 0.04
  — nominally significant, and thin. Worse, *we chose the six layouts*, and we
  chose them to span a range we already believed in.
- **The gate is calibrated on the validation set.** `UNIFORMITY_GATE = 0.7` was
  set by looking at where those same six layouts separated. That is fitting a
  threshold to the data used to justify it. In any other context I would call
  this out immediately.

**What I want from you.** Either (a) a construction that breaks it — a point
layout with high `U` and large true error, or low `U` and small true error — or
(b) a stronger validation: many more randomly generated layouts, the rank
correlation recomputed, and the gate re-derived on layouts *held out* from the
ones used to set it. If the metric survives that, say so and give the number. If
it does not, that is far more valuable to know now than after a panel finds it.

**A bad answer** restates the docstring's reasoning back to me. The docstring's
reasoning is the thing under review.

---

## Q2 — Is the 51× RMSE claim interesting, or definitional?  *(out of scope this pass)*

**The claim.** Six layouts, all with 400 points and identical 0.5 px noise. Fit
RMSE spans 0.698–0.724 (essentially constant) while true worst-case error spans
0.114–5.861 px — a **51× range**. Therefore RMSE cannot substantiate the problem
statement's "sub-pixel across the image" requirement.

**Where.** `src/lunar_reg/eval/uniformity.py` docstring; the probe mechanism in
`eval/conditioning.py::probe_grid`, which places probes on a
`linspace`-uniform grid across the entire image.

**Why I am uncertain.** "True error" is measured at probes spread uniformly over
the whole image. A clustered correspondence set is therefore being scored
largely at locations far from any of its points. That may be exactly the right
test — it is what "across the image" means — or it may make the conclusion close
to definitional: of course a fit constrained in one corner extrapolates badly
into the other three.

I think the claim is fair and important. I am not certain a hostile reviewer
would agree, and I would rather find out from you.

**What I want from you.** A judgement on whether the comparison is fair as
constructed, and if you think it is partly definitional, the strongest honest
reframing. Is there a version of the experiment that is less open to that
objection — probes weighted by distance to the nearest correspondence, say, or a
held-out set of *real* correspondences rather than a synthetic grid?

---

## Q3 — Is the bootstrap conditioning metric circular?

**The claim.** Resampling the correspondences with replacement, refitting, and
measuring the spread of predictions at probe points gives a map of where the
transform is trustworthy. `EXTRAPOLATION_GATE_PX = 1.0` flags regions where the
transform is extrapolating.

**Where.** `src/lunar_reg/eval/conditioning.py::bootstrap_conditioning`.

**Why I am uncertain.** The points fed to it are, in the normal pipeline path,
**the post-RANSAC inlier set** — points already selected for agreeing with one
particular transform. The bootstrap resamples inside that selected set and never
re-runs the selection. So the measured spread is conditional on RANSAC's choice
and should systematically *understate* true uncertainty: every resample is drawn
from a population that a prior fitting step already made self-consistent.

If that is right, the metric is still useful — relative comparisons hold — but
the absolute `1.0 px` gate is measuring something narrower than it appears to,
and calling a region "trustworthy" on that basis is stronger language than the
evidence supports.

**What I want from you.** Confirm or refute the circularity. If it is real,
quantify it: bootstrap over the *pre-RANSAC* correspondence set with the
selection re-run inside each iteration, and report how much wider the spread
gets. Then say whether `EXTRAPOLATION_GATE_PX = 1.0` should move, or whether the
right fix is only to change what we claim the number means.

---

## Q4 — Is the 639 m homography error measured against a strawman?

**The claim.** Fitting one perspective transform to a product's four footprint
corners disagrees with ISRO's shipped per-pixel geometry grid by a **median of
2554.6 px = 639 m** at 0.25 m/px. Cause: a pushbroom sensor has no single
viewpoint, so no single perspective transform describes it.

**Where.** `src/lunar_reg/ingest/geometry_grid.py`; the current four-corner path
in `ingest/overlap.py`. I reproduced the number independently from the raw
`_g_grd_d18.csv` with no project code in the loop, so I am confident in the
*arithmetic*.

**Why I am uncertain.** I am not confident in the *framing*. Fitting a
homography to exactly four points is the minimum-evidence case, and nobody doing
this seriously would stop there. If the honest comparison is against a
least-squares homography fitted to many grid points, or a low-order polynomial
rational function fit, the gap may collapse — and if it does, "the four-corner
homography is wrong by 639 m" is technically true and rhetorically misleading.

**What I want from you.** Fit the stronger alternatives to the same geometry
grid and report their residuals beside the four-corner number: (a) a
least-squares homography over all grid points, (b) an affine over all grid
points, (c) a 2nd- or 3rd-order polynomial. If a global homography gets the
error to a few pixels, the correct claim changes from *"a homography is the
wrong model"* to *"four corners is not enough evidence"*, and every doc that
states it needs rewording. Tell me which of those two the data supports.

---

## Q5 — Is `pseudo_gt`'s 23.09 m floor complete, and is anything reading it as a total?  *(out of scope this pass)*

**The claim.** Synthetic ground truth for OHRC↔IIRS, derived from independently
georeferenced overlap, has a measured error floor of **23.09 m** (≈92 px at
OHRC's 0.25 m/px). `ConfidenceEstimate.total_sigma_m` deliberately returns
`None` while any term is `UNKNOWN`, rather than summing the known terms and
presenting a partial sum as a total.

**Where.** `src/lunar_reg/ingest/pseudo_gt.py`.

**Why I am uncertain.** Three specific things:

- **Term completeness.** I enumerated the error terms myself. I do not know what
  I left out. Candidates I can name but did not quantify: the datum ambiguity
  (Q7), along-track timing/ephemeris error, terrain relief parallax between two
  look angles, and IIRS's own geolocation uncertainty, which I never found a
  documented figure for.
- **`loop_closure_residual_m()` is tautologically zero** and is explicitly
  documented as a trap-detector rather than evidence. Check that nothing —
  code, doc, report draft, or dashboard — presents it as a validation result.
  That is exactly the kind of thing that survives into a slide.
- **The `corner ordering` term was recently changed from `UNKNOWN` to
  `COMPUTED, 0.0`** on the strength of a verified real label. Confirm that
  promotion is justified and that the note attached to it is accurate.

**What I want from you.** A list of error terms that are missing, each marked
*quantifiable now* / *needs data we do not have*. And an explicit yes/no on
whether 23.09 m is being presented anywhere as a total rather than a floor.

---

## Q6 — Does the VRAM model's *form* hold, and is `FP16_BACKBONE_FACTOR` safe to plan against?  *(out of scope this pass)*

**The claim.**
```
bytes(S) = BACKBONE_BYTES_PER_PX · S²  +  bytes_per_element · (S/8)⁴
BACKBONE_BYTES_PER_PX = 3203.0     # MEASURED
FP16_BACKBONE_FACTOR  = 0.6        # ESTIMATED, NOT MEASURED
MAX_DENSE_TILE_PX     = 1408
```
Measured activation exponent 2.13 globally, with the local exponent climbing
1.83 → 3.69 across the sweep.

**Where.** `src/lunar_reg/device.py`, `match/benchmark.py`, `match/memory.py`.

**Why I am uncertain.** Everything above was measured on **host RAM on a machine
with no working CUDA device** — the nvidia kernel module is not loaded and the
installed PyTorch is CPU-only. `match/memory.py` prints *"VRAM CANNOT BE MEASURED
ON THIS MACHINE."* on every run, and no figure is presented as VRAM. But:

- the **two-term form** may be wrong regardless of the platform. Is there an
  intermediate term I have missed — attention intermediates that scale as `S³`,
  or a fixed per-layer cost that matters at small tiles?
- `FP16_BACKBONE_FACTOR = 0.6` is a guess derived from a **CPU bf16 autocast
  ratio**, which is a different backend. It is labelled as estimated, and it
  still feeds `plan_dense_tile`, which hands out tile sizes. A wrong factor here
  produces OOM at runtime.
- An earlier version of this study reported an exponent of **0.96**, which was
  wrong because host RSS included a fixed ~0.43 GB baseline that flattened the
  curve. Fitting on peak-minus-baseline gives 2.13. I would like that correction
  independently sanity-checked.

**What I want from you.** A judgement on the model's functional form from the
LoFTR architecture, not from our measurements. If you have access to a CUDA
device, re-run `match/benchmark.py` and replace the constants with measured
ones — that single act unblocks more of this project than anything else on this
list. If you do not, say so plainly.

---

## Q7 — The polar path: two specific soundness questions  *(out of scope this pass)*

**Where.** `src/lunar_reg/ingest/overlap.py` — `PolarFrame`,
`POLAR_CLIP_MAX_COLATITUDE_DEG = 60.0`, the 80° switch.

**Context.** All three real OHRC products sit at **latitude −85°**, so the polar
path is not an edge case here; it is the main case. Footprints are projected to
an azimuthal equidistant plane centred on the pole, clipped there with
Foster–Hormann–Popa (`clipFHP4`, chosen over Sutherland–Hodgman because the
latter silently requires convexity), then projected back.

**Two things I want checked.**

1. **Where area is computed.** The `PolarFrame` docstring states *"areas are
   never taken from this plane, only from the sphere"*, which is the right
   design — an equidistant projection does not preserve area. Verify that this
   actually holds on every code path, not just the one the docstring describes.
   But note the subtler issue even when it does hold: the **clipped polygon's
   vertices are determined in the plane**, so its edges are straight lines in a
   distance-preserving projection rather than great-circle arcs. The area is
   then computed by spherical excess on a shape whose boundary was decided
   elsewhere. Quantify that error at −85° for a real OHRC footprint. I expect it
   to be small. I have not shown that it is.

2. **The 80° seam.** Switching between the spherical and flat-plane paths
   produces a **measured 0.3–0.8% discontinuity in reported area**. It is
   recorded rather than hidden. Is that the right size for the methods
   involved, or is it larger than it should be — i.e. a symptom rather than a
   seam?

Also relevant, and unresolved: the ISRO geometry label says the coordinates are
*"selenographic"* and gives **no unit and no coordinate-system element**.
Planetocentric versus planetographic is unstated. It cancels while every product
is Chandrayaan-2 and stops cancelling the moment LRO enters, which is the plan.
If you can find documentation that settles it, that closes an open decision. Do
not settle it by assumption.

---

## Q8 — Verify corner ordering independently. I got this wrong once.  *(first reserve — take this only if a core question collapses early)*

**The claim.** ISRO's corner fields are named
`upper_left / upper_right / lower_left / lower_right`, numbered 1–4 in that
order, which is **not** ring order. Ring order is **1, 2, 4, 3**, and
`footprint_from_row` already traverses it correctly:

```python
ordered = (corners[0], corners[1], corners[3], corners[2])
```

**Why this is on the list.** Earlier in this project I reported a **1201× area
error** from corner mis-ordering in production code. **It was not real.** The
pipeline was already correct; my throwaway test had bypassed it and assembled
the ring by hand in naive numeric order, so the "measurement" measured my own
mistake. The retraction is preserved in `CONTEXT_HANDOFF.md` §1.1 rather than
deleted, because a reader who finds the original claim elsewhere needs to know
it was withdrawn.

**What I want from you.** Independent confirmation, from a real label, that the
current traversal is right — reached without reading my reasoning first. The
guard test is `tests/test_ingest_labels.py::test_corner_numbering_is_not_ring_order`,
which asserts `40 < area_km2 < 150`. Check that the bound is meaningful rather
than merely satisfiable.

---

## Q9 — Is disabling the ECC prefilter heuristic the right call, or is there a statistic that works?  *(out of scope this pass)*

**The claim.** `align/refine.py`'s `auto` prefilter mode tried to detect "same
illumination" from a normalised correlation score against
`ECC_SAME_ILLUMINATION_NCC = 0.97`. It cannot: sensor noise and illumination
change both depress the score and it has no way to separate them. On a
deliberately noisy test pair it scored **0.917**, missed the threshold, and
chose wrong. It ships **disabled**, documented as a known defect rather than
tuned until the test passed.

**Where.** `src/lunar_reg/align/refine.py`.

**Why I am uncertain.** I am confident that *this* statistic cannot work and
that tuning the threshold would have hidden the real problem. I am much less
confident that **no** cheap statistic can. Candidates I did not try: mutual
information, correlation of gradient-orientation histograms, phase congruency
agreement (RIFT2 already implements the machinery in `match/rift2/phase.py`), or
simply using the sun-azimuth difference from the labels — which is *known
metadata* and might make the whole heuristic unnecessary.

That last one may be the answer and I may have overcomplicated this.

**What I want from you.** Either a statistic that separates the two causes on
the existing test pairs, with numbers, or a clear statement that the metadata
route is correct and the image-derived heuristic should be deleted rather than
left disabled. Dead code that is documented as broken is still dead code.

---

## Q10 — Provenance audit across everything a panel will read

**What I want.** A sweep of `docs/`, `README.md`, `CONTEXT.md`,
`CONTEXT_HANDOFF.md`, `udocs/`, `scripts/build_demo_results.py`, and the
dashboard/web export for any number that is **not traceable to a run**.

Specific things to look for:

- A figure stated without a source that a reader would take as measured.
- A synthetic result presented in a context that implies real data. Almost every
  headline number here is synthetic; the docs are supposed to say so every time.
- **The two RMSEs.** This repo has a conventional self-residual RMSE
  (`eval/metrics.py`) and a truth-based figure (`eval/error_budget.py`), and
  they differ by **12.7× to 58.6×** on the same pairs. Check that no document
  quotes one where a reader would assume the other. This is the single easiest
  way for this project to look like it is cherry-picking when it is not.
- **The affine-vs-homography ratio.** An agent measured "~20×"; that was TMC-2.
  On OHRC it is **2.4×**. It is product-dependent and must never appear as a
  general figure. Confirm it does not.
- `[INSERT RESULT]` placeholders in the report drafts: confirm every one is
  still a placeholder and none has been quietly filled in.

---

# Priorities

Superseded by the **Budget** section at the top of this document, which is
authoritative. In short: **Q1, Q3, Q4, Q10** are this pass. **Q8** is the first
reserve. Everything else is recorded for a later reviewer with more room.

# What I want back

For each of the four questions in scope (and Q8 if you took it):

1. **Verdict** — one of: `HOLDS` / `HOLDS WITH CAVEAT` / `DOES NOT HOLD` /
   `COULD NOT CHECK`.
2. **Evidence** — the command you ran and its output, or the file and line, or
   the paper and the quoted passage. Not a summary of your reasoning; the thing
   itself.
3. **What changes** — if a claim does not hold, the exact wording that should
   replace it, and every file that states it.
4. **Confidence** — and if you cannot produce one, say why rather than omitting
   it.

Then, separately:

- **What you could not check, and why.** Please make this a real section rather
  than a closing sentence. Hardware you did not have, papers behind a paywall,
  data that is not in the repo — all of it is useful.
- **Anything you found that is not on this list.** The ten questions are the
  things I know I am unsure about. The failures that matter are usually the
  ones nobody thought to ask about.

An honest *"this is weak and here is exactly why"* is worth more to this project
than a confident endorsement. The next reader after you is a panel, and they get
to ask follow-up questions.
