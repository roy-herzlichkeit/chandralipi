# 03 · Why we chose this project — the story we tell, and why it is true

*Audience: the team. This one is a narrative, not a spec — it is the version of
events you can say out loud to a judge, a mentor, or a new teammate. It is
written in the first person for whoever is presenting. Every claim in it is one
we can back up; where a number appears, it came from a real run. Terms are still
defined at first use.*

**"LARP"** here means the story we step into and perform — the framing, the
motivation, the arc. A good LARP is not a lie. It is the true story told with the
parts that matter pulled to the front.

---

## The short version

We chose SIH26166 because it is a problem where **the hard part is not building
the thing — it is knowing whether the thing works.** That is a problem our team
is unusually well-suited to, and it is a problem most teams attempting this will
get wrong. We are not betting that we can align two Moon pictures better than
anyone else. We are betting that we can be the team that *proves* its alignment
is good everywhere in the frame, and catches itself when it isn't.

---

## The longer version, as a story

### It started with a sentence that sounded simple

> "Find correspondence between Chandrayaan-2 optical images and lunar reference
> images with sub-pixel accuracy, maintaining uniform distribution across the
> images."

Read fast, that is "line up two photos of the Moon". There are libraries for
that. OpenCV — the standard open-source computer-vision toolkit — ships SIFT, a
1999 algorithm that finds matching points between two images. Point it at two
lunar images, fit a transform, done. An afternoon.

So we spent a day trying to break it instead of trusting it. We built a
**synthetic lunar scene generator** — code that renders a fake Moon surface with
craters, lit by a sun we place wherever we want, casting hard black shadows the
way an airless body does. The point of a synthetic scene is that *we know the
correct answer* — we chose the transform between the two views when we generated
them — so for once we can actually measure whether a matcher is telling the
truth.

We moved the sun 15 degrees and asked SIFT to match the before and after. It
found 228 correct point pairs. We moved it to 30 degrees: **4**. Sixty degrees:
**zero**. Not a gentle decline — a cliff. The reason is physical: a crater rim is
a ring, half lit and half in shadow, and when the sun swings around, the lit half
and the shadowed half *trade places*. The image effectively inverts. SIFT
describes a patch by its light-to-dark gradients, which is exactly what flipped.

That was the first moment we knew this problem was real. The "afternoon" solution
fails the moment the two images were taken at different times of the lunar day —
which is almost always.

### Then it got more interesting

We kept poking. We took a solution that scored a lovely sub-pixel **RMSE** — root
mean square error, the standard "how far off are we on average" number, and the
one the problem statement suggests reporting — and we checked its *actual* error
against the known truth, at points all across the frame, not just at the points
we fitted to.

We ran six versions of the same test, each with 400 match points and identical
noise, changing only *where the points sat* in the frame. The RMSE moved by 4%.
The true worst-case error moved by **51 times** — from a tenth of a pixel with an
even spread of points, to nearly six pixels when the points were bunched in one
blob. A solution can report "0.7 pixel RMSE, sub-pixel, done" while being six
pixels wrong on the far side of the same image.

That is when the problem statement's phrase **"maintaining uniform distribution"**
stopped looking like a nice-to-have and started looking like the whole game. ISRO
put that clause in *because they know RMSE alone can be gamed*. The teams that
treat it as a checkbox will miss the point. The metric you actually need is one
that tells you *where in the image you can trust the alignment and where you
cannot* — and we built one (bootstrap-based extrapolation uncertainty; doc 02
§4), and then stress-tested it until we could state its limits honestly.

### Why this is our project and not someone else's

Here is the honest self-assessment.

- **The build is tractable.** The pieces exist: public reference imagery from
  NASA's LRO satellite, classical matchers in OpenCV, and *pretrained* neural
  matchers — LoFTR, LightGlue — that we can run without training anything
  ourselves. A small team can assemble this in weeks. We are not blocked on
  inventing an algorithm.

- **The discipline is rare, and it is ours.** This project's rule is that every
  external data field and every parameter carries a tag in the code saying where
  it came from — measured, from a paper, or an unverified guess — and that no
  number appears in a report unless a run produced it. That sounds like overhead.
  It is the reason that when our first five real Chandrayaan-2 products arrived,
  we immediately found that a standard four-corner geometric model was **639
  metres wrong** on a real image strip, that a polar-latitude filter was silently
  throwing away 100% of the real high-resolution data, and that our footprint
  areas were inflated up to 4.2×. Every one of those was caught because the code
  was built to distrust itself.

- **The failure mode we are guarding against is the one that kills hackathon
  projects.** A results table full of plausible numbers that no run produced.
  We have `[INSERT RESULT]` placeholders sitting in our draft report right now,
  in every cell we have not actually computed on real lunar data, and we will
  defend that choice to a panel: an honest "here is what we have measured and
  here is the gap" is worth more than false confidence, because the gap is
  exactly where a sharp judge will push.

### What we are actually claiming

Not: "we register Moon images better than the state of the art."

Instead: "we built a generic, tested pipeline that runs classical and neural
matchers side by side, we measured precisely where and why the classical ones
break, we showed that the standard accuracy metric cannot substantiate the
requirement it is asked to substantiate, we built and validated a metric that
can, and we can tell you — with a map — which parts of any given registration to
trust."

That is a claim we can stand behind under questioning. That is why we chose it.

---

## The one-paragraph version for a 30-second pitch

We chose the lunar image registration problem because its difficulty is hidden in
plain sight: the phrase "sub-pixel accuracy maintaining uniform distribution"
looks like a spec detail, but it is actually the crux. We proved to ourselves,
with measurements on scenes where we know the right answer, that classical
matchers collapse under lunar sun-angle changes (228 correct matches at 15°, zero
at 60°) and that the standard RMSE metric can look perfect while the alignment is
six pixels wrong elsewhere in the frame. So we built a pipeline that runs
classical and modern neural matchers together, and — the real contribution — an
evaluation that reports where in the image the registration can be trusted, with
its limitations stated honestly. We chose this project because the winning move
is rigour, and rigour is what our team does.
