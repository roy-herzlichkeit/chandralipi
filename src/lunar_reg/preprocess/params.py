"""Preprocessing parameters, each tagged with where its value came from.

The pipeline in :mod:`lunar_reg.preprocess.pipeline` reproduces the one in
Makharia et al., *Comparative Evaluation of Traditional and Deep Learning
Feature Matching Algorithms using Chandrayaan-2 Lunar Data* (arXiv:2509.04775).

The paper's full text (27 pages) was read for this module. It specifies the
pipeline **structure** in detail and a handful of **exact values**, but it
describes CLAHE, shadow normalisation, dilation and PCA only qualitatively --
no clip limit, no tile grid, no structuring element, no component count, no
shadow thresholds.

So every parameter here carries a :class:`ParamSource`:

* :attr:`ParamSource.PAPER` -- the value is quoted or unambiguously stated in
  the paper text. Changing it makes the run no longer paper-matched.
* :attr:`ParamSource.PAPER_RANGE` -- the paper gives a range; the specific value
  inside it is ours.
* :attr:`ParamSource.PLACEHOLDER` -- **the paper does not state this.** The value
  is a documented, defensible default chosen here. It is a starting point to
  tune, and results using it must not be described as reproducing the paper's
  parameters.

Call :func:`provenance_report` (or ``lunar-reg params``) before quoting any
result as paper-matched.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ParamSource(str, Enum):
    """Where a parameter's value came from."""

    #: Stated explicitly in the paper text.
    PAPER = "paper"
    #: The paper gives a range or approximate target; the exact value is ours.
    PAPER_RANGE = "paper_range"
    #: Not stated in the paper. A documented default, to be tuned.
    PLACEHOLDER = "placeholder"

    @property
    def is_paper_matched(self) -> bool:
        return self is ParamSource.PAPER


@dataclass(frozen=True)
class Param:
    """One tunable value and its provenance."""

    name: str
    value: Any
    source: ParamSource
    note: str = ""
    quote: str = ""

    @property
    def tunable(self) -> bool:
        """Whether this is a knob to sweep rather than a fixed paper value."""
        return self.source is not ParamSource.PAPER


# ---------------------------------------------------------------------------
# Values the paper states outright.
# ---------------------------------------------------------------------------

NORMALIZE_TARGET_MIN = Param(
    "normalize_target_min", 0, ParamSource.PAPER,
    quote="All datasets were normalised to an 8-bit range (0-255)",
)
NORMALIZE_TARGET_MAX = Param(
    "normalize_target_max", 255, ParamSource.PAPER,
    quote="All datasets were normalised to an 8-bit range (0-255)",
)
INVERSION_MAX = Param(
    "inversion_max", 255, ParamSource.PAPER,
    quote="transformed pixel values to their complement (255 - pixel value)",
)

#: Resampling targets, per sensor pair, in metres per pixel. The paper states a
#: target for each pair it registers. Where it gives a range, the value here is
#: our pick inside that range -- see PAPER_RANGE.
RESAMPLE_TARGETS: dict[tuple[str, str], Param] = {
    ("OHRC", "LRO_NAC"): Param(
        "gsd_ohrc_nac_m", 1.0, ParamSource.PAPER_RANGE,
        note="Paper states NAC is 0.5-2.0 m/pixel; 1.0 is our pick inside that range.",
        quote="OHRC (~30 cm resolution) was resampled to match NAC's resolution "
              "(0.5-2.0 m/pixel)",
    ),
    ("IIRS", "LRO_WAC"): Param(
        "gsd_iirs_wac_m", 100.0, ParamSource.PAPER,
        quote="IIRS (~80 m resolution) was resampled to align with WAC's "
              "100 m/pixel resolution",
    ),
    ("DFSAR", "SELENE_TC"): Param(
        "gsd_dfsar_selene_m", 9.0, ParamSource.PAPER_RANGE,
        note="Paper says '~9 m/pixel'; the approximation is theirs.",
        quote="DFSAR (2-75 m slant resolution) was resampled to match SELENE's "
              "resolution (~9 m/pixel)",
    ),
}

#: Projections the paper names. Georeferencing direction is source -> reference.
PAPER_PROJECTIONS = {
    "OHRC": "Selenographic",
    "LRO_NAC": "Equirectangular Moon",
}

# ---------------------------------------------------------------------------
# Values the paper does NOT state. Placeholders -- tune these.
# ---------------------------------------------------------------------------

CLAHE_CLIP_LIMIT = Param(
    "clahe_clip_limit", 2.0, ParamSource.PLACEHOLDER,
    note="NOT IN PAPER. The paper describes CLAHE qualitatively ('limiting the "
         "height of each histogram') and gives no clip limit. 2.0 is OpenCV's "
         "documented default and a common choice for remote sensing. Sweep this "
         "first -- it is the single most influential preprocessing knob for the "
         "extreme-illumination case the paper highlights.",
)
CLAHE_TILE_GRID = Param(
    "clahe_tile_grid", (8, 8), ParamSource.PLACEHOLDER,
    note="NOT IN PAPER. The paper says CLAHE 'operates on small regions (tiles)' "
         "but never gives a grid size. (8, 8) is OpenCV's default. On the ~1000 px "
         "tiles this pipeline works in, a finer grid amplifies noise in flat mare.",
)
DILATION_KERNEL_SHAPE = Param(
    "dilation_kernel_shape", "ellipse", ParamSource.PLACEHOLDER,
    note="NOT IN PAPER. The paper says only 'using a defined structuring element'. "
         "An ellipse avoids the axis-aligned bias a rectangular element imposes on "
         "crater rims, which are roughly circular.",
)
DILATION_KERNEL_SIZE = Param(
    "dilation_kernel_size", 3, ParamSource.PLACEHOLDER,
    note="NOT IN PAPER. 3x3 is the smallest element that dilates at all; larger "
         "values thicken rims further but start merging nearby features.",
)
PCA_N_COMPONENTS = Param(
    "pca_n_components", 1, ParamSource.PLACEHOLDER,
    note="NOT IN PAPER. The paper describes PCA as dimensionality reduction "
         "'preserving the most significant variance' without a component count. "
         "1 yields a single matchable plane, which is what the matchers consume.",
)
SHADOW_PERCENTILE = Param(
    "shadow_percentile", 5.0, ParamSource.PLACEHOLDER,
    note="NOT IN PAPER. The paper's shadow normalisation is described only as "
         "adjusting 'intensity values in shadowed regions ... while preserving "
         "overall scene contrast', with no threshold or method. This treats the "
         "darkest 5% as shadow. Two cautions: (1) highly scene-dependent -- a "
         "polar image at very low sun elevation may be 30%+ shadow; (2) the "
         "threshold is inclusive and lunar shadow saturates at few DN values, so "
         "the fraction actually selected can far exceed the percentile (measured "
         "9.1% for a nominal 5%). Check with shadow.shadow_fraction().",
)
SHADOW_METHOD = Param(
    "shadow_method", "gamma", ParamSource.PLACEHOLDER,
    note="NOT IN PAPER. Which of several plausible shadow treatments the authors "
         "used is unknown. 'gamma' brightens shadowed pixels while preserving "
         "their relative structure, matching the paper's stated intent of revealing "
         "features rather than erasing them. See shadow.py for the alternatives.",
)
SHADOW_GAMMA = Param(
    "shadow_gamma", 0.5, ParamSource.PLACEHOLDER,
    note="NOT IN PAPER. Exponent applied within shadowed regions; < 1 brightens.",
)
LOG_TRANSFORM_SCALE = Param(
    "log_transform_scale", None, ParamSource.PLACEHOLDER,
    note="NOT IN PAPER. The paper states only that log transform 'enhance[s] "
         "low-intensity details while compressing higher-intensity values'. None "
         "means derive the constant from the data as c = 255 / log(1 + max).",
)
RESAMPLE_INTERPOLATION = Param(
    "resample_interpolation", "area_or_cubic", ParamSource.PLACEHOLDER,
    note="NOT IN PAPER. The paper says only 'this process involved interpolation'. "
         "This pipeline uses INTER_AREA when shrinking (correct for a 20x+ "
         "reduction; INTER_LINEAR aliases and manufactures false corners) and "
         "INTER_CUBIC when enlarging.",
)
IIRS_REFERENCE_BAND = Param(
    "iirs_reference_band", None, ParamSource.PLACEHOLDER,
    note="NOT IN PAPER as a number. The paper says 'a single, visually clear band "
         "was selected as the reference' and that the transform computed on it was "
         "applied to all other bands -- but not which band. None means pick "
         "automatically by highest contrast; set an int to pin it.",
)

ALL_PARAMS: tuple[Param, ...] = (
    NORMALIZE_TARGET_MIN, NORMALIZE_TARGET_MAX, INVERSION_MAX,
    *RESAMPLE_TARGETS.values(),
    CLAHE_CLIP_LIMIT, CLAHE_TILE_GRID,
    DILATION_KERNEL_SHAPE, DILATION_KERNEL_SIZE,
    PCA_N_COMPONENTS,
    SHADOW_PERCENTILE, SHADOW_METHOD, SHADOW_GAMMA,
    LOG_TRANSFORM_SCALE, RESAMPLE_INTERPOLATION, IIRS_REFERENCE_BAND,
)

PARAMS_BY_NAME: dict[str, Param] = {p.name: p for p in ALL_PARAMS}

#: Parameters that are ours, not the paper's. These are the ablation knobs, and
#: no result using them may be called "paper-matched parameters".
PLACEHOLDER_PARAM_NAMES: tuple[str, ...] = tuple(
    p.name for p in ALL_PARAMS if p.source is ParamSource.PLACEHOLDER
)


def provenance_report() -> str:
    """Breakdown of which parameters are the paper's and which are ours."""
    by_source: dict[ParamSource, list[Param]] = {s: [] for s in ParamSource}
    for p in ALL_PARAMS:
        by_source[p.source].append(p)

    lines = [
        "Makharia et al. (arXiv:2509.04775) preprocessing parameters",
        "full paper text read; structure is specified, most numbers are not",
        "",
        f"{len(by_source[ParamSource.PAPER])} stated in the paper:",
    ]
    for p in by_source[ParamSource.PAPER]:
        lines.append(f"  {p.name:26s} = {p.value!r}")
        if p.quote:
            lines.append(f'      "{p.quote}"')

    lines += ["", f"{len(by_source[ParamSource.PAPER_RANGE])} chosen inside a paper-stated range:"]
    for p in by_source[ParamSource.PAPER_RANGE]:
        lines.append(f"  {p.name:26s} = {p.value!r}  -- {p.note}")

    lines += [
        "",
        f"{len(by_source[ParamSource.PLACEHOLDER])} NOT stated in the paper "
        f"(placeholders to tune, NOT paper-matched):",
    ]
    for p in by_source[ParamSource.PLACEHOLDER]:
        lines.append(f"  {p.name:26s} = {p.value!r}")
        lines.append(f"      {p.note}")

    lines += [
        "",
        "Do not describe a run using the placeholders above as reproducing the",
        "paper's parameters. It reproduces the paper's pipeline STRUCTURE only.",
    ]
    return "\n".join(lines)
