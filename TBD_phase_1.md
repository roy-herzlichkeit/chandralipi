[← back to index](TBDs.md) · next: [Phase 2](TBD_phase_2.md)

# Phase 1 — Close out classical/neural results (pre-cluster)

Source: `CONTEXT.md` "Immediate next steps", `CONTEXT_HANDOFF.md` §3 and §6.
Goal: what you'd want settled before presenting classical/neural results as
the first act of the demo. Independent of the cluster-computing phases; can
run in parallel with the start of Phase 2.

## 1.1 Wire `geometry_grid.lonlat_to_pixel` into `overlap.py`
- **File(s):** `src/lunar_reg/ingest/geometry_grid.py` (exists, built and
  validated), `src/lunar_reg/ingest/overlap.py` (`geographic_to_pixel_transform`,
  the function it would replace — currently untouched).
- **Current state:** the four-corner homography currently in use was measured
  wrong by 639 m median error on real OHRC (2554.6 px), 18.5 km on TMC-2
  (`CONTEXT_HANDOFF.md` §1.3). The replacement exists, is independently
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
  regions, none within 65° longitude of each other (`CONTEXT_HANDOFF.md` §1.1c).
  Zero cross-instrument Chandrayaan-2 pairs are possible with what's downloaded.
- **This is flagged as a human decision, not an implementation task** — it needs
  someone to pick a region where OHRC/TMC-2/IIRS coverage is known or likely to
  intersect, then build a footprint-filtered PRADAN cart for exactly that region
  (single digits to low tens of files per instrument, per the recommendation
  already in `CONTEXT_HANDOFF.md` §1.1c — not the previous 500-file-per-instrument
  carts, which produced ~975 GB against 830 GB free and still didn't overlap).
- **Done when:** at least one OHRC↔TMC-2 (and ideally OHRC↔IIRS) pair has
  nonzero overlap area from `lunar-reg overlap`.

## 1.3 Fetch matching LRO NAC coverage for the selected region
- **File(s):** `src/lunar_reg/ingest/lro.py` (written, never run on a real
  product — `CONTEXT_HANDOFF.md` §1.6).
- **Current state:** only LRO WAC (100 m/px) has been fetched, and not through
  this project's own ingest path — it was a `vsicurl` windowed read used as a
  substitute during the JAXA/NASA real-data run (§7). LRO NAC (0.5 m/px, the
  actual OHRC counterpart) has never been fetched.
- **Blocked on:** 1.2 (needs the target region first). Public archive, no
  credentials, three mirrors already confirmed reachable per `CONTEXT.md`.
- **Done when:** `ingest/lro.py`'s own code path (not an ad hoc `vsicurl` read)
  has ingested a real LRO NAC product over the selected region.

## 1.4 Complete an IIRS download
- **File(s):** `src/lunar_reg/preprocess/hyperspectral.py` (exists, never seen
  a real cube — `CONTEXT_HANDOFF.md` §1.7).
- **Current state:** zero IIRS products have finished downloading. Everything
  about IIRS in this repo is design, not result.
- **Done when:** one real IIRS cube has been read by `hyperspectral.py` and its
  band-reduction step has run on real (not synthetic) data.

## 1.5 Decide the datum/coordinate-convention question
- **File(s):** affects any code mixing Chandrayaan-2 geometry with LRO products.
- **Current state:** the OHRC label says "selenographic coordinates" with no
  stated `unit` or coordinate-system element — planetocentric vs. planetographic
  and the reference radius are unstated (`CONTEXT_HANDOFF.md` §1.3, §3 item 4).
- **Blocked on:** 1.3 — this only matters once an LRO product is actually being
  mixed with Chandrayaan-2 geometry.
- **Done when:** a stated convention is picked and documented next to
  `geometry_grid.py`, with a test asserting the two coordinate systems agree
  within a stated tolerance on one real overlapping pair.

## 1.6 Minor: same-sensor overlap double-count
- **File(s):** `src/lunar_reg/ingest/overlap.py`, the pair-search step.
- **Current state:** a same-sensor scan compares each product with itself and
  counts each pair twice — 3 products gave 9 "pairs" (3 self-pairs + 3 real
  pairs counted in both orderings) — `CONTEXT_HANDOFF.md` §6 item 5. Harmless
  for reporting, wrong for any count of distinct overlaps.
- **Done when:** pair search excludes self-pairs and counts each unordered pair
  once, with a regression test on the 3-product case that currently over-counts.

## 1.7 Open decisions that gate what can be claimed (need a human call, not code)
Carried verbatim from `CONTEXT_HANDOFF.md` §3 — listed here because each one
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

---
[← back to index](TBDs.md) · next: [Phase 2](TBD_phase_2.md)
