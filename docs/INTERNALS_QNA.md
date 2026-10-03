# Internals Q&A — anticipated attacks and direct answers

Written for a panel that will look for a weak point to pull on, not for one
asking in good faith. The tone throughout is **calm and factual, never
defensive, never apologetic.** Own every real limitation in one sentence and
move on — hedging or over-explaining is what invites a second attack. Every
number here matches `docs/INTERNALS_SCRIPT.md` and traces to
`docs/project/CONTEXT_HANDOFF.md` / `udocs/50_findings.md` / `data/processed/demo_real/README.md`.

**One rule that applies to every answer below: if you don't know something,
say "I don't know, I'll check" — not a guess.** A wrong confident answer is
what actually damages credibility in front of a panel; "I don't know" from
someone who clearly knows the rest of the project costs nothing.

---

## 1. Data legitimacy — the questions they'll open with

**"This isn't Chandrayaan-2 data. Why are you showing us someone else's mission?"**
Because our archive access — ISRO's download portal — was unreachable over
our network for two nights running, and we chose to demonstrate a working
pipeline over an unreadable slide. Every result on screen says which agency
it's from. We're not claiming this is Chandrayaan-2 data; we're claiming the
same code runs correctly on real orbital imagery from two different agencies.

**"So you admit this is fake."**
No — real is real regardless of whose satellite took it. "Fake" would be
generated imagery or invented numbers. This is the Japan Aerospace
Exploration Agency's Kaguya orbiter and NASA's Lunar Reconnaissance Orbiter,
both real spacecraft, both real downloads, both labelled correctly on the
dashboard. Ask to see the sensor name on any row — it says JAXA or NASA, not
Chandrayaan-2.

**"Why should NASA and JAXA data convince us about an ISRO problem?"**
Because the problem is a general computer-vision problem — illumination
change, scale change, sensor geometry — stated using Chandrayaan-2's
instruments. The pipeline doesn't know or care which agency took the image;
it's the identical illumination-invariance and scale-bridging problem either
way. What it does *not* prove is anything about Chandrayaan-2's specific
label format or archive quirks — we're not claiming that, and say so.

**"Do you actually have any real Chandrayaan-2 data?"**
Five real products, yes. We verified 22 of 25 label fields against them,
found and fixed a bug that was silently rejecting every real Orbiter High
Resolution Camera strip, and measured a 639-metre error in a transform using
one of them. What we don't have is two real Chandrayaan-2 products that
overlap each other on the ground — the ones we hold sit at three unrelated
locations. That's a download-targeting problem, not a pipeline problem.

**"Why didn't you just download the right data, then?"**
We tried. The portal requires login and its bulk-download tool has no
location filter — it returns whatever's in the date range, which is why we
ended up with three unrelated locations in the first place. The fix is a
different, map-based search tool on the same portal, and it needs the
portal to actually be reachable, which it wasn't this week.

---

## 2. Methodology and rigor — where they'll try to find sloppiness

**"Your uniformity metric — you validated it on six examples. That's not science."**
Correct, and we say so ourselves — six synthetic layouts, Spearman rank
correlation of −0.83 against true worst-case error. That is suggestive, not
proof, and we don't oversell it as more. What is not in question is the
underlying finding it's built on: Root Mean Square Error stayed within 4% of
constant across those six layouts while true error varied by 51 times.
That finding doesn't depend on the six-example validation being strong.

**"Why an affine transform / homography and not something more flexible?"**
Because more degrees of freedom fit noise as well as signal. A pushbroom
sensor doesn't have a single viewpoint, so a full projective transform
invents distortion that isn't physically there — we measured that
invention at 639 metres on real data. The right transform is the least
flexible one the physics justifies, not the most powerful one available.

**"Your RANSAC threshold looks arbitrary. Did you tune it to get a good number?"**
It's set from expected point-position noise, in pixels, before any run — not
adjusted afterward to flatter a result. If asked for the exact value used in
a specific run, give it and say where it's set (`PipelineConfig`), don't
guess.

**"How many iterations does RANSAC actually need, and why?"**
There's a closed-form answer: N equals log(1 minus the confidence you want)
over log(1 minus (1 minus the outlier fraction) to the power of the sample
size). At 50% outliers with a 4-point sample it's about 72 iterations; at
80% outliers it's about 4,700. That's exactly why a matcher returning fewer,
cleaner correspondences beats one returning many dirty ones.

**"Isn't Enhanced Correlation Coefficient refinement just curve-fitting until it looks right?"**
No — it maximises the correlation between actual pixel brightness values
under linear brightness changes, which is a real, interpretable
optimisation, not a fudge. And we'll volunteer the honest limitation before
you find it: our automatic prefilter-selection heuristic for it is
defective — it confuses sensor noise with genuine illumination change — so
we shipped it disabled rather than tune the threshold until a test passed.
That's a documented, known defect, not a hidden one.

---

## 3. Depth checks — they may just quiz definitions to see if you understand your own project

**"What is a homography, in one sentence?"**
A transform with eight numbers that maps one flat plane's image to another
under perspective — the effect that makes railway tracks converge in a
photo.

**"What's a pushbroom sensor and why does it matter here?"**
A sensor with one line of detectors that reads out repeatedly while the
spacecraft moves, so every row of the final image was taken from a
different position — meaning there's no single viewpoint to fit a
perspective transform from.

**"What actually makes a transformer, like the ones in LightGlue or the Local Feature TRansformer, different from a convolutional network?"**
A convolutional network looks at fixed local neighbourhoods. A transformer's
attention lets every element look at every other element and decide which
ones matter — here, letting a patch in one image directly compare itself
against every patch in the other image, rather than only nearby ones.

**"Why does illumination change break feature matching specifically?"**
Because descriptors like the Scale-Invariant Feature Transform are built
from brightness gradients — which direction brightness increases. Move the
sun and a crater's lit wall becomes its dark wall: the gradient direction
inverts at exactly the structure the descriptor was keying on.

**"What's the actual difference between your two learned matchers?"**
LightGlue is sparse — it finds keypoints first, then decides which pairs of
keypoints correspond. The Local Feature TRansformer is dense and
detector-free — it compares every location to every other location directly,
which costs far more memory but works on smooth terrain where there's no
distinct keypoint to find at all.

---

## 4. Results and honesty — don't let a strong number get read as the whole story

**"719 inliers sounds impressive, but what's the outlier rate — is that actually good?"**
741 raw matches, 719 kept as inliers — 97% inlier ratio. That's high for a
cross-instrument, ~17-times scale-different pair; the classical detectors on
the same pair returned 16–29 matches total. It's also the only result in the
entire project, real or synthetic, that passes our own uniformity gate — so
it's not just a big number, it's a well-distributed one.

**"How do you know 0.33 pixels isn't just overfitting to that one pair?"**
It's a real-data result on one pair, stated as exactly that — one pair, not
a general claim. We're not claiming 0.33 pixels as our project's headline
accuracy figure; it's evidence the pipeline can reach sub-pixel precision
under favourable conditions, which is what the problem statement asks for.

**"Most of your matchers fail your own uniformity gate. Isn't that a failure?"**
It's the finding, not a failure of the project. The gate exists specifically
to catch exactly this — that a good residual error number can still come
from correspondences clustered in one part of the image. Four of five real
cross-instrument results failing it, and us reporting that plainly, is the
uniformity metric doing its job.

**"Did you cherry-pick your best result and hide the failures?"**
No — ask to see the negative one. We deliberately searched for a
better-looking second location, matched it, and it failed badly — 53 to 72
pixel error despite a matcher reporting a deceptively perfect-looking
"100% inlier ratio." We caught that by looking at the actual image, not by
trusting the number, and we kept the record of it rather than deleting it.
That failure is written up in the same document as the successes.

---

## 5. Scope and ownership — the ones aimed at the person, not the project

**"Did you write this code, or did an AI write it for you?"**
Built with AI-assisted tooling, the same way most serious software is
written in 2026 — and every design decision, every number, and every
limitation just discussed came from decisions made and verified during that
build, not accepted blind. If a specific line of reasoning is challenged,
explain it directly rather than deflecting to "the tool did it."

**"This looks like it's just SIFT and LightGlue wrapped in a demo. What did you actually build?"**
The matchers are existing, cited algorithms, used as building blocks — that's
correct and stated openly. What's built on top: the pipeline that classifies
every outcome rather than silently dropping failures, the geodesy and
footprint-overlap code specific to a lunar sphere and polar imagery, the
uniformity and bootstrap-conditioning metrics that don't exist in the cited
matchers or in the problem statement's suggested metrics, and the 639-metre
pushbroom-geometry finding. None of that came from a library.

**"Why hasn't ISRO already solved this if it's so straightforward?"**
It isn't straightforward — that's the entire first half of this talk. The
problem statement's own suggested metric, Root Mean Square Error, doesn't
actually verify the requirement it's meant to verify; we measured a 51-times
gap between what it reports and true error. If it were solved, it wouldn't
be a hackathon problem.

**"What's actually left before this is a finished product?"**
Two concrete things, no more: a targeted re-download so we hold two
Chandrayaan-2 products that overlap the same ground, and wiring in a
per-pixel geometry file we've already validated in place of a transform we
measured to be off by 639 metres. Both scoped, neither started because they
weren't the priority this week.

---

## If a question is genuinely just hostile, not substantive

Answer the technical content in one sentence, then stop talking. Do not fill
silence, do not apologise, do not ask "does that answer your question" —
that invites a follow-up dig. A flat, correct, short answer followed by
silence reads as confidence; a long one reads as anxiety, which is exactly
what this kind of question is fishing for.
