# 90 · Glossary

Keep this open while reading the others. Every term is defined assuming a
software background and nothing else. The doc where a term is properly
introduced is named in the last column.

## The domain

| term | meaning | doc |
|---|---|---|
| **affine** | a transform that can shift, rotate, scale and shear, but keeps parallel lines parallel. 6 numbers. | 20 |
| **anti-meridian** | the ±180° longitude line. Arithmetic breaks across it: 179.9° and −179.9° are 0.2° apart on the ground and 359.8° apart as numbers. | 11 |
| **azimuth** | a compass direction, in degrees. "Sun azimuth" = which way the sun is, horizontally. | 01 |
| **azimuthal equidistant** | a projection built around one centre point, in which distances *from that centre* are exact. Used here for polar footprints. | 11 |
| **band** | one channel of a multi-channel image. A colour photo has 3; IIRS has ~256. | 31 |
| **bounding box** | the smallest north–south / east–west rectangle containing a shape. A fast pre-filter; never a final answer. | 12 |
| **bow-tie** | a four-sided polygon whose corners were listed in the wrong order, so its edges cross. Its "area" is meaningless. | 12 |
| **colatitude** | 90° − latitude. Angular distance from the pole rather than from the equator. | 10 |
| **conformal** | a projection preserving local shape and angles, at the cost of area. | 11 |
| **convex** | no dents — a line between any two interior points stays inside. Several clipping algorithms silently require it. | 11 |
| **datum** | the agreed model of a body's shape, centre and axes. Coordinates are meaningless without one. | 10 |
| **DEM** | Digital Elevation Model — a raster of heights. TMC-2's real product. | 31 |
| **detector-free** | a matcher that never picks keypoints and compares everything to everything. LoFTR. | 21 |
| **ellipsoid** | a squashed sphere. Earth is one; the Moon is close enough to a sphere that we use a sphere. | 10 |
| **emission angle** | the angle between straight-down and the direction to the spacecraft. Absent from our OHRC labels. | 30 |
| **equal-area** | a projection preserving area, at the cost of shape. | 11 |
| **equidistant** | a projection preserving distance, but only along particular lines. | 11 |
| **footprint** | the patch of ground an image covers, as a polygon. | 12 |
| **foreshortening** | distant things appearing compressed. A perspective effect a pushbroom sensor does not produce. | 20 |
| **georeferenced** | the file knows where on the body each pixel is. The difference between a picture and a map. | 31 |
| **great circle** | the shortest path between two points on a sphere. | 10 |
| **ground track** | the path the spacecraft's position traces on the surface below it. Not aligned to north. | 12 |
| **GSD** | Ground Sample Distance — how much ground one pixel covers. | 31 |
| **haversine** | the numerically stable formula for great-circle distance. | 10, 60 |
| **homography** | affine plus perspective; parallel lines may converge. 8 numbers. Also called *projective*. | 20 |
| **hyperspectral** | many narrow spectral bands, so each pixel is a spectrum. IIRS. | 31 |
| **incidence angle** | the angle between straight-down and the direction to the sun. ISRO stores it as `solar_incidence`. | 30 |
| **nadir** | straight down. *Fore* and *aft* are forward and backward along the flight path. | 31 |
| **panchromatic** | one broad brightness band. Black and white. OHRC and TMC-2. | 31 |
| **PDS4** | the XML-based planetary archive standard. A label plus a raw binary blob. | 30 |
| **phase angle** | the angle at the surface between the sun and the spacecraft. Absent from our OHRC labels. | 30 |
| **planetocentric / planetographic** | two definitions of latitude, identical on a sphere, different on a squashed body. Ours is not stated. | 10 |
| **PRADAN** | ISRO's data portal. Its download scripts contain **live session cookies** — treat them as credentials. | 30 |
| **projection** | a rule for flattening a curved surface onto a plane. Always distorts something. | 11 |
| **pushbroom** | a sensor with one row of detectors, read out repeatedly while the spacecraft moves. **No single viewpoint.** | 13 |
| **radiometric** | to do with brightness values rather than geometry. | 40 |
| **ring order** | the order corners must be in to trace a polygon's boundary without crossing. For ISRO corners: **1, 2, 4, 3**. | 12 |
| **selenographic** | "geographic, for the Moon". *Seleno-* = Moon. | 10 |
| **spectral band** | a narrow slice of wavelengths. | 31 |
| **spherical excess** | the amount by which a spherical triangle's angles exceed 180°. Proportional to its area — how footprint area is computed. | 60 |
| **stereo** | two or more views from different angles, from which height can be derived. | 31 |
| **swath** | how wide a strip of ground a camera sees in one pass. OHRC's is ~3 km. | 31 |
| **terminator** | the line between lit and unlit surface. Abrupt on the Moon — no atmosphere to soften it. | 01 |

## Matching and fitting

| term | meaning | doc |
|---|---|---|
| **attention** | a neural mechanism where each element decides which other elements matter to it. Self-attention looks within one image, cross-attention between two. | 21 |
| **bootstrap** | resample your own data with replacement many times, redo the analysis, look at the spread of answers. | 23 |
| **Clark–Evans index `R`** | mean nearest-neighbour distance ÷ what it would be under complete randomness. `R < 1` clustered, `≈ 1` random, `> 1` dispersed. | 23 |
| **CNN** | Convolutional Neural Network. Slides learned filters over an image. | 61 |
| **coverage `C`** | fraction of grid cells containing at least one match. | 23 |
| **degrees of freedom** | how many independent numbers a transform has, and therefore the minimum evidence needed to fit it. | 20 |
| **descriptor** | a short vector summarising a keypoint's neighbourhood, so it can be compared across images. | 21 |
| **detector** | the part that decides *where* keypoints are. | 21 |
| **DISK** | a CNN keypoint detector and descriptor. SIFT's job, learned. | 21 |
| **ECC** | Enhanced Correlation Coefficient. Sub-pixel refinement on raw brightness, invariant to *linear* brightness change — which lunar illumination change is not. | 22 |
| **entropy `H`** | how evenly matches are spread among occupied cells. Normalised to 0–1. | 23 |
| **extrapolation** | predicting outside the region your data covers. Where transforms go wrong. | 23 |
| **GNN** | Graph Neural Network. A network over a set of things and their connections. LightGlue. | 61 |
| **inlier / outlier** | a match that agrees / does not agree with the fitted transform. | 22 |
| **keypoint** | a spot a program decided is distinctive enough to find again. | 21 |
| **LightGlue** | an attention-based matcher that pairs two keypoint sets, reasoning about them jointly. | 21 |
| **LoFTR** | the main learned matcher here. CNN backbone + transformer, detector-free. | 21 |
| **least squares** | fit by minimising summed squared error. Fast, closed-form, ruined by one bad point. | 22 |
| **LLM** | Large Language Model. **Not used in this project, anywhere.** | 61 |
| **nonlinear radiation distortion** | when two images' brightness relationship is not a straight line — it inverts. The lunar illumination problem, named. | 01, 21 |
| **phase congruency** | responds to where image structure lines up across scales. Survives brightness inversion better than gradients. RIFT2's basis. | 21 |
| **RANSAC** | RANdom SAmple Consensus. Guess from a minimal sample, count who agrees, keep the winner, refit on its supporters. | 22 |
| **residual** | how far one point missed. | 22 |
| **RIFT2** | a phase-congruency cross-modal matcher. Clean-room implemented here because every existing version is unlicensed. | 21 |
| **RMSE** | Root Mean Square Error. Measured on the points you fitted to, so it is *training error*. | 23 |
| **robust** | not ruined by a minority of bad inputs. | 22 |
| **SIFT** | the classical detector/descriptor baseline. Built from brightness gradients — exactly what inverts. | 21 |
| **Spearman correlation** | how well two rankings agree. −1 to +1. Order matters, exact values do not. | 23 |
| **sub-pixel** | accurate to less than one pixel's width. The problem statement's requirement. | 22 |
| **SuperGlue** | strong neural matcher, **noncommercial licence** — runnable for comparison, not shippable. | 21 |
| **transform** | the function taking a point in one image to its position in the other. Registration's output. | 20 |
| **uniformity score `U`** | `sqrt(C · H)`. A geometric mean, so a near-zero in either component drags it down instead of being averaged away. | 23 |
| **warp** | to actually apply a transform and resample the image. | 20 |
| **zero-shot** | using pretrained weights with no training of your own. How every neural matcher here is used. | 61 |

## Systems and engineering

| term | meaning | doc |
|---|---|---|
| **BSQ / BIL / BIP** | three orders for writing multi-band pixels to disk. A wrong guess returns plausible wrong numbers, not an error. | 30 |
| **embarrassingly parallel** | splits into pieces that need no communication. The tile-pair level here. | 70 |
| **idempotent** | doing it twice has the same effect as once. What makes retries safe. | 70 |
| **label** | in PDS4, the XML metadata file, separate from the data it describes. | 30 |
| **namespace** | in XML, a prefix saying whose vocabulary an element name belongs to. ISRO's is `isda`. | 30 |
| **product** | a label plus its data file(s), as one unit. | 30 |
| **strip** | one delivered image file. An OHRC strip is 1.2 GB. | 70 |
| **tile** | a small square cut from a strip, because the matcher cannot process a whole one. Capped at 1408 px. | 70 |
| **VRAM** | memory on the graphics card. Separate from system RAM, much smaller, and the binding constraint. | 60, 70 |
| **windowed read** | reading only the byte range covering a rectangle, instead of the whole file. What makes 1.2 GB strips tractable. | 70 |

## The three evidence labels used throughout

| label | meaning |
|---|---|
| **Measured** | this project produced the number from a run. The module is named. |
| **Documented** | it comes from a paper or standard we read. |
| **Unverified / Unknown** | nobody has checked it. Stated out loud, never smoothed over. |

The rule these enforce: a claim's strength must be visible at the point where a
reader would otherwise assume certainty. A results table filled with
plausible-looking numbers no run produced is the one failure a project cannot
recover from.
