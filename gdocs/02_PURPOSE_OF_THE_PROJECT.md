# 02 · The purpose of this project

*Audience: a teammate with a CS background and no remote-sensing exposure. Terms
are defined at first use, including software-engineering terms where they matter.
Read doc 01 first — it explains why the problem exists at all.*

**New words in this doc**

| word | plain meaning |
|---|---|
| **Chandralipi** | the internal name of this project. ("Chandra" = Moon, "lipi" = script/writing — roughly "lunar transcription".) |
| **pipeline** | a chain of processing stages where each stage's output feeds the next. Our pipeline goes: read data → find overlap → clean up images → match points → fit a transform → refine it → score it → save it. |
| **matcher** | an algorithm that takes two images and returns a list of corresponding point pairs. We ship several and compare them. |
| **classical matcher** | a matcher hand-designed by researchers using fixed maths, no machine learning. Examples: SIFT, ASIFT, AKAZE. |
| **neural / learned matcher** | a matcher that is a neural network whose behaviour was learned from training data. Examples: LoFTR, LightGlue. We use them *pretrained* — we do not train them ourselves. |
| **pretrained / zero-shot** | using a neural network exactly as someone else trained it, with no further training of our own. |
| **transform (geometric)** | the function that maps a coordinate in the source image to its coordinate in the reference image. Could be as simple as a shift, or as complex as a full perspective warp. |
| **RANSAC** | a standard technique for fitting a model when many of the input points are wrong. It repeatedly fits to a small random subset and keeps the fit that the most other points agree with. |
| **RMSE (Root Mean Square Error)** | an average error distance, computed so that big misses count more than small ones. The problem statement suggests reporting it. |
| **inlier** | a match point that agrees with the fitted transform. A "good" match. **inlier ratio** = inliers ÷ total matches. |
| **ground truth** | the known-correct answer, used to check whether a method actually worked. Real lunar image pairs do not come with ground truth; synthetic test scenes do, because we chose the answer when we generated them. |
| **synthetic scene** | a computer-generated fake lunar image where we set the correct transform in advance, so accuracy can be measured exactly. |
| **provenance** | a record, attached to each value, of *where that value came from* — measured by us, taken from a paper, or an unverified guess. We carry this in the code itself, not in a comment. |
| **regression test** | an automated check that a specific past bug has not come back. We have 431 automated tests total. |
| **PDS4** | the file format NASA and ISRO use to ship planetary data. Each product is an XML label file plus a raw binary image file. |

---

## 1. What we are building, in one sentence

**Chandralipi is a generic, automated pipeline that takes a Chandrayaan-2 optical
image and a lunar reference image, finds match points between them that are both
sub-pixel accurate and spread evenly across the frame, warps the source onto the
reference, and reports honest metrics on how well it did.**

That is a restatement of problem statement SIH26166. The rest of this document is
about *how we interpret each part of it* and *what we consider the project's real
contribution*.

---

## 2. What we deliver

ISRO's problem statement names the deliverables. Ours map to them directly:

| ISRO asks for | We deliver |
|---|---|
| Software (a generic solution) | The `lunar_reg` Python package: ingest, overlap detection, preprocessing, classical + neural matchers, robust fitting, sub-pixel refinement, evaluation, per-pair storage, an end-to-end runner, plus a small inspection tool and a results dashboard. |
| A registered product | The warped source image, aligned to the reference, written back out. |
| The corresponding match points | The full list of correspondences (source pixel ↔ reference pixel), saved per image pair. |
| Evaluation metrics — RMSE, inlier count, inlier ratio | All three, plus two additional metrics we argue are necessary (section 4). |

Everything is configuration-driven: which matcher to use, which preprocessing
steps to enable, which reference to align against, are all settings, not code
changes. That is what "generic" means in practice.

---

## 3. What "generic" forces us to handle

A one-off alignment script can assume a lot. A generic pipeline cannot. The
purpose of the project includes correctly handling all of the following, because
ISRO's archive contains all of them:

- **Three source instruments** at wildly different scales (OHRC at 0.25 m/pixel,
  TMC-2 at 5 m, IIRS at ~80 m). The pipeline must pick a sensible reference and,
  where the scale gap is too large for any direct matcher (IIRS ↔ OHRC is 320×),
  route through an intermediate instrument rather than attempt the impossible.

- **Any pair of sun angles.** Two images of the same crater taken months apart
  can be near-photographic-negatives of each other (doc 01, §3.1). The pipeline
  has to detect when illumination differs and adapt its preprocessing.

- **Pushbroom sensor geometry.** These cameras scan the ground one line at a
  time (doc 01, §3.3), so a single perspective transform is the wrong model. The
  pipeline reads the per-pixel geometry table that ISRO ships alongside each
  product instead of guessing.

- **Polar and equatorial data.** Near the Moon's poles, ordinary flat
  (latitude, longitude) coordinates break down because longitude lines converge.
  Our downloaded data sits at −85° latitude, deep in that regime, so the pipeline
  works in a projection that behaves correctly near a pole.

- **Failure.** Some image pairs genuinely do not overlap, or overlap but share no
  matchable content. A generic pipeline must report this as a *classified
  outcome* with a count and an example — never crash, and never silently skip it
  and pretend everything registered.

---

## 4. The project's actual contribution: honest evaluation

If the purpose were only "align two images", this would be a solved problem with
off-the-shelf parts. The part that is *not* solved, and that we treat as the core
purpose, is **measuring whether the alignment is actually good** — specifically,
whether it meets the problem statement's own requirement of *sub-pixel accuracy
across the whole image*.

Here is the trap. The obvious metric, RMSE, is normally computed over the same
match points that were used to fit the transform. That number is nearly blind to
*where those points are*. We measured this on synthetic scenes with a known
answer: across six point layouts holding point count and noise fixed and changing
only the spatial distribution, the fitted-points RMSE moved by **4%** while the
true worst-case error elsewhere in the image moved by **51×**. A solution with
all its match points clustered in one corner can report a beautiful sub-pixel
RMSE while being nearly six pixels wrong on the opposite side of the same frame.

So a pipeline that optimises for RMSE, and a panel that judges on RMSE, can both
be fooled. That is *why the problem statement explicitly demands uniform
distribution* — it is a defence against exactly this failure. And it is why we
report two metrics beyond the three ISRO names:

| metric | what it measures | how we use it |
|---|---|---|
| **Spatial uniformity `U`** | how evenly the match points cover the frame | a *descriptive diagnostic only*. Our stress tests showed it is a weak predictor of true error (it fails some well-conditioned layouts and passes some bad ones), so we never gate on it. |
| **Extrapolation uncertainty** | in pixels, by resampling the match points, how much the fitted transform wobbles where it has little support — i.e. *where in the image the registration can and cannot be trusted* | this is the metric we gate on. In our tests it tracks true error far better than either RMSE or `U`. It renders as a map. |

Stated limit, because our own rule is to state limits: extrapolation uncertainty
measures *precision*, not *accuracy*. A consistent systematic offset — a
georeferencing bias, an illumination-induced shift — leaves it small while the
answer is wrong. It is always reported *next to* RMSE, never instead of it.

**This evaluation argument is the most defensible novel content in the project.**
The registration machinery is careful engineering with known parts; the
"how do you actually know it's sub-pixel everywhere" analysis is the part a
judging panel should find genuinely useful.

---

## 5. How we work — the three rules that are load-bearing

These are not style preferences. Each one exists because violating it caused a
real bug in this project.

1. **Provenance lives in the code, not in prose.** Every external data field and
   every algorithm parameter carries a machine-readable tag: `VERIFIED` (checked
   against a real file), `DOCUMENTED` (from a paper or standard we read), or
   `UNVERIFIED` / `PLACEHOLDER` (a guess, not yet checked). A disclaimer at the
   top of a file does not survive being copied into a report; a tag on the field
   does. Currently the geometry field map is 12 verified / 5 documented / 6
   unverified, and the preprocessing parameters are 9 from-paper / 5
   paper-gives-a-range / 15 placeholder.

2. **Failure is classified, counted, and sampled — never skipped.** When the
   pipeline processes many image pairs and some fail, it records *which failure
   mode*, *how many*, and *one concrete example of each*. A count tells you how
   widespread a problem is; an example tells you what it looks like; diagnosis
   needs both.

3. **Numbers come from runs.** No accuracy figure appears in any of our
   documents unless a real run produced it. Where a run has not happened yet, the
   document says `[INSERT RESULT]` rather than a plausible-looking placeholder. A
   results table full of invented-but-reasonable numbers is the one mistake from
   which a project cannot recover its credibility.

---

## 6. What is deliberately *not* in scope

Being explicit about non-goals keeps the project honest and the pitch defensible.

- **No training of neural networks.** Every neural weight we use was trained by
  someone else on terrestrial imagery and is used zero-shot. This is a deliberate
  choice: it is what makes "a working prototype in weeks on one consumer GPU"
  true, and we have no lunar training set anyway. Doc 04 covers what training
  *would* add and why we treat it as future work.

- **No large language model.** There is no LLM anywhere in the pipeline and no
  place one would help. Registering two images is a geometry problem; text is not
  involved. (Our main neural matcher *is* a transformer — the same attention
  mechanism as a language model — but applied to image patches, not words.)

- **No claim of results on real lunar data beyond what has actually run.** As of
  now, every headline accuracy number came from synthetic scenes, because
  Chandrayaan-2 archive access cleared only recently and only partially. Five
  real products have been processed; that already overturned three assumptions.
  The honest status is: *the machinery is built and internally validated; its
  contact with real data is new and ongoing.*

- **The showcase website is a separate artefact.** It reads a static export and
  does not call the pipeline. It is not part of the deliverable and changes there
  never affect a result.

---

## 7. Success criteria

We consider the project successful for the internal round if:

1. The pipeline runs end-to-end on a real Chandrayaan-2 OHRC product against a
   real LRO reference, unattended, and produces a registered product plus match
   points plus all five metrics. *(Blocked only on selecting a target region and
   downloading matching reference coverage — a human decision, not a code gap.)*
2. On synthetic scenes with known ground truth, the reported extrapolation
   uncertainty reliably flags the cases where true error exceeds one pixel.
   *(Demonstrated: it tracks true error far better than RMSE in our tests.)*
3. Every number in the submission is traceable to a named module and a real run,
   and every unverified assumption is labelled as one.
4. The evaluation argument — why the three standard metrics cannot by themselves
   substantiate "sub-pixel across the image", and what to report instead — is
   written up clearly enough that a panel can follow it.
