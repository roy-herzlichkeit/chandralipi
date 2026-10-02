# CONTEXT.md — Chandralipi

Entry point for a reader with no prior exposure to this project. Written for a
model or engineer picking it up cold.

| | |
|---|---|
| **What** | Lunar image registration: find corresponding points between Chandrayaan-2 optical imagery and a lunar reference, to sub-pixel accuracy, spread evenly across the frame |
| **For** | Smart India Hackathon 2026, problem **SIH26166**, Indian Space Research Organisation |
| **Team** | Severed Department, IIIT Bhubaneswar |
| **Language** | Python 3.10+, package `src/lunar_reg/` |
| **Tests** | `bash scripts/ci.sh` (ruff + CPU suite); last saved run: 984 passed, 21 deselected, ruff clean (`docs/results/ci_20261002.txt`) |
| **Size** | [INSERT RESULT] (no run artefact records the line count) |
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
showcase. Status as of 2026-10-02, each item from the artefact it cites:

- **Real data on disk.** `lunar-reg catalog` reports OHRC, TMC-2, IIRS,
  LRO NAC and the LRO NAC DTM as present and SELENE TC as partial, with the
  product count per instrument (`docs/results/catalog_20261002.txt`).
- **Live result store** (`data/processed/results/`), all real data, none
  synthetic. Counts from `docs/results/live_store_20261002.txt`: 16 results (index rows, one per image pair and matcher) and 31 classified failures.
  The 16 results cover 4 distinct image pairs (`docs/results/live_store_pairs_20261002.txt`).
  Results per sensor combination (`docs/results/live_store_20261002.txt`): 4 OHRC raw vs LRO NAC (1 image pair, 4 matchers), 2 TMC-2 vs the TMC-2 ortho product (1 image pair, 2 matchers), 10 JAXA Kaguya TC vs itself or LRO WAC (2 image pairs, 5 matchers each; image-pair split from docs/results/live_store_pairs_20261002.txt).
  The showcase export `web/public/data/results.json` was regenerated on
  2026-10-02 from the same store.
- **Chandrayaan-2 OHRC vs LRO NAC (Vikram site).** The 2024-04-25 OHRC strip
  registers against the LRO NAC orthoimage; the first run's write-up is
  `docs/results/vikram_2024.md`, the current re-run is
  `data/processed/vikram/runs/p1_19_anchor/`. The three 2023-08-23 strips do
  not register; `docs/VIKRAM_2023_DIAGNOSIS.md` gives the experiment, and
  `data/processed/vikram/exp1_gate.json` records the gate decision BUILD_1B.
- **IIRS** has been run against TMC-2 and produced only classified failures
  (`docs/results/live_store_20261002.txt`); IIRS ↔ optical is still open.
- **JAXA/NASA substitute (2026-09-08/09).** Run while PRADAN was unreachable;
  write-up in `docs/results/jaxa_wac_2026-09-08.md`, summarised in
  `CONTEXT_HANDOFF.md` §7.

Self-residual numbers on real pairs are fit agreement, not accuracy: no real
pair has ground truth.

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
   `ingest/fieldmap.py` (`lunar-reg fields` prints the count per member) and
   `ParamSource` in `preprocess/params.py` (`lunar-reg params` prints the
   count per member); new numbers carry `lunar_reg.provenance.ValueSource`.
   A disclaimer at the top of a module does not survive being copied into a
   report; a field does.

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

- **The live store mixes Chandrayaan-2 and JAXA/NASA results.** Every row in
  `data/processed/results/` is real data, but not every row is Chandrayaan-2:
  the `JAXA_SELENE_TC` and `LRO_WAC` rows are the JAXA/NASA substitute
  (`docs/results/jaxa_wac_2026-09-08.md`); counts per sensor pair are in
  `docs/results/live_store_20261002.txt`. The generated OHRC/TMC-2/IIRS scene
  set is not in the live store; `scripts/build_demo_results.py` regenerates it
  into its default output path, `data/processed/results_ch2_synthetic_backup/`.
  Do not read "real result" in this repo as "Chandrayaan-2 result"
  without checking the sensor name.
- **Truth-based metrics about OHRC/TMC-2/IIRS are from synthetic data** unless
  they say otherwise; on real pairs only self-residual metrics exist.
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
  a design for scaling out. Nothing in it is implemented. Single-GPU runs do
  exist: the run records name the device, e.g. `cuda:0 NVIDIA GeForce RTX 4060
  Laptop GPU` in `data/processed/vikram/runs/p1_19_anchor/run_record.json`.

## Immediate next steps

The phased plan carries them: `PHASES.md` lists the phases and `STATUS.md`
names the current prompt. The exp-1 gate decision that opens Phase 1B is in
`data/processed/vikram/exp1_gate.json`.
