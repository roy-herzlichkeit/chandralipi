"""Decision record: why RIFT2 is a clean-room implementation.

Kept because the *reason* matters for licensing and for how results are
reported, and would otherwise survive only in a commit message.

The problem
-----------
RIFT2 is one of the four classical baselines in Makharia et al., and the most
relevant of them to the cross-modal OHRC-to-IIRS case. Every pre-existing
implementation is unlicensed:

* ``LJY-RS/RIFT2-multimodal-matching-rotation`` (the authors' MATLAB reference):
  no licence, single commit 2022-08-26, unmaintained.
* ``canyagmur/RIFT2-multimodal-matching-rotation-python`` (third-party port):
  no licence, created and last pushed 2024-07-15, not on PyPI, loose scripts,
  and no evidence it reproduces the reference numbers.
* ``phasepack``, the obvious phase-congruency building block: on PyPI, but last
  released 2016 and its licence metadata reads UNKNOWN.

No licence means all rights reserved by default, so none of them can be vendored
into a submission ISRO may evaluate or adopt.

The decision
------------
Implement from the papers instead:

* RIFT, IEEE TIP 2020 (arXiv:1804.09493) -- equations (1)-(17): log-Gabor bank,
  phase congruency, PC moments, MIM, and the 6x6 x No descriptor.
* RIFT2 (arXiv:2303.00319) -- section III: the dominant-index recoding that
  replaces RIFT's convolution-sequence ring.

**No unlicensed source was read.** The implementation in
:mod:`lunar_reg.match.rift2` derives from the published equations and from the
standard published log-Gabor construction, which makes it ours to licence with
the rest of the project.

What is and is not validated
----------------------------
Checks that pass:

* The dominant-index recoding reproduces the worked histogram example in the
  RIFT2 paper exactly -- ``{170,236,450,40,300,100}`` recodes to
  ``{236,450,40,300,100,170}`` for ``s = 2``, as printed in the paper.
* Every parameter is paper-stated: ``No = 6``, ``Ns = 4``, ``J = 96``, 6x6
  grids, 5000 keypoints, dominant ratio 0.8.
* The descriptor is invariant to affine intensity change and to contrast
  inversion, which is the property the method exists for.
* On a synthetic pair under contrast inversion, RIFT2 recovers the homography to
  0.311 px while SIFT fails outright and ASIFT and AKAZE return catastrophically
  wrong transforms (797 px and 329 px respectively).

What is **not** validated: the authors' own numbers. Reproducing them would
require running the unlicensed MATLAB, which is the thing being avoided. So this
implementation should be described as "RIFT2 as specified in the papers", never
as "reproducing the published RIFT2 results".

Known deviation
---------------
The papers use nearest-neighbour matching plus an outlier filter; this
implementation uses a Lowe ratio test, which is not specified in either paper.
See ``DEFAULT_RATIO`` in :mod:`lunar_reg.match.rift2.matcher`.
"""

from __future__ import annotations

#: Kept for callers that imported the old blocker message.
STATUS_SUMMARY = (
    "RIFT2 is implemented in lunar_reg.match.rift2 as a clean-room build from "
    "arXiv:1804.09493 and arXiv:2303.00319. No unlicensed source was consulted. "
    "Its parameters are paper-stated and its dominant-index recoding reproduces "
    "the paper's worked example, but it has NOT been checked against the authors' "
    "MATLAB output -- do not describe results as reproducing published RIFT2 numbers."
)
