# P26166 — SIH 2026 Idea Presentation: Slide-by-Slide Content

Built against the official SIH 2026 Idea Presentation template (6 slides max, including title; points/diagrams only, no paragraphs; must be uploaded as PDF). Content below is trimmed to what actually fits on each slide at a readable font size — copy-paste directly, no further cutting needed.

---

## Slide 1 — Title Page

- **Problem Statement ID:** 26166
- **Problem Statement Title:** Multi-modal, Sun angle and scale invariant image correspondence using Chandrayaan-2 optical images (OHRC, TMC and IIRS)
- **Theme:** Space Technology
- **PS Category:** Software
- **Team ID:** *(fill in)*
- **Team Name:** *(fill in)*

---

## Slide 2 — Idea Title / Proposed Solution

**Idea title (suggested):** *"Illumination-Robust Multi-Sensor Lunar Image Registration Pipeline"*

**Proposed Solution** *(brief — approach detail is on the next slide):*
- Problem: sun-angle, viewpoint & scale differences break matching between Chandrayaan-2 and reference lunar imagery
- Solution: an automated pipeline delivering sub-pixel, uniformly-distributed correspondence, robust to all three
- Novelty: validated against the latest published Chandrayaan-2 benchmark; reports its own spatial-uniformity metric

---

## Slide 3 — Technical Approach

### 3a. Technologies to be used
Stack: Python, OpenCV, PyTorch, pretrained LoFTR/SuperGlue, GPU RTX 4060/3060

### 3b. High-Level Design (HLD) Architecture

A layered pipeline — each layer has one responsibility, a fixed input from the layer before it, and a fixed output for the layer after it. The matching engine is a swappable plug-in point.

```
1· DATA INGESTION       PRADAN/PDS4 reader (OHRC/TMC-2/IIRS) + LROC/SELENE
                         fallback fetcher + metadata (GSD, sun angle)
        ↓
2· PREPROCESSING        GSD-aware resample · IIRS band reduce → grayscale
                         · tile large OHRC frames for VRAM limits
        ↓
3· MATCHING ENGINE       ┌─ Classical: phase-congruency / RIFT-style ─┐
   (pluggable, dual)      └─ Deep: pretrained LoFTR / SuperGlue ──────┘
                              → track combiner/selector
        ↓
4· GEOMETRIC VERIFICATION  RANSAC + homography → uniform-coverage grid
   & REGISTRATION           → sub-pixel refinement (NCC)
        ↓
5· OUTPUT / PRODUCT      registered image + match points + metrics
                         (RMSE, inlier ratio/count, coverage score)
```

*(Render as a 5-box vertical flow diagram on the actual slide — matches the "diagrams over text" rule.)*

**Why this shape:** ingestion/preprocessing isolate sensor quirks from matching · matching engine is swappable without touching other layers · sub-pixel accuracy and uniform coverage are enforced as explicit steps, not side effects · output layer maps directly to the problem statement's two required deliverables.

---

## Slide 4 — Feasibility and Viability

- Feasible zero-shot — no training needed; POC realistic within days on RTX 4060/3060
- Public LRO NAC data unblocks Day 1 while PRADAN access (turnaround unverified) is pending
- Risk: OHRC's large tiles (VRAM limits); IIRS hyperspectral vs. panchromatic mismatch
- Mitigation: tiled OHRC processing, IIRS band-select/PCA, classical track as shadow fallback

---

## Slide 5 — Impact and Benefits

- Automates manual ground-control-point tagging
- Fuses Chandrayaan-2, LRO & SELENE into one coordinate frame
- Supports landing-site selection, DEM generation, change detection
- Generalizes to Mars and other ISRO multi-sensor missions

---

## Slide 6 — Research and References

- Makharia et al., arXiv:2509.04775 (2025) — SuperGlue beats classical matchers on real Chandrayaan-2 data
- Lowe, SIFT, IJCV 2004 · Li et al., RIFT, IEEE TIP 2020
- Sarlin et al., SuperGlue, CVPR 2020 · Sun et al., LoFTR, CVPR 2021
- Zitová & Flusser, *Image Registration Methods: A Survey*, 2003
- Data: pradan.issdc.gov.in/ch2 · pds.lroc.im-ldi.com

*(Full 12-source reference list is in `P26166_report.md` §10, if you want more to cite verbally during Q&A.)*
