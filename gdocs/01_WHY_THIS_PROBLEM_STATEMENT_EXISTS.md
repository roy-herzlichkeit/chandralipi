# 01 · Why this problem statement exists

*Audience: a teammate with a computer-science background, no exposure to remote
sensing, geodesy, or planetary data. Every term is defined the first time it is
used. If a sentence needs background you do not have, that is a defect in this
doc, not in you.*

**New words in this doc**

| word | plain meaning |
|---|---|
| **ISRO** | Indian Space Research Organisation. The agency that flew Chandrayaan-2 and wrote the problem statement we are answering. |
| **Chandrayaan-2** | India's second lunar mission (2019). The lander crashed; the **orbiter** is healthy and still returning data. Our inputs come from the orbiter's cameras. |
| **payload / instrument** | A sensor bolted onto the spacecraft. Chandrayaan-2's orbiter carries several; three are cameras we care about (OHRC, TMC-2, IIRS). |
| **optical image** | An image formed from light (reflected sunlight or emitted heat), as opposed to radar. All three of our cameras are optical. |
| **image registration** | Given two pictures of the same physical place, find the geometric transform that lays one exactly on top of the other. This is the entire problem. |
| **reference image** | The image you trust and align *to*. Also called the *fixed* image. For us this is usually imagery from NASA's LRO satellite. |
| **source image** | The image you move and warp to fit the reference. Also called the *moving* image. For us this is the Chandrayaan-2 image. |
| **correspondence / match point** | A pair of pixel coordinates, one in each image, that point at the same physical spot on the Moon. Registration is estimated from a set of these. |
| **sub-pixel accuracy** | Accurate to *less than the width of one pixel*. If a pixel is 25 cm of ground, sub-pixel means the alignment error is under 25 cm. |
| **uniform distribution** | The match points are spread evenly across the whole frame, not bunched in one corner. The problem statement demands this explicitly, and section 3 explains why. |
| **GSD (Ground Sample Distance)** | How much ground one pixel covers. "0.25 m/GSD" means one pixel is a 25 cm square patch of Moon. |
| **modality** | A particular way of sensing the scene. A black-and-white photo, a colour photo, a heat image, and a radar image are four modalities of the same place. |
| **DEM (Digital Elevation Model)** | A raster where each pixel stores a height instead of a brightness. A height-map, in game-engine terms. |
| **mosaic** | One large map image stitched together from many smaller overlapping image strips. |
| **terminator** | The line on a planet between the sunlit side and the dark side. |

The problem statement is **SIH26166**, posed by ISRO for Smart India Hackathon
2026. Its core sentence:

> Generic software solution for finding correspondence between Chandrayaan-2
> acquired optical images and Lunar reference images with a **sub-pixel accuracy**
> of source image **maintaining uniform distribution** across the images.

This document explains *why ISRO would ask for that* — what is missing today, and
what becomes possible once it exists.

---

## 1. There is a large archive that cannot be used together yet

Chandrayaan-2's orbiter has been imaging the Moon since 2019. Three of its
cameras produce the optical images in this problem:

| camera | full name | GSD (ground per pixel) | what it is good for |
|---|---|---|---|
| **OHRC** | Orbiter High Resolution Camera | 0.25 m | the *shape* of the surface — boulders, crater walls, slopes |
| **TMC-2** | Terrain Mapping Camera 2 | 5 m | *height* — it shoots the same ground from three angles, which yields a DEM |
| **IIRS** | Imaging Infrared Spectrometer | ~80 m | *composition* — ~256 narrow colour bands that reveal which minerals (and water ice) are present |

Each of these produces thousands of image strips. Individually they are already
useful. The problem is that **you cannot currently overlay one on another with
confidence**, and you cannot reliably overlay any of them onto an external
reference map such as NASA's decade-old, laser-calibrated LRO imagery.

Why not? Because every image strip carries a small, unknown geometric error. The
spacecraft's recorded position and pointing are good but not perfect; the camera
model is an approximation; the Moon is a sphere being flattened onto a grid. Two
strips that *should* line up are off by tens or hundreds of metres — sometimes
more. Until that offset is measured and removed, per image, the archive is a pile
of individually-good pictures that do not form a coherent whole.

**Registration is the operation that measures and removes that offset.** It is
the missing first step. Everything in the next section depends on it and cannot
be done without it.

---

## 2. What registration unlocks

Registration is never the end goal. It is the enabling step for four things ISRO
actually wants to do with this data.

### 2.1 Change detection

Question: *did a new crater appear between 2020 and 2024? Did a boulder roll? Is
a slope creeping?*

You answer this by subtracting an older image from a newer one and looking at
what is left. But if the two images are misaligned by even one pixel, the
subtraction lights up every crater rim and every ridge — because a bright edge
shifted by one pixel looks exactly like a bright edge that changed. Misalignment
is indistinguishable from change.

To detect a real surface change you must first remove *all* the fake change, and
fake change is misalignment. This is why the requirement is **sub-pixel**: the
alignment error has to be smaller than the smallest real change you want to see.

### 2.2 Fusing instruments

OHRC tells you the surface is rough here. IIRS tells you there is pyroxene here.
TMC-2 tells you the slope is 12° here. These three facts are only useful
*together* if you know which OHRC pixels sit inside which IIRS pixel and on which
part of the TMC-2 slope.

One IIRS pixel (80 m) covers the same ground as roughly 100,000 OHRC pixels
(0.25 m) — 320 × 320. Lining them up so that "this mineral signature belongs to
*that* crater floor" is a registration problem, and a hard one because the images
look nothing alike (section 3).

### 2.3 Landing-site selection and navigation

Choosing where a future lander touches down means checking a candidate site
against every image ever taken of it, at every sun angle, to be sure there is no
unseen boulder or slope. Those images must be co-registered or the checks
contradict each other.

**Terrain-relative navigation** goes further: a descending spacecraft points a
camera at the ground and matches the live frame against a stored map, in real
time, to know where it is. That is registration under a stopwatch. A generic,
automatic, tested registration pipeline is exactly the component such a system is
built around.

### 2.4 Cartography

A single OHRC strip is about 3 km wide and 25 km long — a thin ribbon. A usable
map of a region is a **mosaic** of hundreds of ribbons. Every ribbon has to be
aligned to its neighbours to sub-pixel precision or the seams show and the map
lies about distances. Building the mosaic *is* running registration hundreds of
times.

---

## 3. Why the Moon makes this genuinely hard

If registration were easy, ISRO would have an in-house script and no problem
statement. Three things make lunar optical images uniquely difficult to match,
and the problem statement names all three.

### 3.1 Illumination changes invert the picture

The Moon has no atmosphere. No atmosphere means no scattered light, which means
shadows are **hard-edged and pure black**, not the soft grey shadows you see on
Earth.

Now consider a crater rim — a circular ridge. At any given sun position, exactly
one side of the rim is lit and the opposite side is in black shadow. Move the sun
to the other side of the sky (a different orbit, a different date) and **the lit
side and the shadowed side swap**. The same crater now looks like a
brightness-inverted version of itself.

Classical matching algorithms describe a patch of image by its pattern of
light-to-dark gradients — which is precisely what just flipped. In our own
measurements on test scenes with a known answer, one classical matcher (SIFT)
found 228 correct match points when the sun moved 15°, **4** when it moved 30°,
and **0** when it moved 60°. That is a cliff, not a slope. Section 3.1 of doc 04
covers what we do about it.

The formal name for this effect is **nonlinear radiation distortion**: the
relationship between the two images' brightness values is not a straight line you
can fix with a contrast slider. In places it genuinely reverses.

### 3.2 Scale differences are enormous

The pixel-size ratios between the instruments:

| pair | ratio of ground-per-pixel |
|---|---|
| OHRC ↔ LRO reference | 2× |
| TMC-2 ↔ OHRC | 20× |
| IIRS ↔ TMC-2 | 16× |
| **IIRS ↔ OHRC** | **320×** |

No feature-matching algorithm bridges a 320× scale gap — a landform that is a
detailed crater with a visible rim in one image is three grey pixels in the
other. There is nothing in common to match. The software has to be smart about
*choosing a reference at a comparable scale* rather than hoping a matcher copes.

### 3.3 Viewpoint and sensor geometry

The two images come from different orbits and different look angles, over a
curved body. And the cameras are **pushbroom** sensors: instead of capturing a
whole rectangular frame in one instant like a phone camera, they capture one
thin line of pixels at a time and build the image up as the spacecraft flies
forward — like a desktop scanner where the paper is the Moon and the scan head is
in orbit. This means the image has no single viewpoint, so no single simple
perspective transform describes it. Assuming one introduces error (we measured
639 m of it in one case; see doc 04).

### 3.4 Multi-modal matching

For IIRS specifically, the two images are not just differently scaled — they are
formed by different physics. IIRS's longer wavelength bands measure *emitted
heat*, not reflected sunlight. A picture of how hot the ground is and a picture
of how bright it is are not the same picture: some features invert, some vanish.
Matching across that gap is close to an open research problem.

---

## 4. Why a *generic* solution, and why a hackathon

The problem statement says **"generic software solution"**, and both words are
deliberate.

- **Generic**, not a one-off. ISRO could pay an analyst to hand-align two
  specific images in a GIS tool over an afternoon. That does not scale to an
  archive of thousands of strips across three instruments and years of sun
  angles. They want *one configurable pipeline* that takes any Chandrayaan-2
  optical product and any lunar reference and returns a registered product plus
  its match points plus honest quality metrics — automatically.

- **Software**, delivered with the method. The deliverable is not a paper
  claiming an accuracy number. It is running code, a registered example product,
  the match points, and the evaluation metrics, so ISRO can rerun it on their own
  data.

- **A hackathon**, because the ingredients now exist outside ISRO. Public
  reference imagery (LRO), open-source classical matchers (in OpenCV), and
  pretrained neural matchers (LoFTR, LightGlue) can all be assembled by a small
  team in weeks. Ten years ago the neural half did not exist. The problem is
  ripe: hard enough to be worth posing, tractable enough to prototype quickly.

---

## 5. The one-paragraph answer

ISRO has a growing archive of Chandrayaan-2 optical imagery — surface shape from
OHRC, elevation from TMC-2, composition from IIRS — that cannot yet be overlaid
on each other or on external reference maps, because every image strip carries a
small unknown geometric offset. Removing that offset (registration) is the
prerequisite for change detection, instrument fusion, landing-site analysis,
navigation, and mapping. Doing it on the Moon is hard because sun-angle changes
invert lunar features, instrument scales differ by up to 320×, and pushbroom
sensor geometry defeats simple perspective models. ISRO wants one generic,
automatic, tested pipeline that does it and reports honestly how well it did.
That is what SIH26166 asks for, and it is what this project builds.
