# CONTEXT.md — Chandralipi

Entry point for a reader with no prior exposure to this project. Written for a
model or engineer picking it up cold.

| | |
|---|---|
| **What** | Lunar image registration: find corresponding points between Chandrayaan-2 optical imagery and a lunar reference, to sub-pixel accuracy, spread evenly across the frame |
| **For** | Smart India Hackathon 2026, problem **SIH26166**, Indian Space Research Organisation |
| **Team** | Severed Department, IIIT Bhubaneswar |
| **Language** | Python 3.10+, package `src/lunar_reg/` |
| **Tests** | 431 passed, 1 skipped; `ruff` clean |
| **Size** | ~17,800 lines across `src/`, `tests/`, `scripts/` |
| **Review** | `FABLE_REVIEW.md` — ten open questions for an adversarial second pass; four are scoped in as the current pass |

## Where to look first

| Document | Contains |
|---|---|
| **`CONTEXT_HANDOFF.md`** | **The detailed status review.** Known data issues, known result issues, what needs a human decision, current metrics. Read this second. |
| `TIMELINE.md` | How the project got here, phase by phase, reconstructed from the development transcript |
| `docs/CROSS_MODAL_IIRS.md` | IIRS↔panchromatic architecture; every claim tagged PAPER / MEASURED / EXTRAPOLATION / UNVERIFIED |
| `docs/MAKHARIA_PARITY.md` | Why our numbers cannot be placed beside the closest published work's |
| `docs/REPORT_SECTION.md` | Draft results section for submission |
| `docs/VRAM_CONSTRAINTS.md` | Measured tiling limits |
| `web/DESIGN.md` | Showcase site visual system |
| **`FABLE_REVIEW.md`** | **Ten open questions for an adversarial second pass**, each with the code path, why it is uncertain, and what a useful answer looks like. Carries an explicit budget: four questions are in scope, the rest are recorded for a later reviewer. Read this if you are the reviewer. |
| `udocs/` | Eighteen learning notes for a software engineer with no domain background. Gitignored; not part of the deliverable. Includes `60_MATHS.md` (every formula derived), `61_ML_and_where_it_fits.md` (what learning is used and what would help), `70_SYSTEM_DESIGN_distributed_gpu.md` (a scale-out design, **not built**). |

## The one-paragraph state

The pipeline is complete and internally validated: ingest, footprint overlap,
preprocessing, classical and learned matchers, robust fitting with sub-pixel
refinement, evaluation, per-pair persistence, a Streamlit tool, and a React
showcase. **Its contact with real Chandrayaan-2 data is hours old.** Until
recently every result came from synthetic scenes. Five real products have now
been processed; that immediately verified 22 of 25 metadata fields, exposed a
polar-rejection blocker that discarded 100% of real OHRC data (fixed), and
measured a 639 m error in the four-corner homography that every crop went
through (a replacement now exists but is not yet wired in). The honest summary:
*the machinery is built and tested; its first real data has already overturned
three assumptions, and more should be expected.*

## Architecture

```
src/lunar_reg/
  ingest/       PDS4 labels, field map with per-field provenance, footprint
                overlap on the lunar sphere, geometry grid, pseudo ground truth
  preprocess/   Makharia-style chain, every step independently toggleable
  match/        SIFT/ASIFT/AKAZE, clean-room RIFT2, LoFTR, LightGlue,
                licence-gated SuperGlue, tiled inference with stitching
  align/        MAGSAC++, inlier refit, ECC with local-contrast prefilter
  eval/         metrics, uniformity, bootstrap conditioning, error attribution,
                synthetic scene generator
  results.py    per-pair persistence (parquet index + .npz)
  pipeline.py   end-to-end runner; failure is a classified outcome, not an
                exception
```

## Three conventions that are load-bearing

These are not style preferences; violating them has caused real bugs here.

1. **Provenance is carried in the code, not in prose.** `Provenance` in
   `ingest/fieldmap.py` (12 VERIFIED / 5 DOCUMENTED / 6 UNVERIFIED) and
   `ParamSource` in `preprocess/params.py` (9 PAPER / 5 PAPER_RANGE /
   15 PLACEHOLDER). A disclaimer at the top of a module does not survive being
   copied into a report; a field does.

2. **Failure is classified, counted, and sampled — never skipped.**
   `OverlapStatus` has one member per failure mode; `OverlapDiagnostics`
   accumulates counts and retains a sample of each. A count says how widespread
   something is, a sample says what it looks like, and diagnosis needs both.

3. **Numbers come from runs.** No figure is stated that has not been produced.
   Where something cannot be measured on this hardware, that is said rather than
   estimated — see the VRAM section of `CONTEXT_HANDOFF.md` for the clearest
   example, and `ingest/pseudo_gt.py::estimate_confidence`, which returns `None`
   for a total rather than summing over unknown terms.

## What is most likely to mislead a new reader

- **Every headline metric is from synthetic data** unless it says otherwise.
  Rankings transfer; absolute numbers do not.
- **RMSE in this repo means two different things.** The conventional
  self-residual and the truth-based figure differ by 12.7× to 58.6× on the same
  pairs. `eval/metrics.py` computes the former; `eval/error_budget.py` the
  latter.
- **`docs/` is the deliverable; `udocs/` is gitignored personal notes.** The
  `udocs/` set is complete (18 files) and every number in it is traceable to a
  named module, but it is written for one reader and is not reviewed output.
- **`web/` is a separate artefact.** A React showcase site that reads a static
  JSON export. It does not call the Python package and is not part of the
  deliverable. Changes there never affect a result.
- **`70_SYSTEM_DESIGN_distributed_gpu.md` describes nothing that exists.** It is
  a design for scaling out. Nothing in it is implemented, and no run on a GPU of
  any kind has ever happened in this project.

## Immediate next steps

1. Wire `ingest/geometry_grid.py` into `overlap.py`, replacing the four-corner
   homography (measured 639 m median error).
2. Choose a target lunar region. The downloaded OHRC (polar, −85°) and TMC-2
   (mid-latitude) products **do not overlap each other**, so the current set
   yields zero cross-instrument pairs. This is a human decision and blocks the
   useful next step.
3. Fetch matching LRO NAC coverage — public archive, no credentials, three
   mirrors confirmed reachable.
4. Complete an IIRS download; none finished.
