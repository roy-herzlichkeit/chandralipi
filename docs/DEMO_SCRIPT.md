# 2–3 minute demo video script

**Rule for this recording:** every number spoken is read off the screen from a
run that actually happened. Where a figure is not yet available it is written
`[INSERT RESULT]` and must be filled from a real run before recording — not
estimated.

**Note added 2026-09-09, script itself unchanged below.** This script and its
numbers are the synthetic Chandrayaan-2-shaped illumination benchmark from
2026-09-05 and are still accurate for what they claim. They predate a
separate, later addition: on 2026-09-08/09, with ISRO/PRADAN access blocked
by poor network conditions, the same pipeline was run end-to-end on real
JAXA (Kaguya) and NASA (LRO WAC) imagery instead — 9 real results, headlined
by a 719-inlier, 97%-ratio cross-instrument LightGlue match and a 0.33 px
sub-pixel same-sensor SIFT match. That story is not scripted here; see
`data/processed/demo_real/README.md` for the numbers and
`CONTEXT_HANDOFF.md` §7 for status. If recording after tonight, consider
whether the real-data result belongs in this video too, or as a separate
clip — a judgment call, not made here.

Commands used on screen:

```
python scripts/build_demo_results.py          # populates the browsable set
python scripts/demo.py --case hard-30deg --matcher asift
streamlit run dashboard/app.py
```

---

### 0:00–0:20 — The problem, stated once

> *[On screen: the side-by-side from `01_matches.png`, before lines are drawn.]*

"These are the same square kilometre of the Moon. The left image was taken with
the sun low and off to one side; the right one with the sun thirty degrees
round. Look at the crater rims — the wall that is lit on the left is the wall
that is dark on the right. The brightness has inverted.

That is Chandrayaan-2's registration problem in one picture. ISRO needs
correspondence between OHRC, TMC-2 and IIRS and a lunar reference, to sub-pixel
accuracy, spread evenly across the frame."

### 0:20–0:45 — What breaks

> *[On screen: terminal running `scripts/demo.py --case extreme-180deg`.]*

"Here is what standard feature matching does when the sun swings all the way
round. Zero correspondences. Not a bad answer — no answer.

We measured where that cliff is. SIFT survives about fifteen degrees of azimuth
change, gets four correct matches at thirty, and none at sixty. And it is
azimuth that matters, not how dark the scene is — the shadow fraction barely
predicts it."

### 0:45–1:20 — The pipeline, running

> *[On screen: `scripts/demo.py --case hard-30deg --matcher asift`, output
> scrolling; then the four figures.]*

"So this is our pipeline on the hard case — thirty degrees of azimuth
difference, which is past where plain SIFT gives up.

Ingest reads the PDS4 label, not the image file, and pulls the footprint.
Overlap detection intersects the footprints on the lunar sphere. Preprocessing
resamples both to a common ground scale. Then the matcher, RANSAC, and a
sub-pixel refinement stage.

Forty-nine inliers out of fifty-one. And here is the alignment check — the
checkerboard. Watch a crater rim cross a tile boundary. It continues. It does
not step. That is what sub-pixel registration looks like when it is real."

### 1:20–1:50 — The part we think is new

> *[On screen: the conditioning heatmap, `04_conditioning.png`.]*

"Now the part we would like you to look at hardest.

The standard metric is RMSE over the matched points. On this pair it reads 1.45
pixels. The true error, which we know because this scene has a known transform,
is 0.09 pixels. The standard metric is out by a factor of sixteen — because it
measures how tightly the correspondences agree with their own fit, not how
right that fit is.

So we added a second metric. We resample the correspondences, refit, and see how
far the answer moves. Cool means the matches pin the transform down there. Hot
means it is extrapolating. On this pair the centre is trustworthy and the edges
are not — and our tool says so, out loud, instead of reporting one number and
calling it done."

### 1:50–2:20 — The dashboard

> *[On screen: `streamlit run dashboard/app.py`, filtering and selecting.]*

"Every run is stored, so all of it is browsable. Twenty-six registered pairs
here, across three sensor pairings, three matchers and four illumination cases.

Filter by sensor, by matcher, by metric threshold. Pick a pair and you get the
correspondences, the metrics, the overlay, and the trust map.

And note the banner. These are generated scenes, not Chandrayaan-2 products —
we have not had archive access. The tool says that on screen rather than letting
you assume otherwise. Every pipeline stage below it is real; when the products
arrive, the input list changes and nothing else does."

### 2:20–2:45 — Honest close

> *[On screen: `docs/MAKHARIA_PARITY.md` scrolling, then back to the dashboard.]*

"One last thing. The closest published work on this exact dataset reports RMSE
using that first definition — the fit's residual on its own points. We read the
paper to check. We can reproduce their table, but we will not put our numbers
next to theirs and call it a comparison, because they are not the same
measurement.

That is the standard we have tried to hold throughout: measure it, or say you
haven't."

---

## Shot list

| # | Shot | Source |
|---|---|---|
| 1 | Side-by-side, no lines | `demo.py` → `01_matches.png`, crop |
| 2 | Terminal, extreme case failing | `demo.py --case extreme-180deg` |
| 3 | Terminal, hard case succeeding | `demo.py --case hard-30deg --matcher asift` |
| 4 | Match lines | `01_matches.png` |
| 5 | Checkerboard, slow zoom on a rim crossing a tile edge | `02_checkerboard.png` |
| 6 | Conditioning heatmap | `04_conditioning.png` |
| 7 | Dashboard: filter, select, overlay toggle | `streamlit run dashboard/app.py` |
| 8 | Parity doc | `docs/MAKHARIA_PARITY.md` |

## Numbers to re-read off screen before recording

All of these came from a real run on 2026-09-05 and should be re-confirmed if
anything changes:

- 49 inliers of 51 matches — `demo.py --case hard-30deg --matcher asift`
- self-residual RMSE 1.4500 px, true RMSE 0.0926 px, ratio 16× — same run
- SIFT azimuth cliff: 228 correct at 15°, 4 at 30°, 0 at 60° — azimuth sweep
- 26 of 36 pairs registered — `build_demo_results.py`
