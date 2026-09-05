"""Per-step configuration for the preprocessing pipeline.

Every step is independently toggleable, which is the point: the paper reports
that CLAHE mattered for extreme illumination but does not isolate the
contribution of the other steps, so the ablation is ours to run.

Two presets mirror the paper's own structure. Makharia et al. do **not** apply
one universal chain -- they apply a common core (4.1) to everything and then a
*different* specialised set (4.2) per sensor pair:

* :func:`ohrc_nac_config` -- core + CLAHE, inversion, dilation, PCA
* :func:`iirs_wac_config` -- core + histogram matching, shadow normalisation,
  log transform

Mixing steps across the two tracks is allowed here, but such a run is no longer
the paper's configuration for either pair; :meth:`PreprocessConfig.describe`
says so.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace

from lunar_reg.preprocess.params import (
    CLAHE_CLIP_LIMIT,
    CLAHE_TILE_GRID,
    DILATION_KERNEL_SHAPE,
    DILATION_KERNEL_SIZE,
    PCA_N_COMPONENTS,
    SHADOW_GAMMA,
    SHADOW_METHOD,
    SHADOW_PERCENTILE,
)

#: Step names in the order the pipeline applies them. The core steps (4.1) come
#: first and in the paper's order; the specialised ones (4.2) follow.
STEP_ORDER: tuple[str, ...] = (
    "georeference",
    "band_reduction",
    "resample",
    "normalize",
    "histogram_match",
    "shadow",
    "clahe",
    "invert",
    "dilate",
    "log_transform",
)

#: Which paper track each specialised step belongs to.
STEP_TRACKS: dict[str, str] = {
    "georeference": "core",
    "band_reduction": "core",
    "resample": "core",
    "normalize": "core",
    "clahe": "ohrc_nac",
    "invert": "ohrc_nac",
    "dilate": "ohrc_nac",
    "histogram_match": "iirs_wac",
    "shadow": "iirs_wac",
    "log_transform": "iirs_wac",
}


@dataclass
class PreprocessConfig:
    """Which steps run, and with what parameters.

    Booleans toggle steps; the remaining fields are their parameters. Values
    sourced from :mod:`lunar_reg.preprocess.params` carry their provenance
    there -- most are PLACEHOLDERS the paper does not state.
    """

    # --- core pipeline (paper 4.1) ---
    georeference: bool = False
    resample: bool = True
    normalize: bool = True

    # --- multi-band handling (paper 4.2 B preamble, and 4.2.4 PCA) ---
    band_reduction: bool = True
    band_reduction_method: str = "pca"  # pca | select | mean
    pca_n_components: int = PCA_N_COMPONENTS.value
    reference_band: int | None = None

    # --- specialised: OHRC/NAC track (paper 4.2 A) ---
    clahe: bool = True
    clahe_clip_limit: float = CLAHE_CLIP_LIMIT.value
    clahe_tile_grid: tuple[int, int] = CLAHE_TILE_GRID.value
    invert: bool = False
    dilate: bool = False
    dilation_kernel_size: int = DILATION_KERNEL_SIZE.value
    dilation_kernel_shape: str = DILATION_KERNEL_SHAPE.value

    # --- specialised: IIRS/WAC track (paper 4.2 B) ---
    histogram_match: bool = False
    shadow: bool = True
    shadow_method: str = SHADOW_METHOD.value
    shadow_percentile: float = SHADOW_PERCENTILE.value
    shadow_gamma: float = SHADOW_GAMMA.value
    log_transform: bool = False

    # --- resampling ---
    source_sensor: str | None = None
    reference_sensor: str | None = None
    target_gsd_m: float | None = None

    #: Free-form label carried into the pipeline history, for ablation tables.
    label: str = "default"

    def enabled_steps(self) -> tuple[str, ...]:
        return tuple(s for s in STEP_ORDER if getattr(self, s))

    def toggle(self, step: str, on: bool) -> PreprocessConfig:
        """A copy with one step switched. Does not mutate the original."""
        if step not in STEP_ORDER:
            raise ValueError(f"unknown step {step!r}; expected one of {STEP_ORDER}")
        return replace(self, **{step: on}, label=f"{self.label}[{step}={'on' if on else 'off'}]")

    def tracks_used(self) -> set[str]:
        return {STEP_TRACKS[s] for s in self.enabled_steps()} - {"core"}

    def describe(self) -> str:
        enabled = self.enabled_steps()
        chain = " -> ".join(enabled) or "(none)"
        lines = [f"config {self.label!r}: {len(enabled)} step(s) -> {chain}"]
        tracks = self.tracks_used()
        if len(tracks) > 1:
            lines.append(
                "  NOTE: mixes steps from both paper tracks "
                f"({', '.join(sorted(tracks))}); this is not the paper's configuration "
                "for either sensor pair"
            )
        return "\n".join(lines)

    def as_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}


def ohrc_nac_config(**overrides) -> PreprocessConfig:
    """The paper's OHRC/LROC-NAC configuration (its section 4.2 A).

    Core pipeline plus CLAHE, inversion, dilation. Shadow normalisation and log
    transform belong to the other track and are off.
    """
    base = PreprocessConfig(
        label="paper/ohrc_nac",
        source_sensor="OHRC", reference_sensor="LRO_NAC",
        clahe=True, invert=True, dilate=True,
        histogram_match=False, shadow=False, log_transform=False,
        band_reduction=False,
    )
    return replace(base, **overrides) if overrides else base


def iirs_wac_config(**overrides) -> PreprocessConfig:
    """The paper's IIRS/LROC-WAC configuration (its section 4.2 B).

    Core pipeline plus band selection, histogram matching, shadow normalisation
    and log transform. CLAHE, inversion and dilation belong to the other track.
    """
    base = PreprocessConfig(
        label="paper/iirs_wac",
        source_sensor="IIRS", reference_sensor="LRO_WAC",
        band_reduction=True, band_reduction_method="select",
        histogram_match=True, shadow=True, log_transform=True,
        clahe=False, invert=False, dilate=False,
    )
    return replace(base, **overrides) if overrides else base


def minimal_config(**overrides) -> PreprocessConfig:
    """Core pipeline only -- the ablation baseline.

    Everything the paper considers an *enhancement* is off, so a leave-one-out
    sweep has something meaningful to be measured against.
    """
    base = PreprocessConfig(
        label="minimal",
        clahe=False, shadow=False, invert=False, dilate=False,
        histogram_match=False, log_transform=False, band_reduction=True,
    )
    return replace(base, **overrides) if overrides else base


def ablation_configs(
    base: PreprocessConfig | None = None,
    steps: tuple[str, ...] | None = None,
) -> list[PreprocessConfig]:
    """Leave-one-out configs for every enabled step, plus the base itself.

    The first entry is ``base`` unchanged; each subsequent entry has exactly one
    enabled step switched off, so comparing each against the first isolates that
    step's contribution.
    """
    base = base or PreprocessConfig()
    candidates = steps or base.enabled_steps()
    return [base, *(base.toggle(step, False) for step in candidates)]
