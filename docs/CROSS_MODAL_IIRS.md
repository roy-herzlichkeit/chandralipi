# Matching IIRS against panchromatic imagery: architecture and plan

**Evidence labelling.** Every claim below is tagged.
`[PAPER]` is demonstrated in the cited work. `[MEASURED]` was measured in this
repository, and says where. `[EXTRAPOLATION]` is our reasoning applied to the
IIRS case and has **not** been tested. `[UNVERIFIED]` is an assumption we have
not been able to check at all.

---

## 1. What the problem actually is

IIRS is ~256 bands over 800–5000 nm at 80 m/px. TMC-2 is panchromatic over
400–850 nm at 5 m/px. OHRC is panchromatic at 0.25 m/px. Two gaps compound:

**Spectral.** The shared spectral support between IIRS and TMC-2 is roughly
800–850 nm — a ~50 nm sliver at the extreme edge of both instruments' ranges.
`[UNVERIFIED: the exact band edges come from the payload summary in
old_assets/P26166_report.md §2.1, not from a product label.]`

Worse, IIRS is not one modality. Below roughly 2500 nm it measures **reflected
sunlight**, so its structure is topographic shading and albedo — the same
physics that forms a panchromatic image. Above roughly 3000 nm it increasingly
measures **thermal emission**, where the sun-facing slopes are warm and shadows
are not black. `[EXTRAPOLATION: the crossover region is well established in
planetary spectroscopy generally, but we have not verified where it falls for
IIRS specifically or how ISRO's calibrated product handles it.]`

The consequence is a design decision, not a nuisance: the short half of the cube
is a near-same-modality matching problem, and the long half is genuinely
visible-to-thermal — the exact setting XoFTR was built for.

**Scale.** IIRS→TMC-2 is 16×. IIRS→OHRC is **320×**.

## 2. The decision that settles most of it

**Do not match IIRS to OHRC. Match IIRS to a reference at its own scale.**

`[PAPER — Makharia et al., arXiv:2509.04775 §4.1.2]` They matched IIRS against
**LRO WAC**, resampling IIRS's ~80 m/px to WAC's 100 m/px — a **1.25× ratio**.
They never attempt IIRS against a high-resolution camera.

Their results show why that works. On IIRS–WAC Equatorial, plain SIFT reaches
RMSE X/Y of 0.6879 / 1.1066 and AKAZE 0.5551 / 1.0841, against SuperGlue's
0.5069 / 0.6167. `[PAPER]` A 0.13 px spread between a 2004 descriptor and a 2020
learned matcher means the cross-modal difficulty had already been removed — by
the choice of reference, not by the matcher.

`[MEASURED — src/lunar_reg/ingest/pseudo_gt.py, tests/test_pseudo_gt.py]` Our
own scan reaches the same conclusion independently: `MAX_DIRECT_SCALE_RATIO` is
8×, IIRS→OHRC is 320×, and `bridge_sensor("IIRS", "OHRC")` returns `TMC2`,
splitting it into 16× and 20×.

So the architecture is a **chain**, never a direct match:

```
IIRS (80 m) ──1.25×──► LRO WAC (100 m)          preferred: same scale, same-ish modality
IIRS (80 m) ──16×────► TMC-2 (5 m)              harder, needed if WAC coverage is absent
TMC-2 (5 m) ──20×────► OHRC (0.25 m)            same modality, existing pipeline handles it
```

**The honest limit of the chain.** `[MEASURED — pseudo_gt.estimate_confidence]`
An IIRS pixel cannot be localised better than its own footprint: quantisation
alone is 80/√12 = **23.09 m**, which is **92 OHRC pixels**. Composing IIRS→TMC-2
with TMC-2→OHRC therefore delivers *IIRS pixel → OHRC region*, never IIRS pixel →
OHRC pixel. Any claim of sub-pixel IIRS-to-OHRC correspondence at OHRC scale is
physically impossible and should be dropped from the pitch.

## 3. Reducing the cube to something matchable

`[PAPER — Makharia et al. §4.2 B]` They selected **"a single, visually clear
band"**, computed the transform on it, and applied that transform to all other
bands. PCA appears only in their OHRC–NAC branch, never for IIRS.

We propose the same shape, with the band choice made physically rather than
visually, and PCA demoted to an ablation arm:

| Arm | Method | Rationale | Status |
|---|---|---|---|
| **A1 (default)** | Integrate IIRS radiance over the reference's spectral response | Produces a synthetic panchromatic band *in the reference's own modality*, and is reproducible scene to scene | `[EXTRAPOLATION]`; needs the response curve, `[UNVERIFIED]` whether it is published in the PDS4 calibration files |
| A2 | Mean of reflectance bands, ~800–1600 nm | Same idea with more photons when A1's window is too narrow for usable SNR | `[EXTRAPOLATION]` |
| A3 | PCA over the **reflectance subset only**, sign-fixed | Ablation arm, to reproduce the paper's OHRC-branch choice | `[EXTRAPOLATION]` |
| A4 | Thermal composite, >3000 nm | Isolates the genuine VIS↔TIR regime for an XoFTR-style matcher | `[EXTRAPOLATION]` |

**Two traps in A3 worth stating**, because a naive PCA implementation hits both.
PC1's sign is arbitrary and flips between scenes, so a learned descriptor sees a
contrast-inverted image from one product to the next unless the sign is pinned
(force positive correlation with the band mean). And PCA over *all* bands mixes
the thermal half into the reflectance half, so the leading component tracks the
scene temperature gradient rather than the topography. Restrict to reflectance
bands first. `[EXTRAPOLATION]`

## 4. The matcher, in order of cost

### 4.1 Baseline: classical, on the reduced band

`[PAPER]` SIFT and AKAZE already reach ~0.5–1.1 px on IIRS–WAC. This is the
starting point and it is nearly free.

`[MEASURED — scripts/build_demo_results.py]` Our own pipeline registers
IIRS-scale pairs at U 0.95–0.99 and extrapolation p95 0.05–0.68 px under mild
illumination change, collapsing to 5.5–6.3 px p95 once the sun azimuth swings
30°. So the classical baseline is adequate *until* illumination diverges, which
is exactly the axis the problem statement is about.

### 4.2 CNSF, for wide illumination gaps

`[PAPER — Remote Sensing 2025, 17(13), 2302, "Robust Feature Matching of
Multi-Illumination Lunar Orbiter Images Based on Crater Neighborhood
Structure"]` Crater detection → Crater Neighborhood Structure Feature
construction → CNSF-similarity matching → outlier removal, evaluated on 321
Multi-illumination Lunar Orbiter Image pairs across latitudes.

**Correction to how this was framed to us:** it is *not* training-free. The
pipeline "integrat[es] deep-learning based crater detection". The *matching*
stage is training-free; the detector is not, and needs a trained crater model.

`[EXTRAPOLATION]` Why it should suit us better than it suits its own paper: a
crater rim is a closed convex ridge with a **physical diameter**, so it is a
landmark whose identity survives both illumination inversion and a scale change.
That makes crater matching a size-and-arrangement problem rather than a texture
problem, which is precisely what a 16× IIRS→TMC-2 gap needs. But CNSF was
demonstrated on **same-instrument, multi-illumination** pairs — not
cross-instrument, not cross-modal, not cross-scale. Treating its published
success as evidence for our case would be exactly the overreach this document is
labelled to prevent.

`[UNVERIFIED]` Whether crater density at 80 m/px is sufficient: only craters
above roughly 400 m are resolved at 5 px. We have not checked counts for any
candidate site.

### 4.3 XoFTR, for the thermal arm

`[PAPER — arXiv:2404.09692]` Architecture: ResNet backbone at 1/8, 1/4, 1/2;
LoFTR-style linear attention at 1/8 with one-to-many assignment; a fine stage
re-matching at 1/2 over 1×1, 3×3 and 5×5 windows; an MLP sub-pixel head. Trained
in two stages — masked image modelling on 95,000 KAIST visible–thermal pairs
(9 epochs, 24 h on 2×A5000), then fine-tuning on MegaDepth at 640×640 with
pseudo-thermal augmentation (24 h on **8×A100**). On METU-VisTIR it reaches AUC@5°
of 22.03 against LoFTR's 2.63 and SuperGlue's 3.90.

That 8.4× improvement over LoFTR is a real, large result **for visible↔thermal
terrestrial scenes**. `[EXTRAPOLATION]` Its transfer to IIRS thermal bands is
untested by anyone, and two things differ materially: lunar thermal imagery has
no atmosphere and no vegetation, and IIRS's thermal bands are far narrower than
a 8–14 µm thermal camera.

**Licence note:** the METU-VisTIR dataset is CC BY-NC-SA 4.0 — noncommercial.
Same class of constraint as SuperGlue's weights, which
`lunar_reg.match.superglue` already refuses to run without explicit
acknowledgement.

### 4.4 MINIMA, for the training data we do not have

`[PAPER — arXiv:2412.19412, CVPR 2025]` Generate the hard modality from RGB data
whose correspondences are already known, so labels come free. Infrared via
StyleBooth + LoRA (rank 256) fine-tuned on LLVIP and M3FD; depth via
DepthAnything V2; event, normal, sketch and paint via other engines. Source is
MegaDepth (40M pairs); output MD-syn spans 7 modalities. LoFTR, LightGlue and
RoMa were retrained on **4×RTX 3090** for 30/50/4 epochs. Zero-shot remote
sensing AUC@10px: MINIMA-RoMa 44.68, MINIMA-LG 38.40, MINIMA-LoFTR 35.18.

`[EXTRAPOLATION — and this is our main proposed contribution]` MINIMA
synthesises modalities with *generative* models, which hallucinate. For
IIRS we can do better, because the forward model is **physics, not style**:
degrade a TMC-2 frame by IIRS's PSF and 16× sampling, apply a spectral
transform, add IIRS noise. A learned style transfer is guessing at a mapping we
can write down.

`[MEASURED — src/lunar_reg/ingest/pseudo_gt.py]` And unlike MINIMA we have a
second, independent supervision route: real co-located IIRS and TMC-2 products
exist wherever footprints overlap, and both carry georeferencing, so approximate
correspondences come free from metadata. `find_cross_sensor_pairs` finds those
overlaps and `build_pseudo_gt` emits the correspondences.

**With the confidence stated honestly**: `estimate_confidence` returns `None`
for the total, because absolute pointing accuracy, the corner-homography model
error and the corner ordering are all unestablished. The floor from quantisation
alone is 23.09 m. So this is a *pre-training / initialisation* signal, never an
evaluation reference. `validate_against_transform` is the route to a real
number, and `recommended_validation_plan()` names the same-modality pairs to
measure it on.

### 4.5 MapGlue, as a zero-shot baseline only

`[PAPER — arXiv:2503.16185]` MapData: 121,781 aligned 512×512 pairs from 233
global sampling points; semantic context plus a dual graph-guided mechanism;
generalises to unseen modalities without retraining.

`[EXTRAPOLATION]` Its trained modality gap is electronic-map↔visible, which is
a *semantic* gap — road networks and labels against photographs. Ours is
radiometric. Worth running zero-shot because it costs one inference pass, but
there is no published reason to expect it to transfer.

## 5. Training plan on one RTX 4060

`[MEASURED — src/lunar_reg/match/benchmark.py, this repository]` LoFTR-family
inference in fp32 breaks between 1024 and 1152 px under an 8 GB cap, with peak
activations following `3203 B/px × S² + 4 × (S/8)⁴`. Training adds optimizer
state and the backward graph, roughly 3–4× inference.

`[EXTRAPOLATION]` So a realistic training tile is ~512 px at batch 1–2 with
gradient checkpointing and autocast. XoFTR's own fine-tune used 8×A100 for 24 h.
On one 4060 the equivalent is on the order of weeks. **Reproducing their
fine-tune is not on the table**, and any plan that assumes it is should be
rejected.

What *is* feasible, in ascending cost:

1. **Zero-shot, no training.** Physical band reduction + metadata-driven scale
   bridging + LightGlue (Apache-2.0). Hours of work. **Recommended for the
   30 Sept deliverable.**
2. **Crater detector only.** A YOLO-class detector on a public lunar crater
   catalogue trains in hours on a 4060 and unlocks the CNSF path. Small, bounded
   risk.
3. **Adapter tuning.** Freeze the pretrained backbone and coarse attention;
   train only a 1×1 "spectral stem" mapping our reduced IIRS channel into the
   statistics the backbone expects, plus the fine decoder and sub-pixel head.
   Hours to a day. This is the highest-value learned option per GPU-hour.
4. **Full fine-tune.** Not feasible on this hardware. Listed so nobody plans it.

## 6. What is genuinely unsolved

1. **Nobody has published IIRS↔OHRC matching.** Makharia et al. matched IIRS to
   WAC at 1.25×, not to a high-resolution camera. The 320× case is open — and
   §2 argues it is open because it is the wrong problem, not because it is hard.
2. **SNR in the 800–850 nm overlap window at 80 m/px is unmeasured.** If it is
   poor, arm A1 collapses to A2 and the modality gap widens.
3. **The thermal crossover (~2500–3000 nm)** is genuinely hard: reflected and
   emitted contributions are comparable and their ratio depends on local
   temperature, so appearance is not a stable function of geometry. No cited
   work covers this.
4. **No ground truth exists,** and our substitute has an unestablished dominant
   error term. Everything downstream rests on metadata geometry being good
   enough to bootstrap, and the geometry fields in `ingest/fieldmap.py` are still
   UNVERIFIED against a real label.
5. **The accuracy target for IIRS is unstated.** The problem statement asks for
   sub-pixel accuracy without saying in whose pixels. At IIRS's own 80 m pixel
   that may be achievable; at OHRC's 0.25 m pixel it is not, for the reasons in
   §2.

## 7. Recommended path for 30 September

Ship the training-free chain: physical band reduction (A1, falling back to A2),
IIRS→WAC at native scale, classical matchers with the local-contrast ECC
prefilter, and both the RMSE and conditioning metrics reported. Add the crater
detector if time allows. Present CNSF, XoFTR and the physical data engine as the
prototype roadmap, clearly labelled as untested — which is both honest and, for
a judging panel, a stronger position than an unsupported claim.
