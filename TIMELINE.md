# Development timeline

**Provenance of this document.** The project was built before `git init` was
ever run, so there is no commit history behind it. Everything below is
reconstructed from the development transcript, not derived from commits. Where a
figure appears it comes from a run recorded in that transcript, and the module it
lives in is named so it can be checked. Treat the *ordering* as reliable and the
*dating within a phase* as approximate.

The repository's own history begins at commit `26a5dd8`, which snapshots the end
state of phase 9.

---

## Phase 1 — Scaffold

Project skeleton: `src/lunar_reg/{ingest,preprocess,match,align,eval,viz}`,
`tests/`, `pyproject.toml`.

Two decisions taken here that constrained everything after:

- **`opencv-python` pinned `<5`.** OpenCV 5 removed AKAZE, KAZE and BRISK from
  the main module, and `opencv-contrib-python` 5.0.0 does *not* restore them
  (verified, not assumed). AKAZE is one of the benchmark paper's four classical
  baselines, so the pin is load-bearing.
- **A VRAM budget model in `device.py`**, because the target is a single 8 GB
  RTX 4060 and tile sizing had to be derived rather than guessed. This model was
  later found to be wrong — see phase 6.

## Phase 2 — Ingest, with a provenance boundary

`ingest/pds4.py`, `ingest/fieldmap.py`, `ingest/manifest.py`.

The governing constraint, set by the user: do not invent PDS4 field names from
memory. The response was a declarative field map where **every field carries a
`Provenance` value** — VERIFIED, DOCUMENTED, or UNVERIFIED — and the manifest
reports which unverified fields actually resolved.

Two hazards documented in code:

- The loader opens the **label**, never the `.IMG`. GDAL maps `.img` to its
  ERDAS HFA driver and returns plausible wrong pixels with no error.
- `axis_order` is surfaced explicitly, because reading a band-sequential cube as
  band-interleaved produces no error, just incorrect per-band values.

`ingest/probe.py` shipped alongside: a `probe-label --suggest` command that dumps
a real label's tree and emits a paste-ready corrected mapping. This turned the
missing-sample-file problem from a blocker into a two-minute task, and is what
eventually resolved the field map in phase 9.

## Phase 3 — Footprint overlap

`ingest/overlap.py`. Corner-coordinate intersection on the lunar sphere.

Constraint from the user: degenerate or empty overlaps must not be silently
skipped. Result: `OverlapStatus`, an explicit enum of outcomes with one member
per failure mode, and `OverlapDiagnostics` accumulating counts plus a retained
sample per mode, with a `report()` intended to print on every run.

Bugs found and fixed during live runs:

- `pygeodesy.areaOf` is wrong on **closed** rings (measured 53× to 51,567× off),
  and `clipFHP4` returns closed rings. Fixed by stripping the duplicate vertex.
- A crop filename collision that let one product overwrite itself when it
  appeared in two pairs.
- An off-by-one window; `BLOCKXSIZE` set without `TILED`; a duplicated report.

## Phase 4 — Preprocessing

`preprocess/`, implementing the Makharia et al. chain with every step
independently toggleable for ablation.

Constraint: parameters the paper does not state must be marked as placeholders,
not passed off as paper-matched. Result: `ParamSource` — currently **9 PAPER,
5 PAPER_RANGE, 15 PLACEHOLDER**. Reading the full paper in phase 8 confirmed
this was the right call; five of its ten steps carry no values.

Two measured bugs:

- Shadow gamma **darkened** instead of brightening (12.20 → 10.01) because it
  normalised against the full intensity range rather than the shadow range.
- Percentile thresholding overshoots on ties — the 5th percentile selected 9.1%
  of pixels while the docstring claimed ~percentile/100.

## Phase 5 — Matchers, alignment, metrics

`match/classical.py` (SIFT, ASIFT, AKAZE), `match/rift2/` (clean-room from the
papers, chosen by the user over wrapping unlicensed reference code),
`align/estimate.py`, `align/refine.py`, `eval/`.

Findings:

- **`cornerSubPix` made SIFT 4× worse** (0.0146 → 0.0577). These detectors are
  already sub-pixel, so `refine_matches` now refuses it by default.
- **ECC's direction convention**: three of four plausible argument arrangements
  give wrong answers, two catastrophically (~48 px), and the returned
  correlation coefficient does **not** distinguish them — a 48 px-wrong result
  scored higher than a correct one.
- The spatial-uniformity gate initially rejected every real result and was
  decoupled from the pass/fail decision.

## Phase 6 — Learned matchers and the VRAM measurement

`match/loftr.py`, `match/superglue.py`, `match/tiled.py`, `match/stitch.py`,
`match/memory.py`, `match/benchmark.py`.

Constraint: measure VRAM headroom empirically rather than assuming a number.

- **`device.py`'s cost model was wrong.** It modelled the coarse score matrix
  alone — pure S⁴ — and underestimated 1024 px by about 4×, which would have
  handed out tile sizes that OOM. Measurement showed two terms:
  `3203 B/px × S² + 4 × (S/8)⁴`, with the local exponent climbing from
  side^1.83 to side^3.69.
- **Break points**: LoFTR fp32 between 1024 and 1152 px; LightGlue between 1536
  and 2048 px. The failing allocation at 1152 px is 1,719,926,784 bytes, and
  ((1152/8)²)² × 4 is 1,719,926,784 exactly — the score matrix, confirmed rather
  than inferred.
- Deduplication across tile boundaries measured: at 0.5 overlap, 2042 raw
  matches collapse to 626 distinct ones. Without it a run would report 3.3× more
  correspondences than it has.
- **SuperGlue cannot ship** — noncommercial-research-only weights. The wrapper
  raises `PermissionError` unless explicitly acknowledged. LightGlue
  (Apache-2.0) is the substitute.

All figures are host RSS: this machine's NVIDIA kernel module is not loaded and
PyTorch is a CPU-only build. The fp16 factor remains unmeasured — CPU bf16
autocast is emulated here and did not finish a 512 px pass in 15 minutes.

## Phase 7 — Error attribution and the metric replacement

`eval/scenes.py`, `eval/error_budget.py`, `eval/conditioning.py`.

Synthetic lunar scenes with a **known** transform, which is what makes stage
attribution possible at all.

- **The refinement stage sets the accuracy floor, not the matcher.** Four
  matchers on one pair converge to identical final error (0.011 / 0.092 /
  0.304 px at 0° / 15° / 30° azimuth difference) from RANSAC fits differing by an
  order of magnitude.
- Acting on that: local-contrast normalisation before ECC cuts 30° error **4.8×**
  and wins 100% of runs over 6 seeds × 2 matchers once illumination differs.
- **Automatic selection of that prefilter failed.** NCC falls both for
  illumination change and for sensor noise and the right response is opposite;
  it chose wrongly on a same-illumination noisy pair. The `"auto"` mode ships
  **disabled and documented as defective**.
- **The uniformity metric is a weak proxy** — Spearman −0.52 against true error,
  and wrong in both directions on realistic layouts. Replaced as the gate by
  bootstrap conditioning at **+0.78**. U retained as a diagnostic.
- Classical matchers fail outright past ~30° azimuth: **228 correct matches at
  15°, 4 at 30°, 0 at 60°.**

## Phase 8 — Persistence, dashboard, showcase

`results.py`, `pipeline.py`, `dashboard/app.py`, `web/`.

Nothing had been persisted per-pair, so nothing could be browsed after a run.
Added a parquet index plus per-pair `.npz`, then a Streamlit tool and a React
showcase (`web/`, with `web/DESIGN.md` recording the visual system).

Also in this phase: Makharia et al. read in full. Their RMSE is the
self-residual (§4.7.1), so their numbers cannot be placed beside a truth-based
figure. Their IIRS work matches against **LRO WAC at 1.25×**, never a
high-resolution camera — which reshaped the cross-modal architecture in
`docs/CROSS_MODAL_IIRS.md`.

## Phase 9 — First contact with real data

Real Chandrayaan-2 products arrived from PRADAN. Five completed before the
download stopped: 2 OHRC, 3 TMC-2. No IIRS.

- **Field map verified.** `probe-label` against a real OHRC label resolved
  **22 of 25 fields**, including all eight corners and both sun angles. Geometry
  provenance went from 10 UNVERIFIED to **12 VERIFIED / 6 UNVERIFIED**.
- `incidence_angle_deg` was a **name miss** — ISRO calls it `solar_incidence`.
  The old guess silently resolved to `None`. Confirmed by
  6.729185 + 83.270815 = 90 exactly on the same label.
- Binary layout **cross-validated**: 101,074 × 12,000 = 1,212,888,000, exactly
  the `.img` byte length.
- **A corner-ordering "critical bug" was reported and then retracted.** The
  throwaway check built the ring in numeric order; `footprint_from_row` already
  traverses 1, 2, 4, 3. A regression test now pins it.
- **The real blocker**: `POLAR_LATITUDE_DEG = 80.0` rejected *all three* real
  OHRC products, which sit at −85°. Fixed by clipping in an azimuthal
  equidistant frame. The three now validate `ok` at 78.89 / 78.96 / 79.33 km²
  with pairwise overlaps of **69.30 / 65.97 / 74.22 km²** — the project's first
  real overlap detection.
- **The four-corner homography measured 639 m median error** on a real OHRC
  strip (2554.6 px at 0.25 m/px), reproduced independently from the raw CSV. It
  is worse than the plain affine it generalises. ISRO ships a per-product
  geometry grid (`_g_grd_d18.csv`, 122,452 measured points) that replaces it;
  `ingest/geometry_grid.py` now loads it.
- **The manifest was discarding the corners** it had just verified, reducing them
  to a bounding box and inflating footprint area **3.9–4.2× on OHRC**. Fixed.

End state: **431 passed, 1 skipped**, ruff clean.
