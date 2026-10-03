[← back to index](TBDs.md) · next: [Phase 2](TBD_phase_2.md)

# Phase 1 — Close out classical/neural results (pre-cluster)

Source: `docs/project/CONTEXT.md` "Immediate next steps", `docs/project/CONTEXT_HANDOFF.md` §3 and §6.
Goal: what you'd want settled before presenting classical/neural results as
the first act of the demo. Independent of the cluster-computing phases; can
run in parallel with the start of Phase 2.

## 1.1 Wire `geometry_grid.lonlat_to_pixel` into `overlap.py`
- **File(s):** `src/lunar_reg/ingest/geometry_grid.py` (exists, built and
  validated), `src/lunar_reg/ingest/overlap.py` (`geographic_to_pixel_transform`,
  the function it would replace — currently untouched).
- **Current state:** the four-corner homography currently in use was measured
  wrong by 639 m median error on real OHRC (2554.6 px), 18.5 km on TMC-2
  (`docs/project/CONTEXT_HANDOFF.md` §1.3). The replacement exists, is independently
  cross-checked against the raw CSV, and is not wired in — described as "not a
  change to make without a decision" because it alters every crop the pipeline
  produces.
- **Done when:** `overlap.py` crops use `lonlat_to_pixel`'s per-point line/sample
  mapping instead of `cv2.getPerspectiveTransform` on four corners, and the
  regression suite (currently 431 passing) is re-verified green with the new
  path.

## 1.2 Select a target lunar region and re-download against it
- **File(s):** none yet — this is a data-acquisition decision, not code.
- **Current state:** the currently-downloaded OHRC (−83.9° to −85.5°N), TMC-2
  (−1.9° to −29.6°N), and IIRS (−3.9° to 31.4°N) products sit in three disjoint
  regions, none within 65° longitude of each other (`docs/project/CONTEXT_HANDOFF.md` §1.1c).
  Zero cross-instrument Chandrayaan-2 pairs are possible with what's downloaded.
- **This is flagged as a human decision, not an implementation task** — it needs
  someone to pick a region where OHRC/TMC-2/IIRS coverage is known or likely to
  intersect, then build a footprint-filtered PRADAN cart for exactly that region
  (single digits to low tens of files per instrument, per the recommendation
  already in `docs/project/CONTEXT_HANDOFF.md` §1.1c — not the previous 500-file-per-instrument
  carts, which produced ~975 GB against 830 GB free and still didn't overlap).
- **Done when:** at least one OHRC↔TMC-2 (and ideally OHRC↔IIRS) pair has
  nonzero overlap area from `lunar-reg overlap`.
- **Update 2026-09-28:** region chosen: the **Vikram landing site**
  (−69.9…−68.7°, 31.9…32.8°E), picked from the full ISSDC catalogue, which has
  21 OHRC products over 11 dates there. 4 OHRC raw products are on disk. TMC-2 and
  IIRS are deferred for the demo. See `docs/DATA_ACQUISITION.md`.

## 1.3 Fetch matching LRO NAC coverage for the selected region
- **File(s):** `src/lunar_reg/ingest/lro.py` (written, never run on a real
  product — `docs/project/CONTEXT_HANDOFF.md` §1.6).
- **Current state:** only LRO WAC (100 m/px) has been fetched, and not through
  this project's own ingest path — it was a `vsicurl` windowed read used as a
  substitute during the JAXA/NASA real-data run (§7). LRO NAC (0.5 m/px, the
  actual OHRC counterpart) has never been fetched.
- **Blocked on:** 1.2 (needs the target region first). Public archive, no
  credentials, three mirrors already confirmed reachable per `docs/project/CONTEXT.md`.
- **Done when:** `ingest/lro.py`'s own code path (not an ad hoc `vsicurl` read)
  has ingested a real LRO NAC product over the selected region.
- **Update 2026-09-28:** partially done. The map-projected NAC orthoimages and
  DTM `NAC_DTM_VIKRAMSITE1` are downloaded (4.6 GB), but read by
  `scripts/run_vikram.py`, **not** `ingest/lro.py`. GDAL's geotransform for them
  is wrong (degree pixel size with metre origin); the corrected transform and
  the one inferred sign flip are in `data/raw/reference/lro_nac_vikram/PROVENANCE.json`.
  `ingest/lro.py` still trusts GDAL and would reproduce the bug.

## 1.4 Complete an IIRS download
- **File(s):** `src/lunar_reg/preprocess/hyperspectral.py` (exists, never seen
  a real cube — `docs/project/CONTEXT_HANDOFF.md` §1.7).
- **Current state:** zero IIRS products have finished downloading. Everything
  about IIRS in this repo is design, not result.
- **Done when:** one real IIRS cube has been read by `hyperspectral.py` and its
  band-reduction step has run on real (not synthetic) data.

## 1.5 Decide the datum/coordinate-convention question
- **File(s):** affects any code mixing Chandrayaan-2 geometry with LRO products.
- **Current state:** the OHRC label says "selenographic coordinates" with no
  stated `unit` or coordinate-system element — planetocentric vs. planetographic
  and the reference radius are unstated (`docs/project/CONTEXT_HANDOFF.md` §1.3, §3 item 4).
- **Blocked on:** 1.3 — this only matters once an LRO product is actually being
  mixed with Chandrayaan-2 geometry.
- **Done when:** a stated convention is picked and documented next to
  `geometry_grid.py`, with a test asserting the two coordinate systems agree
  within a stated tolerance on one real overlapping pair.

## 1.6 Minor: same-sensor overlap double-count
- **File(s):** `src/lunar_reg/ingest/overlap.py`, the pair-search step.
- **Current state:** a same-sensor scan compares each product with itself and
  counts each pair twice — 3 products gave 9 "pairs" (3 self-pairs + 3 real
  pairs counted in both orderings) — `docs/project/CONTEXT_HANDOFF.md` §6 item 5. Harmless
  for reporting, wrong for any count of distinct overlaps.
- **Done when:** pair search excludes self-pairs and counts each unordered pair
  once, with a regression test on the 3-product case that currently over-counts.

## 1.7 Open decisions that gate what can be claimed (need a human call, not code)
Carried verbatim from `docs/project/CONTEXT_HANDOFF.md` §3 — listed here because each one
changes what Phase 1's "classical/neural results" slide is allowed to say:
- Whether to accept SuperGlue's noncommercial licence for direct comparability
  with Makharia et al., or stay with LightGlue (Apache-2.0, already shippable,
  a different model — won't reproduce their headline number either way).
- Which of the 11-of-14 `PLACEHOLDER` preprocessing parameters
  (`src/lunar_reg/preprocess/params.py`) to standardize on before the demo, and
  whether tuning them on synthetic data risks overfitting to a shading model
  that isn't the real Moon.
- Whether a synthetic-only result set is acceptable for the round being shown,
  or whether the presentation should wait for/lead with the real JAXA/NASA
  results (`data/processed/demo_real/`, §7) instead.
- Whether shipping with `incidence_angle_deg`/`emission_angle_deg`/
  `phase_angle_deg` unresolved (§1.2) is acceptable — not currently used by any
  matcher, so likely fine, but it's still an open call.

## 1.8 New algorithm: illumination-bridged hybrid (classical + neural) — for Fable

**Owner:** Fable (handover). **Status:** proposed; nothing below is built
except where marked MEASURED/EXISTS.

Evidence labels used throughout: **MEASURED** = produced by a real run in this
repo; **EXISTS** = code already in the repo; **PROPOSED** = design, untested;
**VERIFY** = a literature claim to confirm from the full paper before relying on
it (not written from memory, deliberately).

### Why a new algorithm, from what was actually observed

- **MEASURED (2026-09-28, `data/processed/vikram/README.md`):** OHRC raw ↔ LRO
  NAC orthoimage registers with SIFT, AKAZE, ASIFT and LightGlue when the OHRC
  sun azimuth (304°) is on the same side as the reference's (inferred north-west).
  Uniformity 0.83–0.99; the label corners are 2,939 m off. Without ECC, SIFT and
  LightGlue agree to 2.2 m at the corners (about half a 4 m pixel).
- **MEASURED:** all four matchers fail on three OHRC strips with sun azimuth 62°
  (0–7 raw matches; ASIFT 28–32 candidates, of which 4–5 survive RANSAC). The coarse
  LightGlue pass failed on them too.
- **CAVEAT, must be resolved first:** those failing fine passes searched a
  500 m margin around the *label* position, which is ~2.9 km wrong. So "lighting
  caused the failure" is **not established**; the matchers may not have been
  shown the right ground. Rerun them with `--prior-shift 556,-2888 --margin-m 2000`
  before designing for illumination.
- **MEASURED:** ECC refinement pulls every matcher's estimate to the same
  solution (0.0 m apart). Good for final precision; it also means matcher
  choice only matters for *reaching* ECC's convergence basin.
- **MEASURED:** DISK/LightGlue on CPU costs roughly 2–3 KB per reference pixel,
  so full-resolution neural matching of a 4 km crop is out of reach on a 16 GB machine.
- **MEASURED:** the NAC bundle includes a 3 m DTM (`NAC_DTM_VIKRAMSITE1.TIF`,
  7668×15895, correctly georeferenced in metres).

### Proposed pipeline

1. **Geometric prior — EXISTS, improve.** Label corners today (2.9 km error).
   Wire `geometry_grid.lonlat_to_pixel` (item 1.1) for calibrated products; for
   raw products, keep the wide search window. Search radius should come from
   a stated prior error, not a constant.
2. **Illumination bridge — PROPOSED, the core idea.** Render the reference DTM as
   shaded relief under the **source's** sun azimuth/elevation (read from the OHRC
   label, MEASURED fields), with cast shadows. `eval/scenes.py` already ray-marches
   shadows for synthetic terrain (EXISTS); reuse it on the real DTM. Match OHRC
   against (a) the NAC orthoimage and (b) this rendered image, and keep
   whichever gives the better-conditioned solution. This turns an
   opposite-lighting problem into a same-lighting one. VERIFY: find published
   DEM-shading-based planetary registration and read its reported gains before
   quoting any.
3. **Coarse neural stage — EXISTS, extend.** LightGlue/DISK at 8 m/px over the
   wide window (the current coarse pass), run against both reference
   renderings. Output: translation plus a rough homography.
4. **Fine classical stage — EXISTS.** SIFT/ASIFT/AKAZE at 2–4 m/px in the
   re-centred crop, plus RIFT2 (phase congruency, the repo's illumination-robust
   classical matcher; clean-room, never run on real data). Pool the
   correspondences from every matcher that succeeds.
5. **Consensus and outlier control — PROPOSED.** Robust fit (MAGSAC++ as today)
   on the pooled set. Then a **cross-matcher agreement check before ECC**: fit
   each matcher separately and measure corner disagreement. This is the one
   independent consistency signal available without ground truth (MEASURED
   2.2 m on the 2024 pair). Reject if disagreement exceeds 1 px.
6. **Sub-pixel refinement — EXISTS.** ECC with the local-contrast prefilter,
   seeded by the consensus transform. Then tiled native-resolution (0.25 m)
   matching seeded by the 4 m transform, using `match/tiled.py` and
   `align/warp.py:warp_blockwise` for the output product.
7. **Registered product — EXISTS (2026-09-28).**
   `align/warp.py:save_registered_geotiff` writes the result on the NAC grid with
   provenance tags; `run_vikram.py --export-only` rebuilds GeoTIFFs from stored results.

### Experiments that decide it (in order)

1. Rerun the three 2023 strips with the corrected search area (caveat above). If
   they register, the illumination bridge is lower priority than the prior.
2. Get the reference sun azimuth from SPICE for NAC M1442997156 (currently only
   inferred from the full-moon date). Without it, "opposite lighting" is a hypothesis.
3. Build step 2 on the Vikram DTM. Benchmark: the three 2023 strips.
   Success = ≥ 20 inliers, uniformity ≥ 0.7, and pre-ECC cross-matcher agreement < 1 px.
4. Run RIFT2 on the same strips as the classical baseline for the lighting case.
5. Only then, native-resolution tiled refinement on the successful pairs.

### Settings Fable should know about

- Demo thresholds: `run_vikram.py` defaults to `--min-inliers 5` (the library's
  `PipelineConfig.min_inliers` stays 8). A homography needs 4 points, so 5
  inliers leave one redundant point. Prefer `--model affine` at that level.
  Every result records `min_inliers`, `model` and `search_prior` in its `extra`.
- There is no ground truth on real pairs. The only independent signals are pre-ECC
  cross-matcher agreement and bootstrap conditioning. Don't report self-RMSE as accuracy.
- The NAC absolute georeference is established only to ~1 km (PROVENANCE.json).
  Relative registration is unaffected; absolute lat/lon of the product is not.

---
[← back to index](TBDs.md) · next: [Phase 2](TBD_phase_2.md)
