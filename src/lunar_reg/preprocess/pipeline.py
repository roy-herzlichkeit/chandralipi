"""The Makharia et al. preprocessing pipeline, step by step and fully ablatable.

Reproduces the structure in arXiv:2509.04775 section 4:

* **4.1 core** -- georeferencing, resolution resampling, intensity normalisation
* **4.2 specialised** -- per sensor pair; see
  :mod:`lunar_reg.preprocess.config` for the two tracks

Every step is toggleable and every run returns a :class:`PreprocessResult`
carrying a :class:`StepRecord` per step: whether it ran, why it was skipped if
not, and how the image changed. A step that could not run (georeferencing
without a CRS, histogram matching without a reference) is recorded as
``skipped`` with a reason -- never silently passed over, because a chain that
quietly dropped half its steps looks identical to one that ran fully.

Parameter provenance
--------------------
The paper specifies this structure precisely but states few numeric values.
Anything not stated is a placeholder chosen here. ``result.uses_placeholders``
and :func:`lunar_reg.preprocess.params.provenance_report` make that explicit;
do not describe a run as using the paper's parameters without checking.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from lunar_reg.preprocess.config import STEP_ORDER, PreprocessConfig
from lunar_reg.preprocess.params import PLACEHOLDER_PARAM_NAMES

logger = logging.getLogger(__name__)


@dataclass
class StepRecord:
    """What one pipeline step did."""

    name: str
    ran: bool
    reason: str = ""
    shape_before: tuple[int, ...] | None = None
    shape_after: tuple[int, ...] | None = None
    dtype_after: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def changed_shape(self) -> bool:
        return self.ran and self.shape_before != self.shape_after

    def __str__(self) -> str:
        if not self.ran:
            return f"  {self.name:16s} SKIPPED  {self.reason}"
        shape = (
            f"{self.shape_before} -> {self.shape_after}"
            if self.changed_shape
            else str(self.shape_after)
        )
        extra = f"  {self.detail}" if self.detail else ""
        return f"  {self.name:16s} ok       {shape} {self.dtype_after}{extra}"


@dataclass
class PreprocessResult:
    """A preprocessed image plus the full record of how it got that way."""

    image: np.ndarray
    config: PreprocessConfig
    history: list[StepRecord] = field(default_factory=list)

    @property
    def steps_run(self) -> tuple[str, ...]:
        return tuple(r.name for r in self.history if r.ran)

    @property
    def steps_skipped(self) -> tuple[str, ...]:
        return tuple(r.name for r in self.history if not r.ran)

    @property
    def uses_placeholders(self) -> tuple[str, ...]:
        """Placeholder parameters that actually influenced this run.

        Empty only when every step that ran is governed by paper-stated values.
        """
        active: list[str] = []
        run = set(self.steps_run)
        mapping = {
            "clahe": ("clahe_clip_limit", "clahe_tile_grid"),
            "dilate": ("dilation_kernel_shape", "dilation_kernel_size"),
            "shadow": ("shadow_percentile", "shadow_method", "shadow_gamma"),
            "log_transform": ("log_transform_scale",),
            "band_reduction": ("pca_n_components", "iirs_reference_band"),
            "resample": ("resample_interpolation",),
        }
        for step, names in mapping.items():
            if step in run:
                active.extend(n for n in names if n in PLACEHOLDER_PARAM_NAMES)
        return tuple(dict.fromkeys(active))

    def report(self) -> str:
        lines = [self.config.describe(), ""]
        lines += [str(r) for r in self.history]
        skipped = self.steps_skipped
        if skipped:
            lines += ["", f"{len(skipped)} step(s) did not run: {', '.join(skipped)}"]
        placeholders = self.uses_placeholders
        if placeholders:
            lines += [
                "",
                f"this run depends on {len(placeholders)} placeholder parameter(s) "
                f"not stated in the paper:",
                f"  {', '.join(placeholders)}",
                "-> reproduces the paper's pipeline STRUCTURE, not its parameter values",
            ]
        return "\n".join(lines)


@dataclass
class PreprocessContext:
    """Everything a step might need beyond the pixels themselves.

    All optional. A step whose inputs are absent records itself as skipped with
    a reason rather than guessing.
    """

    src_dataset: Any = None
    ref_dataset: Any = None
    reference_image: np.ndarray | None = None
    src_gsd_m: float | None = None
    ref_gsd_m: float | None = None


def run_pipeline(
    image: np.ndarray,
    config: PreprocessConfig | None = None,
    context: PreprocessContext | None = None,
) -> PreprocessResult:
    """Run the configured steps in the paper's order.

    ``image`` may be 2D or a ``(bands, rows, cols)`` cube; band reduction is the
    step that collapses the latter. Returns a :class:`PreprocessResult`.
    """
    config = config or PreprocessConfig()
    context = context or PreprocessContext()
    current = np.asarray(image)
    history: list[StepRecord] = []

    for step in STEP_ORDER:
        if not getattr(config, step):
            continue
        before = current.shape
        handler = _HANDLERS[step]
        try:
            current, detail, reason = handler(current, config, context)
        except Exception as exc:  # noqa: BLE001 - a failed step is recorded, not fatal
            history.append(StepRecord(step, False, f"{type(exc).__name__}: {exc}", before))
            logger.warning("preprocess step %r failed: %s", step, exc)
            continue

        history.append(
            StepRecord(
                name=step,
                ran=reason is None,
                reason=reason or "",
                shape_before=before,
                shape_after=current.shape,
                dtype_after=str(current.dtype),
                detail=detail,
            )
        )

    return PreprocessResult(image=current, config=config, history=history)


# ---------------------------------------------------------------------------
# Step handlers. Each returns (image, detail, skip_reason_or_None).
# ---------------------------------------------------------------------------


def _step_georeference(image, config, context):
    from lunar_reg.preprocess.georeference import georeference

    result = georeference(image, context.src_dataset, context.ref_dataset)
    if not result.applied:
        return image, {}, result.reason
    return result.image, {"src_crs": result.src_crs, "dst_crs": result.dst_crs}, None


def _step_band_reduction(image, config, context):
    from lunar_reg.preprocess.hyperspectral import reduce_bands

    if image.ndim != 3:
        return image, {}, f"input is {image.ndim}D, not a multi-band cube"
    reduced, detail = reduce_bands(
        image,
        method=config.band_reduction_method,
        n_components=config.pca_n_components,
        band=config.reference_band,
    )
    return reduced, detail, None


def _step_resample(image, config, context):
    from lunar_reg.preprocess.resample import paper_target_gsd, to_common_gsd

    src_gsd = context.src_gsd_m
    target = config.target_gsd_m or paper_target_gsd(
        config.source_sensor, config.reference_sensor
    )
    if src_gsd is None and config.source_sensor:
        from lunar_reg.constants import SENSORS

        spec = SENSORS.get(config.source_sensor)
        src_gsd = spec.gsd_m if spec else None
    if src_gsd is None or target is None:
        return image, {}, (
            "need a source GSD and a target GSD; supply target_gsd_m or a "
            "source/reference sensor pair the paper gives a target for"
        )
    if abs(src_gsd - target) < 1e-9:
        return image, {"src_gsd_m": src_gsd}, "source already at the target GSD"
    return (
        to_common_gsd(image, src_gsd, target),
        {"src_gsd_m": src_gsd, "target_gsd_m": target, "factor": src_gsd / target},
        None,
    )


def _step_normalize(image, config, context):
    from lunar_reg.preprocess.radiometric import to_uint8

    return to_uint8(image), {"target": "8-bit 0-255 (paper 4.1.3)"}, None


def _step_histogram_match(image, config, context):
    from lunar_reg.preprocess.radiometric import match_histogram

    if context.reference_image is None:
        return image, {}, "no reference image supplied to match against"
    return match_histogram(image, context.reference_image), {}, None


def _step_shadow(image, config, context):
    from lunar_reg.preprocess.shadow import estimate_shadow_severity, normalize_shadows

    severity = estimate_shadow_severity(image)
    out = normalize_shadows(
        image,
        method=config.shadow_method,
        percentile=config.shadow_percentile,
        gamma=config.shadow_gamma,
    )
    return out, {"method": config.shadow_method, "shadow_severity": round(severity, 4)}, None


def _step_clahe(image, config, context):
    from lunar_reg.preprocess.radiometric import apply_clahe

    return (
        apply_clahe(image, config.clahe_clip_limit, tuple(config.clahe_tile_grid)),
        {"clip_limit": config.clahe_clip_limit, "tile_grid": tuple(config.clahe_tile_grid)},
        None,
    )


def _step_invert(image, config, context):
    from lunar_reg.preprocess.radiometric import invert

    return invert(image), {"formula": "255 - pixel (paper 4.2.2)"}, None


def _step_dilate(image, config, context):
    from lunar_reg.preprocess.radiometric import dilate

    return (
        dilate(image, config.dilation_kernel_size, config.dilation_kernel_shape),
        {"kernel": f"{config.dilation_kernel_shape}{config.dilation_kernel_size}"},
        None,
    )


def _step_log_transform(image, config, context):
    from lunar_reg.preprocess.radiometric import log_transform

    return log_transform(image), {}, None


_HANDLERS = {
    "georeference": _step_georeference,
    "band_reduction": _step_band_reduction,
    "resample": _step_resample,
    "normalize": _step_normalize,
    "histogram_match": _step_histogram_match,
    "shadow": _step_shadow,
    "clahe": _step_clahe,
    "invert": _step_invert,
    "dilate": _step_dilate,
    "log_transform": _step_log_transform,
}


def run_ablation(
    image: np.ndarray,
    configs,
    context: PreprocessContext | None = None,
) -> list[PreprocessResult]:
    """Run several configurations over the same input, for comparison.

    Pass :func:`lunar_reg.preprocess.config.ablation_configs` output to get a
    leave-one-out sweep. Pair the results with a matcher and the metrics in
    :mod:`lunar_reg.eval` to see what each step actually contributes.
    """
    return [run_pipeline(image, config, context) for config in configs]
