# P26166 — Multi-modal, Sun-Angle and Scale-Invariant Image Correspondence Using Chandrayaan-2 Optical Images

**Organization:** ISRO / Department of Space | **Theme:** Space Technology | **Category:** Software

---

## 1. Problem Statement Summary

Build a **generic software solution** that finds correspondence (match points) between Chandrayaan-2 optical images (OHRC, TMC-2, IIRS) and reference lunar images (LRO NAC, SELENE), then geometrically aligns the source image to the reference image. The output must have:

- **Sub-pixel accuracy** in the located match points.
- **Uniform spatial distribution** of match points across the image (not clustered in a few high-texture regions).
- A **registered product** plus **quantitative evaluation metrics** (e.g. RMSE, inlier count, inlier ratio).

Three coupled difficulties make this hard:

| Challenge | Cause | Effect on matching |
|---|---|---|
| Illumination variation | Different sun azimuth/elevation between passes | Same crater/ridge looks radiometrically different; shadows appear/disappear/move; breaks intensity-gradient-based descriptors (plain SIFT) |
| Viewpoint variation | Different orbit geometry/camera orientation | Shift, rotation, and perspective distortion between source and reference |
| Scale variation | Missions fly at different altitudes/GSDs | Same feature spans very different pixel counts across sensors (0.25 m to 80 m/pixel — a >300× range) |

---

## 2. Dataset

### 2.1 Source imagery — Chandrayaan-2 optical payloads

| Payload | GSD (resolution) | Orbit altitude | Swath | Spectral | Format | Notes |
|---|---|---|---|---|---|---|
| **OHRC** (Orbiter High Resolution Camera) | ~0.25–0.3 m/px | 100 km | 3 km | Panchromatic | PDS4 (raw + calibrated) | Highest-res lunar orbiter camera flown to date; very large full-res tiles |
| **TMC-2** (Terrain Mapping Camera-2) | 5 m/px | 100 km | 20 km | Panchromatic, 0.4–0.85 μm | PDS4 (raw/calibrated/derived incl. GeoTIFF DEM/ortho) | Tri-stereo (fore/nadir/aft) — built for DEM generation |
| **IIRS** (Imaging Infrared Spectrometer) | 80 m/px | 100 km | 20 km | Hyperspectral, ~256 bands, 800–5000 nm, 12-bit | PDS4 | Not directly comparable to panchromatic references without band reduction |

**Access:** All three are archived per PDS4 standard on ISRO's PRADAN portal (`https://pradan.issdc.gov.in/ch2/`), which requires account signup. Browsing is also available at `https://chmapbrowse.issdc.gov.in/`.
**Risk flag:** We could not verify anywhere (portal docs, forums, papers) whether PRADAN account approval is instant or manually gated with a multi-day wait. **Treat this as an unknown, non-zero delay — do not block Day 1 work on it** (see §7, §8).

### 2.2 Reference imagery

| Source | GSD | Orbit altitude | Access | Notes |
|---|---|---|---|---|
| **LRO NAC** (Lunar Reconnaissance Orbiter, Narrow Angle Camera) | ~0.5 m/px | ~50 km | **Fully public, no login** — bulk PDS archive at `https://pds.lroc.im-ldi.com/` (~105,828 products, ~10 TB); mirrored at USGS (`ode.rsl.wustl.edu`, `pds-geosciences.wustl.edu`) | The domains in the official PS text (`lroc.im-ldi.com`, `quickmap.lroc.im-ldi.com`) are the real current ASU domains post-migration, not typos. QuickMap is a viewer; use the PDS archive for bulk pixel downloads. |
| **SELENE / Kaguya** (JAXA) — Terrain Camera / Multiband Imager | TC: 10 m/px; MI: 20 m (VIS) / 62 m (NIR) | — | JAXA DARTS archive (`https://darts.isas.jaxa.jp/planet/pdap/selene/`) has an unverified click-through/approval step; confirmed no-login fallbacks: NASA PDS Imaging Node (`pds-imaging.jpl.nasa.gov`) and AWS Open Data (`registry.opendata.aws/jaxa-usgs-nasa-kaguya-tc/`) | Use as a secondary reference source if LRO NAC coverage is insufficient for a given site |

### 2.3 Practical implication for the project

Because LRO NAC is public and instantly downloadable while Chandrayaan-2/PRADAN access has an unknown lead time, the recommended approach is:
1. Register on PRADAN on Day 1 regardless (start the clock).
2. Immediately pull public LRO NAC tiles to unblock pipeline development.
3. Once PRADAN access clears, swap in real OHRC/TMC-2 pairs against the same LRO NAC references — the pipeline code doesn't need to change, only the input tiles.

---

## 3. Core Technical Challenges (mapped to technique choice)

- **Illumination/sun-angle invariance** → needs descriptors built on *structure* (edges, corners, phase) rather than raw intensity gradients, since intensity relationships between source/reference are nonlinear and unstable under illumination change.
- **Viewpoint invariance** → needs affine/perspective-tolerant detection (multi-scale, multi-orientation) plus a robust outlier-rejecting geometric fit (RANSAC + homography/affine).
- **Scale invariance** → needs either (a) inherently scale-invariant detectors (SIFT-family, learned detectors with multi-scale training) and/or (b) GSD-aware pre-resampling using each payload's known, calibrated pixel scale (metadata-driven, not purely visual) since the scale ratios here are extreme (up to ~300×) and too large for detector scale-invariance alone.

---

## 4. Literature / State of the Art

### 4.1 Classical, illumination-robust techniques
Plain **SIFT** (Lowe, *IJCV* 2004) and **ASIFT** (Yu & Morel, *SIAM J. Imaging Sci.* 2009) are scale/affine-invariant but only *geometrically* — both are known to be weak under strong, nonlinear illumination change, which is exactly this problem's core difficulty. Purpose-built alternatives instead use phase/structure information:

- **RIFT** (Li, Hu, Ai, *IEEE TIP* 2020) — phase congruency + log-Gabor "maximum index map" descriptor, designed for nonlinear radiometric differences across sensors.
- **HOPC** (Ye et al., *IEEE TGRS* 2017) — histogram of oriented phase congruency + normalized cross-correlation similarity.
- **OS-SIFT** (Xiang et al., *IEEE TGRS* 2018) — built for optical–SAR fusion, same underlying nonlinear-intensity problem.
- **PSO-SIFT** (Ma et al., *IEEE GRSL* 2017) — redefines the SIFT gradient to resist nonlinear intensity shifts.

### 4.2 Deep-learning matchers
Modern learned matchers can be run **zero-shot** (pretrained, no training required) and are light enough for 6–8 GB consumer GPUs:
- **SuperPoint** (DeTone et al. 2018) + **SuperGlue** (Sarlin et al., *CVPR* 2020) — detector + learned graph-based matcher.
- **LoFTR** (Sun et al., *CVPR* 2021) — detector-free transformer matcher, simpler pipeline (no separate keypoint detector).
- **LightGlue** (Lindenberger et al., *ICCV* 2023) — faster, adaptive successor to SuperGlue.
- (D2-Net, R2D2, DISK are further alternatives, generally similar tier to the above.)

### 4.3 Directly relevant prior work — key finding
**Makharia et al., "Comparative Evaluation of Traditional and Deep Learning Feature Matching Algorithms using Chandrayaan-2 Lunar Data," arXiv:2509.04775 (Sept 2025)** benchmarks SIFT/ASIFT/AKAZE/RIFT2 vs. SuperGlue **on real TMC-2/OHRC data pulled from PRADAN** — the same dataset and problem this project targets. **SuperGlue won on both RMSE and speed.** This is strong, citable, in-domain evidence that a pretrained deep-learning matcher is the stronger technical bet for this exact problem, and it substantially de-risks attempting a deep-learning-based POC in a 6-day window (no training required, just inference).

Other adjacent work found: MoonMetaSync (arXiv:2410.11118, 2024); an MDPI *Remote Sensing* 2025 paper on multi-illumination lunar orbiter image matching (title confirmed, full detail not accessible); Wu, Zeng, Hu (*Planetary and Space Science* 152:45, 2018) — illumination-invariant SIFT variant tested on Moon and Mars imagery. No paper was found doing cross-mission Chandrayaan-vs-LRO-NAC deep-learning registration specifically — **this project sits in a narrow, current research niche**, which is a good novelty angle for the slide deck.

### 4.4 Sub-pixel refinement (applied after coarse matching)
- **Normalized cross-correlation (NCC) refinement** — standard photogrammetric practice.
- **Lucas-Kanade** (1981) — iterative gradient-based local alignment.
- **Least-Squares Matching / LSM** (Gruen, 1985) — can reach ~0.01 px under good conditions.
- **Phase-correlation sub-pixel refinement** (Foroosh, Zerubia, Berthod, *IEEE TIP* 2002).

---

## 5. Proposed Pipeline Architecture

```
 Source image (OHRC/TMC-2/IIRS)      Reference image (LRO NAC/SELENE)
            │                                    │
            ▼                                    ▼
   ┌─────────────────────┐            ┌─────────────────────┐
   │  Preprocessing       │            │  Preprocessing       │
   │  - GSD-aware resample│            │  - crop/tile to AOI  │
   │  - IIRS: band-select/│            │                       │
   │    PCA → grayscale    │            │                       │
   └──────────┬───────────┘            └──────────┬───────────┘
              └─────────────┬─────────────────────┘
                             ▼
              ┌───────────────────────────────┐
              │  Dual-track feature matching   │
              │  A) Classical illumination-    │
              │     robust (RIFT/HOPC-style)   │
              │  B) Pretrained deep matcher     │
              │     (LoFTR / SuperGlue)         │
              └────────────────┬────────────────┘
                                ▼
              ┌───────────────────────────────┐
              │  RANSAC geometric verification │
              │  (homography / affine fit,      │
              │   outlier rejection)            │
              └────────────────┬────────────────┘
                                ▼
              ┌───────────────────────────────┐
              │  Grid-based uniformity          │
              │  enforcement (tiled NMS to      │
              │  spread inliers across image)   │
              └────────────────┬────────────────┘
                                ▼
              ┌───────────────────────────────┐
              │  Sub-pixel refinement (NCC/     │
              │  Lucas-Kanade around inliers)   │
              └────────────────┬────────────────┘
                                ▼
              ┌───────────────────────────────┐
              │  Output: registered/warped      │
              │  product + match-point list +   │
              │  metrics report                 │
              └───────────────────────────────┘
```

**Why dual-track (A + B):** classical illumination-robust descriptors give a fast, interpretable, no-GPU-required baseline and fall back gracefully when a deep model struggles on an unfamiliar sensor; the pretrained deep matcher is the stronger performer per §4.3 and needs no training. Running both and reporting both also directly satisfies the problem statement's implicit ask for a rigorously evaluated solution, not a black box.

---

## 6. Evaluation Metrics

- **RMSE** at held-out checkpoints (source vs. transformed reference).
- **Inlier count** and **inlier ratio** (post-RANSAC).
- **Success rate / repeatability** across multiple image pairs and illumination conditions.
- **Spatial coverage / uniformity**: no single standard metric exists in the literature for this (checked — none found); we define our own simple **grid-coverage score** (fraction of an N×N tile grid over the image that contains at least one inlier match) and state explicitly that this is a self-defined metric, not a cited standard.

Canonical reference for registration accuracy/error framework: Zitová & Flusser, "Image Registration Methods: A Survey," *Image and Vision Computing*, 2003.

---

## 7. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| PRADAN approval delay (unverified duration) | Could block access to real Chandrayaan-2 data before Sept 2 | Register Day 1; build/demo entirely on public LRO NAC data in parallel; swap in real data whenever it arrives, pipeline code is data-agnostic |
| OHRC full-resolution tiles (0.25 m/px) too large for 6–8 GB VRAM | OOM during deep-matcher inference | Patch-based/tiled processing with overlap-stitching of matches |
| IIRS is hyperspectral (256 bands), not directly comparable to panchromatic references | Feature matching fails on raw cube | Reduce to a single-band or PCA/grayscale composite before matching |
| Extreme illumination near the terminator (deep shadows) | Feature dropout in shadowed regions | Rely on the illumination-robust classical track (RIFT/HOPC) as fallback; document as a known limitation |
| Deep matcher not trained on lunar/multimodal domain | Possible degraded accuracy vs. §4.3's reported results | Report says off-the-shelf still won in the cited study; light fine-tuning is a prototype-phase stretch goal if PRADAN data volume allows |

---

## 8. Effort Plan

### 8.1 POC — due Sept 2, 2026 (6 working days, 2 active builders)

| Day | Work |
|---|---|
| Day 1 (Aug 26) | Register on PRADAN immediately; pull public LRO NAC tiles; set up environment (Python, OpenCV, PyTorch, pretrained LoFTR + SuperGlue checkpoints); read arXiv:2509.04775 as implementation blueprint |
| Day 2 | Classical baseline: SIFT/RIFT-style features + RANSAC + homography on public pairs; first match visualization |
| Day 3 | Integrate pretrained LoFTR/SuperGlue zero-shot inference on the same pairs; side-by-side comparison vs. classical baseline |
| Day 4 | Sub-pixel refinement (NCC around inliers) + metrics module (RMSE, inlier count/ratio, grid-coverage score) + warped-overlay "registered product" output |
| Day 5 | Swap in real OHRC/TMC-2 pairs if PRADAN access has cleared; otherwise continue on LRO NAC illumination-varied pairs and state that caveat plainly; wrap in a minimal CLI or Streamlit demo |
| Day 6 (Sept 1) | Buffer: bug fixes, record demo, finalize numbers |
| **Sept 2** | **POC deliverable**: script/notebook or minimal app taking two lunar images → match visualization → RANSAC-filtered inliers → registered overlay → metrics table, plus a classical-vs-deep-learning comparison |

### 8.2 Prototype — rest of September

- Real multi-sensor support: handle OHRC/TMC-2/IIRS formats and true scale ratios via GSD-aware pyramids; band-select/PCA-reduce IIRS cubes.
- Strengthen illumination robustness: RIFT/HOPC preprocessing ahead of the deep matcher; light domain fine-tuning if data volume allows.
- Real grid-based uniform-coverage enforcement (tiled non-max suppression, not just a reporting metric).
- Patch-based/tiled processing so full-resolution OHRC frames fit in 6–8 GB VRAM.
- Package as an installable tool with georeferenced output.
- Validate across multiple pairs spanning different illumination/scale conditions; write up results.

---

## 9. Team & Resource Allocation

- **2 active technical builders** — own the pipeline: data ingestion, matching (classical + deep tracks), RANSAC/geometry, sub-pixel refinement, metrics.
- **Remaining ~4 team members** — dataset curation/labeling of checkpoints for RMSE evaluation, report/slide polishing, demo rehearsal, and (once real Chandrayaan-2 data lands) manual sanity-checking of registered outputs against known lunar features.
- **Compute**: RTX 4060 8 GB + RTX 3060 6 GB — sufficient for zero-shot LoFTR/SuperGlue inference on tiled patches; not sufficient for full model training/fine-tuning at scale without patching.

---

## 10. References

1. Makharia et al., "Comparative Evaluation of Traditional and Deep Learning Feature Matching Algorithms using Chandrayaan-2 Lunar Data," arXiv:2509.04775, 2025.
2. Lowe, D., "Distinctive Image Features from Scale-Invariant Keypoints," *IJCV*, 2004. (SIFT)
3. Yu, G. & Morel, J-M., "ASIFT: A New Framework for Fully Affine Invariant Image Comparison," *SIAM J. Imaging Sciences*, 2009.
4. Li, J., Hu, Q., Ai, M., "RIFT: Multi-Modal Image Matching Based on Radiation-Variation Insensitive Feature Transform," *IEEE TIP*, 2020.
5. Ye, Y. et al., "Fast and Robust Matching for Multimodal Remote Sensing Image Registration" (HOPC), *IEEE TGRS*, 2017.
6. Xiang, Y. et al., "OS-SIFT: A Robust SIFT-Like Algorithm for High-Resolution Optical-to-SAR Image Registration," *IEEE TGRS*, 2018.
7. Ma, W. et al., "Remote Sensing Image Registration with Modified SIFT and Enhanced Feature Matching" (PSO-SIFT), *IEEE GRSL*, 2017.
8. DeTone, D., Malisiewicz, T., Rabinovich, A., "SuperPoint: Self-Supervised Interest Point Detection and Description," 2018.
9. Sarlin, P-E. et al., "SuperGlue: Learning Feature Matching with Graph Neural Networks," *CVPR*, 2020.
10. Sun, J. et al., "LoFTR: Detector-Free Local Feature Matching with Transformers," *CVPR*, 2021.
11. Zitová, B. & Flusser, J., "Image Registration Methods: A Survey," *Image and Vision Computing*, 2003.
12. Data portals: PRADAN (`pradan.issdc.gov.in/ch2`), Chandrayaan-2 browse (`chmapbrowse.issdc.gov.in`), LROC PDS (`pds.lroc.im-ldi.com`), JAXA DARTS SELENE (`darts.isas.jaxa.jp/planet/pdap/selene`).

*All facts above were verified against public sources during report preparation (Aug 26, 2026); where a claim could not be verified (e.g. PRADAN approval turnaround time), it is explicitly flagged as unknown rather than assumed.*
