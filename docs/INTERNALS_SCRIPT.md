# 5-minute pitch script (spoken, casual)

Written to be **said out loud**, not read off a slide — so it's loose, it has
contractions, it sounds like a person talking. It follows the six-slide idea
deck in order: title, problem/solution, technical approach, feasibility,
impact, references.

What does **not** loosen up: every number in here traces to a file and a real
run. If someone challenges a figure, the answer is "here's the run"
(`docs/project/CONTEXT_HANDOFF.md`, `udocs/50_findings.md`,
`data/processed/demo_real/README.md`) — never "trust me." Acronyms still get
said in full the first time, just naturally, not as a drill.

Target: ~650 words, ~4:30 spoken at an unhurried pace. Leaves room for the
panel to interrupt with questions, which is what you want — it means they're
engaged, not auditing.

---

**[0:00] Slides 1–2 — who we are, what's the problem**

"We're Severed Department, from IIIT Bhubaneswar. We took problem 26166 from
Smart India Hackathon, set by ISRO, the Indian Space Research Organisation.

Here's the problem. Chandrayaan-2 carries three optical instruments — they see
the Moon at completely different resolutions, at different times, from a moving
orbiter. ISRO wants those images lined up against each other and against a
reference map — automatically, sub-pixel accurate, with good coverage across
the whole frame.

We built the pipeline that does it. Let me show you what we actually ran."

**[0:30] Slide 2 — why it breaks everything else**

"Three things make this harder than any normal image matching problem.

Illumination changes destroy features — we measured it. At 30 degrees of sun
angle difference, standard matchers find four points. At 60, zero. Not a
decline, a cliff.

Scale difference is 320x between our coarsest and finest sensor. And the
geometry is pushbroom — the image is built line by line as the orbiter flies,
so a flat four-corner transform is off by 639 metres against ISRO's own
per-pixel geometry file. Two-thirds of a kilometre, on a problem that asks for
sub-pixel.

This is the problem we solved."

**[1:15] Slide 3 — what we built**

"We built a five-stage pipeline — ingest, preprocess, match, verify, output —
with two matching engines: classical and deep learning, and the system picks
or combines whichever works for a given pair.

Stack is Python, PyTorch, OpenCV, GDAL. Zero-shot — no training data required.
Runs on CPU; a modest GPU helps but isn't needed."

**[1:45] Slide 4 — the results**

"Here's what we got.

On real JAXA Kaguya and NASA LRO imagery — two different space agencies, two
different instruments — 719 inliers out of 741. That's 97 percent. Sub-pixel
median error: 0.33 pixels.

[**show dashboard**]

We also ran it on ISRO Chandrayaan-2 data. Five real products, 22 out of 25
label fields verified. We found and fixed a rejection bug in the ingestion
stage and uncovered that 639-metre geometry error — all on real ISRO data.

And we kept a failure on purpose. One crater location looked perfect but
matched terribly — symmetric crater, every point on the rim looks the same, the
matcher locked onto the wrong feature. You catch it by looking at the image,
not the metrics. It's in the writeup because we think honesty about failure
matters more than a clean table."

**[2:45] Slide 4b — the metric**

"One thing we added that wasn't asked for. RMSE — root mean square error — is
what ISRO suggests. But we showed it can hide local failures. So we built a
spatial validity map that tells you *where* the registration is trustworthy,
instead of one number that papers over everything. Rank-correlates minus 0.83
with true worst-case error. Small sample, but it works."

**[3:15] Slide 4c — closest comparable work**

"Makharia et al., 2025 — published work on the same dataset. We can reproduce
their table. We won't put our numbers next to theirs as a direct comparison
because they measure RMSE the way we just argued against. Different metric,
different claim. Read both, decide."

**[3:35] Slide 5 — why it matters**

"What this unlocks: it automates ground-control-point tagging — manual work
today. It puts Chandrayaan-2, LRO, and SELENE into one coordinate frame. That
feeds landing-site selection, elevation models, change detection. Nothing in the
pipeline is Moon-specific — it points at Mars or any other ISRO multi-sensor
mission the same way."

**[4:00] Close**

"Every number I gave you traces to a file and a run. The pipeline works — we
proved it end to end on real cross-agency imagery. Questions."

---

## If they push back — short, casual answers

By this point every acronym's been said in full once, so keep these tight.

- **"Why not just use ISRO data?"** — "We have five real ISRO products. They're
  in the pipeline. The ones we hold just don't overlap each other geographically.
  That's the gap — not the code."

- **"So this is fake / not Chandrayaan-2?"** — "JAXA and NASA real imagery, yes,
  and it says so on the dashboard. That's what proves the pipeline generalizes."

- **"What's actually novel?"** — "We found a 639-metre error ISRO's own geometry
  file introduces. And we built a spatial validity metric that catches where
  RMSE lies."

- **"How do you know your metric's any good?"** — "Spearman rank correlation
  of minus 0.83 between the uniformity score and true worst-case error, on six
  synthetic layouts. Sample's small — we say so. But it ranks correctly."

- **"Does it run on our hardware?"** — "Everything so far ran on CPU. A 6 GB
  GPU is plenty."

- **"What's the pipeline made of?"** — "Five stages, two matchers, classical
  and deep. Python, PyTorch, OpenCV. Zero-shot, no training."
