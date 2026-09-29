# 05 · Feasibility of the project

*Audience: a teammate with a CS background, no remote-sensing background. Terms
defined at first use. Read docs 01, 02, and 04 first.*

**Evidence labels** (same as doc 04): **[MEASURED]** = a real run in this repo
produced it; **[DOCUMENTED]** = from a standard or mission doc; **[EXTRAPOLATION]**
= our reasoning, not tested; **[INSERT RESULT]** = a number no run has produced
yet, deliberately not guessed.

**New words in this doc**

| word | plain meaning |
|---|---|
| **PRADAN** | ISRO's web portal for downloading Chandrayaan-2 data products. Access requires registration and approval. |
| **LRO** | NASA's Lunar Reconnaissance Orbiter — the source of our reference imagery. Its data is on public servers, no login. |
| **NAC / WAC** | LRO's Narrow Angle Camera (~0.5 m/pixel) and Wide Angle Camera (~100 m/pixel). NAC is the natural reference for OHRC; WAC is close to IIRS's scale. |
| **CUDA** | NVIDIA's system for running general computation on a graphics card. "No working CUDA device" means the GPU cannot currently be used for neural-network work on this machine. |
| **CPU-only build** | a version of the deep-learning library (PyTorch) that runs only on the processor, not the graphics card — much slower, and unable to measure real GPU memory use. |
| **RTX 4060** | the target consumer GPU: 8 GB of VRAM. The pipeline is sized to run on this. |
| **CI (continuous integration)** | automatically running the full test suite on every change. |
| **datum** | the reference model of the Moon's shape and size that coordinates are measured against. Two datasets using different datums will not line up even if everything else is correct. |

Feasibility is assessed on five axes: **technical**, **data**, **compute**,
**schedule**, and **risk**. Each is rated and justified with evidence.

---

## 1. Technical feasibility — **demonstrated**

The pipeline is built and internally validated.

| indicator | status | evidence |
|---|---|---|
| End-to-end pipeline exists | yes — ingest → overlap → preprocess → match → align → refine → eval → persist | **[MEASURED]** runs on synthetic and (partially) real data |
| Automated tests | 431 passed, 1 skipped; linter clean | test suite |
| Classical matchers | SIFT, ASIFT, AKAZE, clean-room RIFT2 | **[MEASURED]** benchmarked on synthetic scenes |
| Neural matchers | LoFTR, LightGlue integrated (pretrained) | implemented; **[INSERT RESULT]** GPU run pending (see §3) |
| Robust fitting + sub-pixel refinement | MAGSAC++ then ECC | **[MEASURED]** 0.011–0.304 px true error vs known transform on synthetic scenes |
| Evaluation | RMSE, inlier count, inlier ratio, spatial uniformity, extrapolation uncertainty | **[MEASURED]** all computed; extrapolation uncertainty validated as the best predictor of true error in our tests |
| Real-data ingest | 5 real Chandrayaan-2 products processed (2 OHRC, 3 TMC-2) | **[MEASURED]** 22/25 label fields verified against a real label |

**What first contact with real data proved about feasibility.** The five real
products immediately surfaced three wrong assumptions — a four-corner geometric
model **639 m** in error **[MEASURED — `ingest/geometry_grid.py`]**, a
polar-latitude filter silently rejecting **100%** of real high-resolution data
(fixed) **[MEASURED — `ingest/overlap.py`]**, and footprint areas inflated up to
**4.2×** (fixed) **[MEASURED — `ingest/manifest.py`]**. That the pipeline was
built to catch these — rather than produce plausible wrong output — is the
strongest evidence that the *approach* is sound. Expect more such corrections as
more real data flows through; that is normal and budgeted for.

**Known technical gap:** every headline accuracy number so far is from synthetic
scenes. Synthetic scenes are not a shortcut — they carry an *exact known
transform*, which real data never does, and that is the only way to check whether
an accuracy metric is telling the truth. But the synthetic shading model omits
lunar photometry, detector noise, and real pushbroom distortion.
**[EXTRAPOLATION]** Conclusions about the *ranking* of methods transfer to real
data; **absolute numbers do not** and must be recomputed.

---

## 2. Data feasibility — **partially cleared, on track**

| data | needed for | status |
|---|---|---|
| Chandrayaan-2 OHRC (PDS4) | primary source imagery | **[MEASURED]** 2 real products in hand, ingested and validated |
| Chandrayaan-2 TMC-2 | scale bridge, terrain | **[MEASURED]** 3 real products (a confirmed stereo triple) in hand |
| Chandrayaan-2 IIRS | multi-modal arm | **not yet** — no IIRS download has completed |
| LRO NAC | reference for OHRC | **not yet downloaded** — 3 public mirrors confirmed reachable, no login required |
| LRO WAC | reference for IIRS | **not yet downloaded** — same public archive |
| ISRO per-product geometry grid | correct pushbroom geometry | **[MEASURED]** present for the real OHRC products; loader implemented |

**The one real blocker is a human decision, not a technical one.**
**[MEASURED — `ingest/overlap.py`]** Our downloaded OHRC products sit near the
south pole (latitude −85°); our TMC-2 products sit near the equator (142° east).
They are pictures of *different places*, so the current set yields **zero**
usable cross-instrument pairs — all 9 candidate pairs correctly classified as
`disjoint`. No algorithm fixes two images of different places. Someone has to
**pick a target lunar region** and re-download a co-located set across
instruments plus matching LRO coverage. Until that is done, end-to-end real-data
registration cannot run. Once it is done, the path is clear: LRO data needs no
credentials and the mirrors are confirmed up.

**Secondary data question:** the OHRC label says "selenographic" coordinates with
no datum element (see glossary). Within Chandrayaan-2 this cancels out; it stops
cancelling the moment LRO is introduced. This needs to be resolved before the
first cross-archive registration is trusted. **[UNVERIFIED]** at present.

---

## 3. Compute feasibility — **feasible on target hardware; not yet demonstrated**

**Target:** a single NVIDIA RTX 4060, 8 GB VRAM. The whole design assumes this.

| aspect | status | evidence |
|---|---|---|
| Neural matchers run without training | yes — pretrained / zero-shot, no training loop, no dataset, no checkpoints | design decision; **[EXTRAPOLATION]** this is what makes "prototype in weeks on one consumer GPU" true |
| Memory budget characterised | yes | **[MEASURED — `match/memory.py`]** peak activation follows `3203 B/px × S² + 4·(S/8)⁴`; dense-tile cap ≈ 1408 px; LoFTR fp32 breaks between 1024 and 1152 px; LightGlue between 1536 and 2048 px |
| Large images handled | tiling + cross-seam de-duplication | **[MEASURED — `match/tiled.py`, `match/stitch.py`]** at 0.5 tile overlap, 2042 raw matches collapse to 626 distinct — without de-dup a run would over-report correspondences 3.3× |
| Actual GPU run | **not done** | the current development machine's NVIDIA kernel module is not loaded and PyTorch is a CPU-only build |

**Honest caveat on the memory numbers.** **[MEASURED]** They were produced on a
machine with **no working CUDA device**, so they are host-memory proxies, not
true VRAM measurements. The *shape* of the scaling (the rising exponent as tiles
grow, driven by the neural comparison table's `S⁴` term overtaking the CNN's
`S²` term) is trustworthy; the *absolute byte figures are not VRAM* and the code
says so on every run. **[INSERT RESULT]** true VRAM break points, to be
re-measured on an actual RTX 4060 before anyone plans capacity against them.
**[INSERT RESULT]** LoFTR / LightGlue accuracy and timing on a real GPU.

**[DOCUMENTED / EXTRAPOLATION]** Training (if pursued later) needs roughly 3–4×
inference memory, capping a training tile near 512 px at batch 1–2 on 8 GB. Full
fine-tunes of comparable models used 8× datacentre GPUs for a day; the 4060
equivalent is weeks. So training is explicitly *out of scope for this timeframe*
and only the zero-shot path is on the critical path.

---

## 4. Schedule feasibility — **on track for the internal round**

**Done:** full pipeline, 431 tests, synthetic validation, the evaluation
argument, first real-data ingest, three real-data bugs caught and fixed, docs.

**Remaining for a real-data end-to-end result, in order:**

1. Wire ISRO's per-pixel geometry grid into the overlap stage in place of the
   four-corner homography. Justified by a **[MEASURED]** 639 m error. Not yet
   done because it changes *every crop the pipeline produces* and should be a
   deliberate step.
2. **Pick a target lunar region** and re-download a co-located multi-instrument
   set. This is the gating human decision (§2).
3. Download matching LRO NAC coverage — public, no credentials, mirrors
   confirmed reachable.
4. Complete one IIRS download for the multi-modal arm.
5. Run end-to-end on real OHRC ↔ LRO NAC; fill the `[INSERT RESULT]` cells.

**[EXTRAPOLATION]** Steps 1, 3, and 5 are days of work each. Step 2 is a meeting.
Step 4 depends on PRADAN download throughput, which has been the slow link. None
of this requires new research.

---

## 5. Risk register

| risk | likelihood | impact | mitigation |
|---|---|---|---|
| PRADAN download throughput stays slow; IIRS never arrives in time | medium | medium | the OHRC ↔ LRO NAC path (the core deliverable) does not depend on IIRS; IIRS becomes a labelled roadmap item |
| Selected region has poor overlap or poor LRO coverage | low–medium | high | choose the region *from* LRO coverage maps and known Chandrayaan-2 archive density, not blind |
| Real-data accuracy is worse than synthetic and misses "sub-pixel" | medium | medium | this is a *result*, not a failure — report it honestly with the extrapolation-uncertainty map showing where it does and does not hold; the evaluation argument stands regardless |
| Datum / coordinate-system mismatch introduces a systematic offset vs LRO | medium | high | resolve the datum question (§2) before trusting any cross-archive number; a systematic offset is exactly what extrapolation uncertainty *cannot* catch, so it must be checked directly |
| No GPU available for the demo | medium | low–medium | classical matchers run on CPU; neural results presented from a documented GPU run done ahead of time, or on borrowed hardware |
| Reviewer expects a side-by-side comparison with published numbers | high | low | we have a written explanation (doc: MAKHARIA_PARITY) of why the closest paper's RMSE is a different quantity than ours and cannot be tabled beside it; their table is reproduced separately |
| Synthetic-to-real gap larger than assumed | medium | medium | rankings transfer, absolute numbers are recomputed on real data and labelled; no synthetic number is presented as a real one |

---

## 6. Overall assessment

| axis | rating | one-line justification |
|---|---|---|
| Technical | **demonstrated** | pipeline complete, 431 tests, synthetic validation, real-data ingest working and already self-correcting |
| Data | **partially cleared** | real OHRC + TMC-2 in hand; LRO is public and reachable; blocker is choosing a region, not access |
| Compute | **feasible, not yet shown** | zero-shot design fits 8 GB by construction; memory scaling characterised; real-GPU run still pending |
| Schedule | **on track** | remaining steps are engineering and one decision, no open research on the critical path |
| Risk | **manageable** | the one high-impact risk (datum offset) has a concrete check; the core deliverable does not depend on the slowest data (IIRS) |

**The project is feasible.** The registration machinery is built and tested; the
honest-evaluation contribution is the strongest and most defensible part; the
remaining work to a real-data result is engineering plus one region-selection
decision, with public reference data and no unsolved research standing in the
way. Every number in this assessment came from a real run or is marked
`[INSERT RESULT]`; nothing is estimated.
