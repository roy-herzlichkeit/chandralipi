# SIH26166 — Understanding the Problem Statement

## 1. The problem in one sentence

Given a Chandrayaan-2 optical image and another lunar image covering the same physical area, automatically find corresponding locations between them accurately enough that the Chandrayaan-2 image can be aligned to the reference image, despite differences in illumination, viewpoint, sensor modality, and scale—and ensure those correspondences are spread across the image rather than concentrated in one region.

The official problem statement defines registration, names the source/reference roles, lists illumination, viewpoint, and scale variation as the key difficulties, and explicitly asks for **sub-pixel correspondence with uniform distribution** plus a registered product, match points, and evaluation metrics.

---

# 2. Start with the title

The title is:

> **“Multi-modal, Sun angle and scale invariant image correspondence using Chandrayaan-2 optical images (OHRC, TMC and IIRS)”**

Every word matters.

## “Image correspondence”

This is the heart of the problem.

Suppose this point exists in image A:

```text
Image A
               crater
                 ↓
        ┌──────────────────┐
        │                  │
        │       ● P        │
        │                  │
        └──────────────────┘
```

And the same crater appears somewhere else in image B:

```text
Image B
        ┌──────────────────┐
        │                  │
        │                  │
        │   ● Q            │
        │                  │
        └──────────────────┘
```

Then:

\[
P \leftrightarrow Q
\]

is a **correspondence**.

In coordinates:

\[
(x_s,y_s)\leftrightarrow(x_r,y_r)
\]

where:

- \(s\) = source
- \(r\) = reference

For example:

\[
(812.4,\ 531.7)
\leftrightarrow
(1213.8,\ 904.2)
\]

means:

> “The physical lunar feature represented by pixel position `(812.4, 531.7)` in the Chandrayaan image corresponds to position `(1213.8, 904.2)` in the reference image.”

Notice the decimal coordinates.

That already takes us toward **sub-pixel correspondence**, which we'll come to later.

---

# 3. Correspondence is not exactly the same thing as registration

This distinction is important.

**Correspondence** asks:

> Which point in A is the same physical place as which point in B?

**Registration** asks:

> What geometric transformation maps A into B?

Correspondences are generally used to estimate the registration transform.

So conceptually:

```text
images
  ↓
find corresponding points
  ↓
estimate geometry
  ↓
transform source
  ↓
registered image
```

The official statement describes lunar registration as finding match points between source and reference images and then aligning the source with the reference.

---

# 4. “Multi-modal”

A **modality** is essentially a particular way of sensing or representing the scene.

The problem names:

- OHRC
- TMC-2
- IIRS

and reference imagery such as LRO NAC and SELENE.

These sensors can differ in things such as:

- spatial resolution,
- spectral response,
- imaging geometry,
- field of view,
- detector characteristics.

So you cannot assume:

> Same lunar feature → same pixel appearance.

Two sensors may be looking at the **same physical crater** while producing substantially different numerical images.

Therefore the system is not merely doing:

```text
find patches that have the same brightness
```

It needs something closer to:

```text
find evidence that these two regions represent
the same physical lunar structure
```

That is much harder.

---

# 5. “Sun angle invariant”

“Invariant” means:

> The result should remain reliable even when this thing changes.

Therefore:

### Sun-angle invariant

means approximately:

> The correspondence mechanism should still recognize the same lunar terrain even when the Sun's illumination direction/elevation changes.

The official statement identifies changes in Sun azimuth and elevation as a challenge because they affect surface lighting and make lunar features difficult to correlate.

There are two important angles here.

## Sun azimuth

Think of azimuth as:

> **Which compass-like direction is the sunlight coming from?**

For example:

```text
        North
          ↑
West ← Moon → East
          ↓
        South
```

Sunlight might come from the east in one observation and southwest in another.

A crater then casts its shadow in different directions.

## Sun elevation

Elevation means:

> How high the Sun is above the local horizon?

Low elevation:

```text
Sun →
      _____________
         /\________________
        hill     long shadow
```

High elevation:

```text
          Sun
           ↓
      _____________
         /\
        /  \ short shadow
```

Therefore even with the same crater:

```text
same terrain
≠
same pixels
```

because illumination changes.

---

# 6. Why illumination variation is especially nasty on the Moon

The fundamental point is:

> **Changing illumination can change local intensity and gradient patterns dramatically even though the terrain itself has not changed.**

Actual illumination depends on:

- crater shape,
- local slope,
- terrain,
- Sun azimuth,
- Sun elevation,
- incidence angle.

The important distinction is:

> **Geometry remains, radiometry changes.**

---

# 7. “Scale invariant”

Suppose one camera sees:

```text
┌─────────────────┐
│                 │
│      crater     │
│       ○         │
│                 │
└─────────────────┘
```

Another higher-resolution camera might see:

```text
┌────────────────────────────┐
│                            │
│        __________          │
│      /          \          │
│     /            \         │
│    |   ○   ○      |        │
│     \            /         │
│      \__________/          │
└────────────────────────────┘
```

The same crater occupies radically different numbers of pixels.

That is **scale variation**.

The official statement says this arises because lunar imaging missions operate at different altitudes and spatial resolutions, creating scale ratios.

---

# 8. Spatial resolution

Suppose:

### Camera A

\[
1\ pixel = 0.25\ m
\]

### Camera B

\[
1\ pixel = 5\ m
\]

Then a 20 m crater occupies approximately:

For camera A:

\[
20 / 0.25 = 80\ pixels
\]

For camera B:

\[
20/5 = 4\ pixels
\]

Same physical object, but:

```text
Camera A: crater ≈ 80 pixels wide
Camera B: crater ≈ 4 pixels wide
```

A feature detector therefore sees two extremely different structures.

This is why comparing images purely in **pixel coordinates** can be misleading.

The physical quantity underneath is meters per pixel, commonly called **ground sample distance** or an equivalent spatial-resolution measure.

---

# 9. “Invariant” does NOT mean literally unchanged

When computer-vision papers say:

> scale invariant

they usually do **not** mean:

> absolutely perfect under arbitrary scaling from 1× to infinity.

They mean that the representation/method is designed to tolerate scale changes within some meaningful operating range.

Same with:

- rotation invariant,
- illumination invariant,
- viewpoint invariant.

A safer presentation statement is:

> “The system must remain capable of establishing correspondence despite substantial scale differences.”

---

# 10. “Chandrayaan-2 optical images”

The problem is specifically about the Chandrayaan-2 orbiter's optical payload products.

The statement names:

- **OHRC**
- **TMC-2**
- **IIRS**

as Chandrayaan-2 sources.

It also lists LRO NAC and SELENE imagery as reference imagery.

One conceptual distinction matters:

### “Optical” does not necessarily mean “ordinary photograph”

Remote-sensing images are sensor measurements.

Each pixel represents a measured signal associated with:

- location,
- wavelength/spectral band,
- detector,
- observation geometry,
- acquisition conditions.

That becomes important later when dealing with IIRS.

---

# 11. Source image

The official statement defines:

> **Source Image (Moving): The image that is to be geometrically transformed to align with the reference image.**

“Moving” does **not** mean the spacecraft is currently moving.

It means:

> This is the image whose coordinate system we are going to modify.

Suppose:

```text
SOURCE
crater at:
(100, 200)
```

and:

```text
REFERENCE
same crater at:
(340, 510)
```

We estimate a transform \(T\) such that:

\[
T(100,200)\approx(340,510)
\]

The source is consequently called the **moving image**.

---

# 12. Reference image

The official statement defines:

> **Reference Image (Fixed): The target image about which source image is to be geometrically transformed.**

More naturally:

> The reference defines the coordinate frame that you want the final result to match.

You generally leave its pixel grid unchanged.

After registration, the source and reference should describe the same terrain in the same coordinate frame.

---

# 13. “Common coordinate system”

Registration aligns images into a **common coordinate system**.

Before registration:

```text
Source coordinates:
(x_s, y_s)

Reference coordinates:
(x_r, y_r)
```

These are separate coordinate systems.

After estimating \(T\):

\[
(x_r,y_r)=T(x_s,y_s)
\]

Now a source location can be expressed in the reference coordinate system.

That enables questions like:

> Which source pixel corresponds to this reference pixel?

---

# 14. What is a “geometric transform”?

A transformation is a mathematical rule mapping coordinates.

For example, the simplest possible transformation is translation:

\[
x'=x+t_x
\]

\[
y'=y+t_y
\]

If:

\[
t_x=20,\quad t_y=-5
\]

then:

\[
(100,100)\rightarrow(120,95)
\]

Lunar imagery may additionally involve:

- rotation,
- scaling,
- shear,
- perspective-like effects,
- more complex spatial distortion.

Different transformation models can represent different amounts of complexity.

For now:

> **Correspondences give evidence from which the geometric transformation can be estimated.**

---

# 15. “Finding match points”

The problem statement explicitly asks for **match points**.

Imagine:

```text
SOURCE                    REFERENCE

● A                        ● A'
     ● B              ● B'
          ● C                    ● C'
```

The output might conceptually contain:

```text
source_x source_y   ref_x ref_y
--------------------------------
101.4    550.2      861.8  421.3
430.8    221.9      997.1  173.4
701.2    809.6     1325.7  694.1
```

Each row says:

> “These two coordinates correspond to the same physical lunar location.”

Those are match points.

---

# 16. A feature is not necessarily a “named feature”

When people hear “match points,” they may imagine:

- crater centre,
- mountain peak,
- rock.

Not necessarily.

A match point can simply be a visually distinctive local position such as:

```text
edge intersection
ridge corner
texture structure
crater-rim junction
```

The computer does not necessarily have to understand:

> “This is crater Aristarchus.”

It may only determine:

> “This local structure in image A corresponds strongly to that local structure in image B.”

---

# 17. Keypoint vs correspondence vs match

Keep these terms separate.

### Keypoint

A point detected in **one image**.

```text
Source:
P1, P2, P3, P4
```

### Candidate match

An algorithm suspects:

\[
P_2 \leftrightarrow Q_7
\]

### Correspondence

A pairing between points from the two images.

### Correct correspondence / inlier

A correspondence consistent with the actual geometric relationship.

### Incorrect correspondence / outlier

A false pairing.

---

# 18. “Viewpoint variation”

The official statement defines this as differences caused by camera position/orientation, making objects appear shifted, scaled, rotated or perspective-distorted.

Think of photographing a circular plate.

Straight overhead:

```text
     _______
   /         \
  |           |
   \_________/
```

From the side:

```text
    __________
  /            \
  \____________/
```

Same physical object.

Different projection.

For lunar data this can arise because observations may have different:

- spacecraft positions,
- viewing angles,
- sensor orientations,
- orbit geometry.

So:

\[
\text{same terrain}\not\Rightarrow\text{same 2-D shape}
\]

---

# 19. Why viewpoint variation differs from illumination variation

### Illumination variation

Changes mostly:

\[
\text{pixel intensity / appearance}
\]

while physical terrain remains the same.

### Viewpoint variation

Changes:

\[
\text{where and how terrain is projected onto the image}
\]

So:

```text
Illumination:
same geometry, different brightness

Viewpoint:
different apparent geometry
```

Real imagery can have both simultaneously.

---

# 20. Scale variation is technically a type of geometric variation

You might ask:

> “If viewpoint can cause scaling, why does ISRO separately mention scale variation?”

Because there is an additional huge cause:

> **Different spatial resolutions from different sensors/missions.**

A small viewpoint difference might make something 1.1× larger.

Different sensors could produce much larger resolution ratios.

Therefore scale deserves explicit treatment.

---

# 21. The most important sentence

ISRO asks for:

> **“Generic software solution for finding correspondence between Chandrayaan-2 acquired optical images and Lunar reference images with a sub-pixel accuracy of source image maintaining uniform distribution across the images.”**

Break it apart.

---

# 22. “Generic software solution”

**Generic** is significant.

They are not asking for:

```text
a script that works for one manually selected image pair
```

The intended system should handle a broader class of valid lunar-registration inputs.

At minimum, conceptually:

```text
Input:
source lunar image
reference lunar image

↓

automated/general pipeline

↓

match points
transformation
registered result
metrics
```

“Generic” argues against:

- manually entering correspondences for every pair,
- hand-tuning coordinates for one demonstration,
- hardcoding a known transform,
- building something that only works on one particular crop.

It should be a **software solution**, not merely one successful experiment.

---

# 23. “Finding correspondence”

This is the core computational output.

Given:

\[
I_s
\]

and:

\[
I_r
\]

find a set:

\[
C=
\{
(p_i,q_i)
\}_{i=1}^{N}
\]

where:

\[
p_i=(x_i^s,y_i^s)
\]

and:

\[
q_i=(x_i^r,y_i^r)
\]

Each pair asserts:

> source point \(p_i\) and reference point \(q_i\) represent the same terrain location.

Everything downstream depends on the quality of \(C\).

---

# 24. “Sub-pixel accuracy”

This is perhaps the most important technical phrase.

A pixel coordinate does not have to be an integer.

Integer precision:

```text
(412, 731)
```

Sub-pixel precision:

```text
(412.27, 730.63)
```

Sub-pixel accuracy means the registration error should be **less than one source-image pixel** under the relevant accuracy definition.

For example:

True correspondence:

\[
(100.00,100.00)
\]

Predicted:

\[
(100.31,99.82)
\]

error:

\[
e=
\sqrt{0.31^2+(-0.18)^2}
\]

\[
e\approx0.36\text{ pixels}
\]

That is below one pixel.

---

# 25. Why “source image” matters

The statement specifically says:

> **sub-pixel accuracy of source image**.

This matters because images may have different resolutions.

Suppose:

```text
source:
1 pixel = 0.25 m

reference:
1 pixel = 0.50 m
```

Then:

```text
0.8 source pixels = 0.20 m
0.8 reference pixels = 0.40 m
```

These are not the same physical error.

So always ask:

> **Pixel error measured in which image's pixel grid?**

The statement answers:

> source image.

---

# 26. Pixel accuracy vs sub-pixel localization

Images are sampled at discrete pixel positions, but an estimated geometric correspondence can be continuous.

For instance, after fitting a transformation:

\[
T(x,y)
\]

there is no requirement that:

\[
T(100,200)
\]

must land at integer coordinates.

It might produce:

\[
(523.417,811.203)
\]

That is valid.

Sub-pixel registration therefore generally involves **continuous coordinate estimation**, despite the images themselves being sampled on pixel grids.

---

# 27. “Maintaining uniform distribution across the images”

This is easy to overlook.

Imagine you produce **1,000 excellent matches**.

Sounds great.

But all 1,000 are here:

```text
┌───────────────────────────────┐
│●●●●●●                         │
│●●●●●●                         │
│●●●●●●                         │
│                               │
│                               │
│                               │
│                               │
│                               │
└───────────────────────────────┘
```

That is **not spatially uniform**.

Compare:

```text
┌───────────────────────────────┐
│ ●          ●         ●        │
│       ●                       │
│                  ●            │
│ ●                    ●        │
│          ●                    │
│                        ●      │
│    ●          ●               │
│                    ●          │
└───────────────────────────────┘
```

Now correspondences cover the image.

That is much closer to the intent of **uniform distribution**.

---

# 28. Why uniformity matters

Suppose all correspondences lie near the top-left corner.

You may accurately estimate the transformation **there**.

But what happens at the bottom-right?

You have little evidence.

Therefore the requirement is not merely:

> “Give me many correct matches.”

It is stronger:

> **Give me accurate correspondences that represent the spatial extent of the image.**

Think:

\[
\text{quality}
=
\text{accuracy}
+
\text{coverage}
\]

not just:

\[
\text{quality}=\text{number of matches}
\]

---

# 29. This is why match count alone is insufficient

Suppose algorithm A finds:

```text
2000 correct matches
```

but they are almost entirely in one crater-rich region.

Algorithm B finds:

```text
600 correct matches
```

distributed across the image.

Depending on the registration objective, B may be far more useful.

Hence **uniform distribution** changes what a good solution means.

---

# 30. What is the “registered product”?

ISRO asks for:

> **Software and registered product with corresponding match points.**

The **registered product** is essentially the geometrically corrected/aligned output.

Conceptually:

```text
BEFORE

Reference:
      crater ●

Source:
                  crater ●
```

After estimating \(T\) and warping the source:

```text
AFTER

Reference:
      crater ●

Registered source:
      crater ●
```

The source pixels have been resampled into the reference geometry.

---

# 31. “Warping”

**Warping** means:

> Use the estimated geometric transformation to generate a transformed version of the source image.

Suppose:

\[
T(x_s,y_s)=(x_r,y_r)
\]

Then you create a new source representation in the reference coordinate frame.

That transformed source is the registered output.

---

# 32. Correspondence and warp are two different outputs

### Correspondence output

```text
P1 ↔ Q1
P2 ↔ Q2
P3 ↔ Q3
...
```

### Registered image

```text
complete source image geometrically transformed
into reference coordinates
```

ISRO asks for both: the registered product **with corresponding match points**.

---

# 33. Evaluation metrics

ISRO gives examples:

- RMSE
- inlier match count
- inlier ratio

and leaves room for others through “etc.”

Understand all three precisely.

---

# 34. Inlier

Suppose the algorithm claims:

\[
P_i\leftrightarrow Q_i
\]

After estimating transformation \(T\), test:

\[
T(P_i)
\]

against:

\[
Q_i
\]

If they are sufficiently close:

```text
predicted ●──● observed
        small error
```

the match is an **inlier**.

If:

```text
predicted ●────────────────● observed
               huge error
```

it may be an **outlier**.

The exact threshold depends on the evaluation methodology.

---

# 35. Inlier match count

This is simply:

\[
N_\text{inlier}
\]

Example:

```text
Total matches = 800
Correct/geometrically consistent = 620
```

Then:

\[
N_\text{inlier}=620
\]

Higher is generally desirable, but count alone says nothing about spatial distribution.

---

# 36. Inlier ratio

\[
\text{Inlier Ratio}
=
\frac{N_\text{inlier}}
{N_\text{total matches}}
\]

Example:

\[
\frac{620}{800}
=
0.775
\]

or:

\[
77.5\%
\]

This measures the reliability/purity of the proposed match set.

Example:

### Algorithm A

```text
10,000 matches
1,000 correct
```

\[
10\%\text{ inliers}
\]

### Algorithm B

```text
1,500 matches
1,200 correct
```

\[
80\%\text{ inliers}
\]

A has more raw matches.

B's matches are dramatically more reliable.

---

# 37. RMSE

RMSE = **Root Mean Square Error**.

For each correspondence:

\[
e_i=
\sqrt{
(\hat{x}_i-x_i)^2+
(\hat{y}_i-y_i)^2
}
\]

Then:

\[
RMSE
=
\sqrt{
\frac{1}{N}
\sum_{i=1}^{N}e_i^2
}
\]

Simple interpretation:

> **How far away, on average in a squared-error sense, are the predicted corresponding positions?**

If:

\[
RMSE=0.42\text{ source pixels}
\]

then the residual error scale is below one source pixel.

---

# 38. Why it is “root mean square”

Suppose errors are:

```text
0.2 px
0.3 px
0.4 px
2.5 px
```

Squaring them gives:

```text
0.04
0.09
0.16
6.25
```

Large errors contribute disproportionately.

Therefore RMSE penalizes large residuals more heavily than a simple mean absolute error would.

---

# 39. But RMSE alone cannot tell you everything

Consider:

```text
RMSE = 0.30 px
```

Excellent.

But imagine every measured point lies here:

```text
┌────────────────────┐
│ ●●●●               │
│ ●●●●               │
│                    │
│                    │
│                    │
└────────────────────┘
```

Can you conclude:

> “The entire image is registered to 0.3 pixels”?

Not necessarily.

You've demonstrated strong accuracy **where you had validation points**.

This is why the phrase:

> **uniform distribution across the images**

deserves serious treatment.

---

# 40. The three challenges form different kinds of instability

A useful mental model:

| Challenge | What changes? |
|---|---|
| Illumination variation | pixel appearance |
| Viewpoint variation | image geometry |
| Scale variation | apparent size / sampling |
| Multi-modality | sensor representation |

The system must recover:

\[
\boxed{\text{same physical terrain}}
\]

despite all of those changing.

---

# 41. Think in terms of “physical reality vs image”

There is a real lunar surface:

\[
L
\]

Different sensors observe it through different processes.

You can imagine:

\[
I_1=F_1(L)
\]

\[
I_2=F_2(L)
\]

where \(F_1\) and \(F_2\) include:

- sensor properties,
- viewing geometry,
- resolution,
- sunlight,
- spectral response.

So although both originate from the same terrain:

\[
I_1\neq I_2
\]

sometimes dramatically.

Your task is to recover:

\[
\text{which location in }I_1
\]

corresponds to:

\[
\text{which location in }I_2.
\]

That is a much better abstraction than:

> “compare two Moon photographs.”

---

# 42. “Same scene” does not mean same image bounds

“Same scene” can mean **overlapping terrain**, not necessarily two perfectly identical rectangular footprints.

For example:

```text
Image A
┌───────────────┐
│               │
│        ┌──────┼───────┐
│        │//////│       │
│        │//////│       │
└────────┼──────┘       │
         │              │
         └──────────────┘
             Image B
```

The shaded region is the common physical terrain.

Only that overlap can yield valid correspondences.

---

# 43. What the system conceptually does

At a very abstract level:

```text
Chandrayaan-2 source
        +
lunar reference
        │
        ▼
normalize / represent
        │
        ▼
detect useful locations
        │
        ▼
describe them
        │
        ▼
find candidate correspondences
        │
        ▼
reject false correspondences
        │
        ▼
estimate geometry
        │
        ▼
refine positions
        │
        ▼
obtain sub-pixel matches
        │
        ▼
ensure spatial coverage
        │
        ▼
warp source
        │
        ▼
registered product
        +
match points
        +
metrics
```

This is not yet a POC architecture. It is the conceptual decomposition implied by the problem.

---

# 44. What “generic” prevents you from doing

Weak demonstrations would be:

```text
a script that works for one manually selected image pair
```

or:

```text
manually pick 10 crater centres
```

or:

```text
hard-code coordinates for one LRO/OHRC pair
```

or:

```text
manually adjust rotation until the images overlap
```

because those do not convincingly solve:

> **generic software solution for finding correspondence.**

The system should **discover correspondences**, not merely display ones already provided.

---

# 45. Detection vs matching vs verification

These are separate concepts.

Suppose the algorithm detects:

```text
Source:
1000 interesting points

Reference:
1200 interesting points
```

That is **feature/keypoint detection**.

Next it says:

```text
source point #41 probably corresponds
to reference point #817
```

That's **matching**.

Then geometric reasoning says:

```text
No, that pairing contradicts all
the other matches.
```

That's **verification/outlier rejection**.

---

# 46. Why false matches are inevitable

The Moon contains repeated-looking structures.

Many craters can resemble other craters.

If a local descriptor only sees a small patch, there may be numerous similar patches elsewhere.

Therefore:

\[
\text{visual similarity}
\neq
\text{true geographical correspondence}
\]

This is why geometric verification and global consistency become important.

---

# 47. What ISRO does NOT explicitly specify

The problem statement does **not** prescribe:

- SIFT,
- ORB,
- LoFTR,
- SuperPoint,
- transformers,
- deep learning,
- classical computer vision,
- homography,
- affine transformation,
- TPS,
- DEM-based correction,
- a specific matching architecture.

It asks for an **outcome**, not a specific algorithm.

That gives the team freedom in implementation.

---

# 48. What ISRO also does not fully formalize

The statement says:

> maintaining uniform distribution across the images.

But it does not provide a mathematical definition of “uniform distribution.”

Therefore your team will eventually need to define a defensible metric.

Possible approaches include:

```text
grid occupancy
spatial entropy
coverage percentage
nearest-neighbour spacing
quadrant coverage
convex-hull coverage
```

These belong to the evaluation/design discussion later.

Likewise, “sub-pixel” requires an evaluation protocol:

- Error relative to what ground truth?
- At which control points?
- Before or after outlier removal?
- RMSE?
- 95th percentile?
- Entire image?
- Only overlap region?
- Source-pixel units or physical distance?

The PS gives example metrics but does not completely formalize the evaluation protocol.

---

# 49. Why real imagery creates an evaluation problem

Suppose your system outputs:

\[
RMSE=0.27\text{ px}
\]

You should immediately ask:

> **0.27 pixels relative to what known truth?**

If the true transform is unknown, you cannot simply declare the result accurate because the estimated model agrees with its own selected matches.

For synthetic experiments, you can intentionally apply a known transform:

\[
T_\text{true}
\]

then estimate:

\[
T_\text{pred}
\]

and compare them.

That gives genuine ground truth.

Synthetic validation is therefore scientifically useful, although real-data performance must ultimately be demonstrated separately.

---

# 50. The three levels of evidence

Keep these separate in the presentation:

```text
ISRO requirement
       ↓
project analysis / experiment
       ↓
design decision
```

For example:

### ISRO requirement

Sun-angle variation is a stated challenge.

### Project analysis

A synthetic experiment shows how a particular baseline behaves as Sun angle changes.

### Design decision

Therefore the POC needs a correspondence strategy that is more robust to illumination changes.

This separation makes the argument much more defensible.

---

# 51. The problem in mathematical language

Let:

\[
S(x,y)
\]

be the source image.

Let:

\[
R(u,v)
\]

be the reference image.

There exists some physical/geometric relationship:

\[
(u,v)=T(x,y)
\]

Your system must estimate correspondences:

\[
(x_i,y_i)
\leftrightarrow
(u_i,v_i)
\]

despite appearance changes.

From them estimate/refine:

\[
\hat T
\]

such that:

\[
\hat T(p_i)
\approx
q_i
\]

with residuals ideally below one source pixel under the chosen evaluation definition, while the \(p_i\) are reasonably distributed across the source-image domain.

Then generate:

\[
S_\text{registered}
\]

in the reference coordinate frame.

That's SIH26166 in mathematical form.

---

# 52. The single most important conceptual picture

```text
             REAL LUNAR TERRAIN
                    │
          ┌─────────┴──────────┐
          │                    │
       Sensor A             Sensor B
          │                    │
   different Sun          different Sun
   different view         different view
   different scale        different scale
   different modality     different modality
          │                    │
          ▼                    ▼
      SOURCE               REFERENCE
          │                    │
          └─────────┬──────────┘
                    │
            FIND SAME PLACES
                    │
              correspondences
                    │
            estimate geometry
                    │
              warp source
                    │
                    ▼
           REGISTERED PRODUCT
```

Everything else is implementation detail.

---

# 53. A concise explanation for the group

> **“We have two images containing overlapping lunar terrain. One is the Chandrayaan-2 source image and the other is a fixed lunar reference. Because they may come from different sensors, resolutions, viewing geometries and Sun angles, the same terrain can look very different in both images. Our job is to automatically identify which coordinates represent the same physical lunar locations. Using those correspondences, we estimate a geometric transformation that warps the Chandrayaan image into the reference coordinate system. ISRO specifically demands that this registration reach sub-pixel accuracy measured relative to the source image, and that the correspondences be spatially distributed across the image rather than concentrated in one region. The final output must include the registered image, the match points and quantitative evaluation such as RMSE, inlier count and inlier ratio.”**

If everyone understands every noun in that paragraph, they understand the problem statement.

---

# 54. What to understand before the POC

Before discussing implementation, make sure these six concepts are completely clear:

1. **Radiometric differences** — the same terrain can have different brightness/appearance.
2. **Geometric differences** — the same terrain can occupy different coordinates/shapes.
3. **Feature correspondence** — identifying the same physical location in two images.
4. **Transformation estimation** — deriving the geometry that maps source coordinates to reference coordinates.
5. **Residual error** — measuring how far predicted correspondences are from their expected positions.
6. **Spatial coverage** — ensuring correspondences represent the image rather than one small region.

Once these are clear, the POC architecture becomes much easier to understand.