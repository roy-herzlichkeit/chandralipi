# 5-minute pitch script (spoken, casual)

Written to be **said out loud**, not read off a slide — so it's loose, it has
contractions, it sounds like a person talking. It follows the six-slide idea
deck in order: title, problem/solution, technical approach, feasibility,
impact, references.

What does **not** loosen up: every number in here traces to a file and a real
run. If someone challenges a figure, the answer is "here's the run"
(`CONTEXT_HANDOFF.md`, `udocs/50_findings.md`,
`data/processed/demo_real/README.md`) — never "trust me." Acronyms still get
said in full the first time, just naturally, not as a drill.

Target: ~850 words, ~5:15 spoken at an unhurried pace. Run it once against a
timer before the room.

---

**[0:00] Slides 1–2 — who we are, what we're doing**

"We're Severed Department, from IIIT Bhubaneswar, and we took problem 26166 —
Smart India Hackathon problem number 26166, set by ISRO, the Indian Space
Research Organisation.

Here's the setup. Chandrayaan-2, ISRO's lunar orbiter, carries three optical
instruments — OHRC, the Orbiter High Resolution Camera; TMC-2, the Terrain
Mapping Camera 2; and IIRS, the Imaging Infrared Spectrometer. They shoot the
Moon at wildly different resolutions, at different times of lunar day, from a
moving platform. ISRO wants those images lined up against each other and
against a reference map — automatically, down to sub-pixel accuracy, with the
matched points spread evenly across the frame instead of bunched in one
corner.

We didn't write a paper about it. We built the pipeline, ran it, and I'll show
you real output before I'm done."

**[0:40] Slide 2 — why this is genuinely hard, and we measured all three**

"Three things break normal image matching here, and we didn't assume any of
them — we measured them.

One, illumination. The Moon has no atmosphere, so shadows are dead black, and
when the sun moves, a crater wall that was lit goes dark. We ran SIFT — the
Scale-Invariant Feature Transform, the standard matcher — across a sweep of
sun angles. 228 good matches at 15 degrees of difference. Four at 30. Zero at
60. That's not a gentle decline, that's a cliff.

Two, scale. IIRS is 320 times coarser than OHRC. Nothing stays matchable
across a gap that big, so we never match them directly — we bridge it in
steps.

Three, geometry. These are pushbroom sensors — no single camera position, the
image is built line by line as the orbiter flies. Fit the obvious flat
four-corner transform anyway and you're off by 639 metres against ISRO's own
per-pixel geometry file. Two-thirds of a kilometre, on a problem that asks for
sub-pixel."

**[1:35] Slide 3 — the pipeline**

"So the pipeline is five stages, each with one job.

Ingestion reads the PDS4 labels from OHRC, TMC-2 and IIRS, with an LRO and
SELENE fetcher as backup, and pulls out ground scale and sun angle.

Preprocessing resamples everything to a common ground scale, collapses IIRS's
spectral bands down to one grayscale image, and tiles the big OHRC frames so
they fit in 6 to 8 gigs of VRAM.

The matching engine is the swappable part — two tracks. A classical track,
phase-congruency and RIFT-style, and a deep-learning track: LoFTR and
LightGlue. Those two are transformers — same attention mechanism as a language
model, run over image patches instead of words. LightGlue is the fast
successor to SuperGlue, which is what's named on the slide. A selector picks or
combines the tracks.

Then geometric verification — RANSAC to throw out the bad matches, then
sub-pixel refinement with ECC, the Enhanced Correlation Coefficient. And an
output stage that writes the registered image, the match points, and the
metrics.

Stack's all open: Python, PyTorch, OpenCV, NumPy, GDAL, CUDA when there's a
GPU."

**[2:35] Slides 3–4 — the metric nobody asked for, and feasibility**

"One thing we added that wasn't in the ask. ISRO suggests RMSE — root mean
square error — as the accuracy metric. We don't think RMSE can certify
'sub-pixel across the whole image,' and we showed it: six different point
layouts, same noise, RMSE barely moves — 0.7 pixels across all six. But the
true error away from those points ranges 51 to 1, up to six pixels. So we
built a uniformity score and a bootstrap conditioning map that tells you
*where* the transform is trustworthy, instead of one number that hides it. It
rank-correlates minus 0.83 with true worst-case error — small sample, but it
fires.

On feasibility: it's zero-shot. No training, no GPU cluster. Everything I'm
about to show you actually ran on a CPU. Public LRO data means you're not
blocked waiting on archive access. The known risks — OHRC's giant tiles, IIRS
being hyperspectral — we handle with tiling and band selection, and the
classical track stays in as a fallback when the deep matchers choke on
shadow."

**[3:25] The honest bit — is any of this real data?**

"Straight answer, because I'd rather you hear it from me. Yes, with one
specific gap.

Chandrayaan-2: we have five real products. We verified 22 of 25 label fields
against them, found and fixed a bug that was rejecting every real OHRC strip,
and found that 639-metre error — all on real ISRO data. But the five files we
got sit at three spots on the Moon that don't overlap. So we have zero real
Chandrayaan-2 cross-instrument pairs. That's a download problem — ISRO's
portal was unreachable on our network two nights running — not a pipeline
problem.

So we ran the exact same pipeline — same matchers, same metrics, end to end —
on two other real, public datasets: JAXA's Kaguya orbiter and NASA's LRO.
[**show dashboard here**] Real imagery, two space agencies, genuine overlap.
LightGlue got 719 inliers out of 741, 97 percent — and it's the only result in
this whole project, real or synthetic, that passes our own uniformity gate.
Same-sensor pair, 0.33 pixel median error. Sub-pixel, on real data.

And we kept a failure: a second location that looked better and matched
terribly — big symmetric crater, every point on the rim looks the same, the
matchers locked onto the wrong crater. We caught it by looking at the image,
not the metrics table. It's in the writeup on purpose.

The closest published work on this exact dataset is Makharia et al., 2025. We
read it, we can reproduce their table — but we won't put our numbers next to
theirs and call it a comparison, because they measure RMSE the way we just
argued against."

**[4:25] Slide 5 — why it matters**

"What this unlocks: it automates ground-control-point tagging, which is manual
work right now. It puts Chandrayaan-2, LRO and SELENE into one coordinate
frame. That feeds landing-site selection, elevation models, change detection.
And nothing about it is Moon-specific — the same pipeline points at Mars or
any other ISRO multi-sensor mission."

**[4:45] Close**

"Every number I gave you traces to a file and a run. Nothing's a guess dressed
up as a result. The pipeline works — we proved it end to end on real
cross-agency imagery — and the one thing between here and Chandrayaan-2
specifically is a download. Questions."

---

## If they push back — short, casual answers

By this point every acronym's been said in full once, so keep these tight.

- **"Why not just use ISRO data?"** — We've got five real ISRO products and we
  used them — that's where the label-field checks and the 639-metre finding
  came from. The ones we hold just don't overlap each other on the ground.
  That's what's missing, not the code. Say it once, don't over-explain.
- **"So this is fake / not Chandrayaan-2?"** — Plainly: correct, this specific
  result is JAXA and NASA data, and it says so on the dashboard. It proves the
  pipeline; it doesn't claim to be OHRC. Don't let it get reframed as "faking a
  result" — the real sensor names are right there on screen.
- **"What's actually novel?"** — The uniformity and conditioning metrics, and
  the 639-metre pushbroom finding. Lead with those.
- **"How do you know your metric's any good?"** — Spearman rank correlation of
  minus 0.83 between the uniformity score and true worst-case error, on six
  synthetic layouts. Say the sample's small if pressed — don't oversell it.
- **"Does it run on our hardware?"** — Zero-shot, no training. Everything so
  far ran on CPU; a 6–8 GB card is plenty for the deep track.
