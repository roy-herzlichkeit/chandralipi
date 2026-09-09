# 5-minute internals script

Written to be **spoken**, not read off a slide. Direct, front-loaded evidence,
no hedging language. Every acronym is spelled out in full the first time it's
said, then shortened after — so nobody in the room has to guess what a letter
stands for. Every number here traces to a file — if challenged on any of
them, the answer is "here's the run" (`CONTEXT_HANDOFF.md`,
`udocs/50_findings.md`, `data/processed/demo_real/README.md`), not "trust me."

Target: ~700 words, ~4:45 spoken at a confident, unhurried pace. Practice it
once against a timer before the room.

---

**[0:00] What we built**

"Team Severed Department, problem SIH26166 — that's the Smart India
Hackathon, problem number 26166, set by the Indian Space Research
Organisation, ISRO. Their orbiter Chandrayaan-2 carries three optical
instruments — the Orbiter High Resolution Camera, OHRC; the Terrain Mapping
Camera 2, TMC-2; and the Imaging Infrared Spectrometer, IIRS — imaging the
Moon at wildly different resolutions and conditions. The ask: find
pixel-accurate correspondences between them and a reference image,
automatically, to sub-pixel accuracy, spread evenly across the frame. Not a
paper. A working pipeline, tested, and I'll show you real output in a
minute."

**[0:30] Why it's actually hard — three things, each measured, not assumed**

"One. Illumination. No atmosphere, so shadows are hard black. Move the sun,
and a crater's lit wall becomes its dark wall. We measured this using the
Scale-Invariant Feature Transform, SIFT — a standard matching algorithm: 228
correct matches at 15 degrees of sun-angle difference, 4 at 30, zero at 60.
Not gradual decay — a cliff.

Two. Scale. IIRS is 320 times coarser than OHRC. Nothing is scale-invariant
across eight octaves, so we bridge it in stages, never directly.

Three. Geometry. These are pushbroom sensors — no single camera position,
ever. Fit the obvious four-corner transform anyway, and we measured a
639-metre error against ISRO's own per-pixel geometry file. Two-thirds of a
kilometre, on a sub-pixel requirement."

**[1:20] What we built to solve it**

"Classical detectors — SIFT, and Accelerated-KAZE, AKAZE — as baselines,
because the collapse above is the argument for going further. Modern
matchers — LightGlue, and the Local Feature TRansformer, LoFTR — these are
transformers, the same attention mechanism as a language model, run over
image patches instead of words. We fit the transform with Random Sample
Consensus, RANSAC, then refine it to sub-pixel with the Enhanced Correlation
Coefficient, ECC.

And one thing nobody asked for, but the problem statement needs: ISRO
suggests Root Mean Square Error, RMSE, as the metric. We proved RMSE cannot
certify 'sub-pixel across the image.' Six point layouts, identical noise —
RMSE barely moves, 0.7 pixels across all six. True error away from those
points: a 51-times range, up to six pixels. So we built a uniformity metric
and a bootstrap conditioning map that shows exactly *where* a transform can
be trusted, not just one number that hides the answer."

**[2:25] The direct question — is any of this real data?**

"Yes, and I'll say exactly which parts, because I'd rather you hear it from
me than find it yourselves.

Chandrayaan-2: we have five real products. Verified 22 of 25 label fields
against them, found and fixed a bug rejecting every real OHRC strip, found
the 639-metre error — on real data. But the specific files we hold sit at
three different, non-overlapping locations on the Moon. Zero real
cross-instrument Chandrayaan-2 pairs yet. That's a data-acquisition gap —
ISRO's download portal was unreachable over our network the last two nights
— not a pipeline gap.

So we validated the *same* pipeline, same matchers, same metrics, end to
end, on two other real public datasets: the Japan Aerospace Exploration
Agency's, JAXA's, Kaguya orbiter, and the American National Aeronautics and
Space Administration's, NASA's, Lunar Reconnaissance Orbiter, LRO.
[**show dashboard here**] Real imagery, two agencies, genuine overlap.
Result: LightGlue, 719 inliers out of 741 matches, 97 percent inlier ratio —
the only result anywhere in this project, real or synthetic, that passes our
own uniformity gate. Same-sensor pair: 0.33 pixel median error. Sub-pixel. On
real data."

**[3:55] What's left, scoped, not hidden**

"Two things. One: Chandrayaan-2 OHRC and TMC-2 at the same location — a
targeted download, not a code fix. Two: wire in the per-pixel geometry grid
we already validated, replacing the transform that's off by 639 metres —
ready, held back deliberately because it changes every crop the pipeline
produces."

**[4:30] Close**

"Every number I gave you traces to a file and a run. Nothing here is a guess
dressed up as a result. The pipeline works — we proved it end to end on real
cross-agency imagery — and the only thing between this and Chandrayaan-2
specifically is one download. Questions."

---

## If they push back — short, prepared answers

By this point in the talk every acronym below has already been said in full
once, so these can stay short.

- **"Why not just use ISRO data?"** — We have five real ISRO products and
  used them for verification (label fields, the 639 m finding). The ones we
  hold don't overlap each other geographically — that's what's missing, not
  the code. Say it once, don't over-explain.
- **"So this is fake / not Chandrayaan-2?"** — Say plainly: correct, this
  specific result is JAXA and NASA data, labelled honestly as such on the
  dashboard. It proves the pipeline; it does not claim to be OHRC data.
  Do not let this get reframed as "faking a result" — the sensor names are
  right there on screen.
- **"What's actually novel here?"** — The uniformity and conditioning
  metrics, and the 639 m pushbroom finding. Lead with those if asked for
  "the contribution."
- **"How do you know your metric is any good?"** — Spearman rank
  correlation of −0.83 between the uniformity score and true worst-case
  error, on six synthetic layouts. Say the sample size is small if
  pressed — don't oversell it.
