"""The Makharia et al. preprocessing pipeline, step by step and fully ablatable.

Reproduces the structure in arXiv:2509.04775 section 4:

* **4.1 core** -- georeferencing, resolution resampling, intensity normalisation
* **4.2 specialised** -- per sensor pair; see
  :mod:`lunar_reg.preprocess.config` for the two tracks

Every step is toggleable and every run returns a :class:`PreprocessResult`
carrying a :class:`StepRecord` per step: a classified :class:`StepStatus`
(ran, skipped for a missing input, no-op, failed, degenerate output), the
reason when it did not run, and how the image changed. A step that could not run
(georeferencing without a CRS, histogram matching without a reference) is
recorded with a reason -- never silently passed over, because a chain that
quietly dropped half its steps looks identical to one that ran fully.

Geometric steps (georeference, resample) also report a 3x3 pixel transform;
``PreprocessResult.pixel_transform`` composes them so a transform found on the
preprocessed images can be mapped back to input pixels
(Phase_1/LLD/preprocess_geometry.md §2).

Parameter provenance
--------------------
The paper specifies this structure precisely but states few numeric values.
Anything not stated is a placeholder chosen here. ``result.uses_placeholders``
and :func:`lunar_reg.preprocess.params.provenance_report` make that explicit;
do not describe a run as using the paper's parameters without checking.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any

import numpy as np

from lunar_reg.preprocess.config import STEP_ORDER, PreprocessConfig
from lunar_reg.preprocess.params import PARAMS_BY_NAME, PLACEHOLDER_PARAM_NAMES
from lunar_reg.provenance import ValueSource

logger = logging.getLogger(__name__)


class StepStatus(str, Enum):
    """Classified outcome of one pipeline step (Phase_1/LLD/preprocess_geometry.md §1)."""

    RAN = "ran"
    SKIPPED_MISSING_INPUT = "skipped_missing_input"
    NOOP = "noop"  # e.g. already at target GSD, CRSs already equal
    FAILED = "failed"  # handler raised; reason = "<ExcType>: <msg>"
    DEGENERATE_OUTPUT = "degenerate_output"  # no finite non-zero valid pixel, or a zero-size axis

    @property
    def is_failure(self) -> bool:
        return self in (StepStatus.FAILED, StepStatus.DEGENERATE_OUTPUT)


#: Steps that move pixels and therefore contribute to ``PreprocessResult.pixel_transform``.
GEOMETRIC_STEPS: tuple[str, ...] = ("georeference", "resample")

#: Provenance of a composed pixel transform is that of its weakest factor, in
#: this order (weakest first).
_TRANSFORM_SOURCE_ORDER: tuple[ValueSource, ...] = (
    ValueSource.UNKNOWN,
    ValueSource.INFERRED,
    ValueSource.COMPUTED,
)

#: Steps that must receive a 2-D image: everything after band reduction.
_NEEDS_2D: frozenset[str] = frozenset(STEP_ORDER[STEP_ORDER.index("band_reduction") + 1 :])


@dataclass
class StepRecord:
    """What one pipeline step did."""

    name: str
    status: StepStatus
    reason: str = ""
    shape_before: tuple[int, ...] | None = None
    shape_after: tuple[int, ...] | None = None
    dtype_after: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def ran(self) -> bool:
        return self.status is StepStatus.RAN

    @property
    def changed_shape(self) -> bool:
        return self.ran and self.shape_before != self.shape_after

    def __str__(self) -> str:
        if not self.ran:
            return f"  {self.name:16s} {self.status.value.upper()}  {self.reason}"
        shape = (
            f"{self.shape_before} -> {self.shape_after}"
            if self.changed_shape
            else str(self.shape_after)
        )
        extra = f"  {self.detail}" if self.detail else ""
        return f"  {self.name:16s} ok       {shape} {self.dtype_after}{extra}"


#: Per step: the PLACEHOLDER params it consumes and the config attribute holding
#: each value (None when the step always uses the params-module value).
_STEP_PARAMS: dict[str, tuple[tuple[str, str | None], ...]] = {
    "clahe": (("clahe_clip_limit", "clahe_clip_limit"), ("clahe_tile_grid", "clahe_tile_grid")),
    "dilate": (
        ("dilation_kernel_shape", "dilation_kernel_shape"),
        ("dilation_kernel_size", "dilation_kernel_size"),
    ),
    "shadow": (
        ("shadow_percentile", "shadow_percentile"),
        ("shadow_method", "shadow_method"),
        ("shadow_gamma", "shadow_gamma"),
    ),
    "log_transform": (("log_transform_scale", None),),
    "band_reduction": (
        ("pca_n_components", "pca_n_components"),
        ("iirs_reference_band", "reference_band"),
    ),
    "resample": (("resample_interpolation", None),),
}


def _same_value(a: Any, b: Any) -> bool:
    if isinstance(a, (list, tuple)) or isinstance(b, (list, tuple)):
        try:
            return tuple(a) == tuple(b)
        except TypeError:
            return False
    return a == b


@dataclass
class PreprocessResult:
    """A preprocessed image plus the full record of how it got that way.

    ``pixel_transform`` (3x3 float64) maps an input pixel centre ``(x, y)`` to
    the output pixel centre ``(x', y')``: the product of every geometric step
    that ran, identity when none did. NaN-filled, with ``pixel_transform_source``
    = ``unknown``, when a geometric step ran but could not report its matrix.
    ``pixel_transform_source`` is the weakest ``ValueSource`` over the composed
    steps: ``computed`` for resampling alone, ``inferred`` once the cross-CRS
    georeference fit is part of it.
    """

    image: np.ndarray
    config: PreprocessConfig
    history: list[StepRecord] = field(default_factory=list)
    pixel_transform: np.ndarray = field(default_factory=lambda: np.eye(3, dtype=np.float64))
    pixel_transform_source: str = ValueSource.COMPUTED.value

    @property
    def steps_run(self) -> tuple[str, ...]:
        return tuple(r.name for r in self.history if r.ran)

    @property
    def steps_skipped(self) -> tuple[str, ...]:
        return tuple(r.name for r in self.history if not r.ran)

    @property
    def status_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self.history:
            counts[r.status.value] = counts.get(r.status.value, 0) + 1
        return counts

    @property
    def failed(self) -> bool:
        """Whether any step FAILED or produced a DEGENERATE_OUTPUT."""
        return any(r.status.is_failure for r in self.history)

    @property
    def uses_placeholders(self) -> tuple[str, ...]:
        """Placeholder parameters that actually influenced this run.

        A name is listed when its step RAN and the config's value equals the
        placeholder's value in :data:`~lunar_reg.preprocess.params.PARAMS_BY_NAME`.
        Empty only when every step that ran is governed by paper-stated (or
        caller-overridden) values.
        """
        active: list[str] = []
        run = set(self.steps_run)
        for step, names in _STEP_PARAMS.items():
            if step not in run:
                continue
            for name, attr in names:
                if name not in PLACEHOLDER_PARAM_NAMES:
                    continue
                param = PARAMS_BY_NAME[name]
                if attr is None or _same_value(getattr(self.config, attr), param.value):
                    active.append(name)
        return tuple(dict.fromkeys(active))

    def report(self) -> str:
        lines = [self.config.describe(), ""]
        lines += [str(r) for r in self.history]
        counts = self.status_counts
        if counts:
            lines += [
                "",
                "step outcomes: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())),
            ]
        skipped = self.steps_skipped
        if skipped:
            lines += [f"{len(skipped)} step(s) did not run: {', '.join(skipped)}"]
        if self.failed:
            first = next(r for r in self.history if r.status.is_failure)
            lines += [
                f"PREPROCESSING FAILED: first {first.status.value} step "
                f"{first.name!r}: {first.reason}"
            ]
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

    All optional. A step whose inputs are absent records itself as
    SKIPPED_MISSING_INPUT with a reason rather than guessing. ``valid`` is the
    nodata mask of the image (True = real data) and ``reference_valid`` that of
    ``reference_image``; :func:`run_pipeline` works on a copy of the context, so
    a geometric step that resamples ``valid`` never changes the caller's object.
    """

    src_dataset: Any = None
    ref_dataset: Any = None
    reference_image: np.ndarray | None = None
    src_gsd_m: float | None = None
    ref_gsd_m: float | None = None
    valid: np.ndarray | None = None
    reference_valid: np.ndarray | None = None


def _degeneracy(image: np.ndarray, valid: np.ndarray | None) -> str | None:
    """Why ``image`` is degenerate, or None when it has a usable pixel."""
    arr = np.asarray(image)
    if arr.size == 0:
        return f"output has a zero-size axis {arr.shape}"
    usable = arr != 0
    if np.issubdtype(arr.dtype, np.inexact):
        usable &= np.isfinite(arr)
    if valid is not None and np.shape(valid) == arr.shape[-2:]:
        usable &= np.asarray(valid, dtype=bool)
    if not usable.any():
        return "output has no finite, non-zero valid pixel"
    return None


def run_pipeline(
    image: np.ndarray,
    config: PreprocessConfig | None = None,
    context: PreprocessContext | None = None,
) -> PreprocessResult:
    """Run the configured steps in the paper's order.

    ``image`` may be 2D or a ``(bands, rows, cols)`` cube; band reduction is the
    step that collapses the latter. Never raises for a bad step: a handler that
    raises is recorded as FAILED, a RAN step whose output is empty as
    DEGENERATE_OUTPUT, and any later step still runs. Returns a
    :class:`PreprocessResult`.
    """
    config = config or PreprocessConfig()
    # A copy: steps may store a resampled ``valid`` back into the context.
    context = replace(context) if context is not None else PreprocessContext()
    current = np.asarray(image)
    history: list[StepRecord] = []
    pixel_transform = np.eye(3, dtype=np.float64)
    transform_source = ValueSource.COMPUTED

    for step in STEP_ORDER:
        if not getattr(config, step):
            continue
        before = current.shape
        if step in _NEEDS_2D and current.ndim != 2:
            history.append(
                StepRecord(
                    step,
                    StepStatus.FAILED,
                    f"input is {current.ndim}-D after band_reduction",
                    before,
                )
            )
            continue
        handler = _HANDLERS[step]
        try:
            out, detail, status, reason = handler(current, config, context)
        except Exception as exc:  # noqa: BLE001 - any handler may raise; recorded as FAILED, not fatal
            history.append(
                StepRecord(step, StepStatus.FAILED, f"{type(exc).__name__}: {exc}", before)
            )
            continue

        out = np.asarray(out)
        if status is StepStatus.RAN:
            why = _degeneracy(out, context.valid)
            if why is not None:
                status, reason = StepStatus.DEGENERATE_OUTPUT, why
        if step in GEOMETRIC_STEPS and status in (StepStatus.RAN, StepStatus.DEGENERATE_OUTPUT):
            matrix = detail.get("pixel_transform")
            if matrix is None:
                pixel_transform = np.full((3, 3), np.nan)
                step_source = ValueSource.UNKNOWN
            else:
                pixel_transform = np.asarray(matrix, dtype=np.float64) @ pixel_transform
                step_source = ValueSource(
                    detail.get("pixel_transform_source", ValueSource.COMPUTED.value)
                )
            transform_source = min(transform_source, step_source, key=_TRANSFORM_SOURCE_ORDER.index)
        current = out
        history.append(
            StepRecord(
                name=step,
                status=status,
                reason=reason or "",
                shape_before=before,
                shape_after=current.shape,
                dtype_after=str(current.dtype),
                detail=detail,
            )
        )

    result = PreprocessResult(
        image=current,
        config=config,
        history=history,
        pixel_transform=pixel_transform,
        pixel_transform_source=transform_source.value,
    )
    if result.failed:
        first = next(r for r in history if r.status.is_failure)
        logger.warning(
            "preprocess %r: %s; first %s: %s: %s",
            config.label,
            result.status_counts,
            first.status.value,
            first.name,
            first.reason,
        )
    else:
        logger.debug("preprocess %r: %s", config.label, result.status_counts)
    return result


# ---------------------------------------------------------------------------
# Step handlers. Each returns (image, detail, status, reason); reason is "" or
# None when the step RAN.
# ---------------------------------------------------------------------------


def _step_georeference(image, config, context):
    from lunar_reg.preprocess.georeference import georeference, reproject_valid_mask

    result = georeference(image, context.src_dataset, context.ref_dataset)
    detail: dict[str, Any] = {}
    if result.src_crs is not None:
        detail.update(src_crs=result.src_crs, dst_crs=result.dst_crs)
    if result.status is not StepStatus.RAN:
        return image, detail, result.status, result.reason
    if context.valid is not None and np.shape(context.valid) != image.shape[-2:]:
        raise ValueError(
            f"context.valid shape {np.shape(context.valid)} != image grid {image.shape[-2:]}"
        )
    if result.pixel_transform is not None:
        detail["pixel_transform"] = result.pixel_transform.tolist()
    detail["pixel_transform_source"] = result.pixel_transform_source
    detail["pixel_transform_fit_rms_px"] = result.pixel_transform_fit_rms_px
    detail["pixel_transform_fit_rms_px_source"] = result.pixel_transform_fit_rms_px_source
    # Reference pixels no source pixel reaches (and source nodata) are NaN in the
    # output; they must be invalid for every later masked step, or normalize/CLAHE
    # turn them into ordinary-looking data.
    out = result.image
    finite = np.isfinite(out) if out.ndim == 2 else np.isfinite(out).all(axis=0)
    if context.valid is not None:
        # The mask follows the pixels onto the reference grid (Q-P1.09-2 c).
        moved = reproject_valid_mask(context.valid, context.src_dataset, context.ref_dataset)
        context.valid = moved & finite
    elif not finite.all():
        context.valid = finite
    return out, detail, StepStatus.RAN, None


def _step_band_reduction(image, config, context):
    from lunar_reg.preprocess.hyperspectral import reduce_bands

    if image.ndim == 2:
        return image, {}, StepStatus.NOOP, "input is 2D, not a multi-band cube"
    if image.ndim != 3:
        return image, {}, StepStatus.FAILED, f"input is {image.ndim}-D; expected 2-D or 3-D"
    reduced, detail = reduce_bands(
        image,
        method=config.band_reduction_method,
        n_components=config.pca_n_components,
        band=config.reference_band,
    )
    return reduced, detail, StepStatus.RAN, None


def _step_resample(image, config, context):
    from lunar_reg.constants import SENSORS
    from lunar_reg.preprocess.resample import (
        paper_target_gsd,
        resample_mask,
        resample_pixel_transform,
        to_common_gsd,
    )

    side = config.side
    if side == "source":
        gsd, sensor, attr = context.src_gsd_m, config.source_sensor, "src_gsd_m"
    elif side == "reference":
        gsd, sensor, attr = context.ref_gsd_m, config.reference_sensor, "ref_gsd_m"
    else:
        raise ValueError(f"config.side must be 'source' or 'reference', got {side!r}")
    target = config.target_gsd_m or paper_target_gsd(config.source_sensor, config.reference_sensor)
    detail: dict[str, Any] = {"side": side, "gsd_source": "context"}
    nominal_spec = None
    if gsd is None and sensor:
        nominal_spec = SENSORS.get(sensor)
        if nominal_spec is not None:
            gsd = nominal_spec.gsd_m
            detail["gsd_source"] = "nominal"
            detail["nominal_gsd_value_source"] = nominal_spec.gsd_source.value
    if gsd is None or target is None:
        return (
            image,
            {"side": side},
            StepStatus.SKIPPED_MISSING_INPUT,
            (
                f"need a {side} GSD (context.{attr} or a nominal sensor GSD) and a target "
                "GSD; supply target_gsd_m or a source/reference sensor pair the paper "
                "gives a target for"
            ),
        )
    if nominal_spec is not None:
        logger.warning(
            "resample (%s side): context.%s is None; using the %s nominal GSD %s m (%s)",
            side,
            attr,
            sensor,
            gsd,
            nominal_spec.gsd_note,
        )
    detail["src_gsd_m"] = gsd
    if abs(gsd - target) < 1e-9:
        return image, detail, StepStatus.NOOP, f"{side} already at the target GSD"
    if context.valid is not None and np.shape(context.valid) != image.shape:
        raise ValueError(
            f"context.valid shape {np.shape(context.valid)} != image shape {image.shape}"
        )
    out = to_common_gsd(image, gsd, target)
    detail.update(
        target_gsd_m=target,
        factor=gsd / target,
        pixel_transform=resample_pixel_transform(image.shape, out.shape).tolist(),
        pixel_transform_source=ValueSource.COMPUTED.value,
    )
    if context.valid is not None:
        context.valid = resample_mask(context.valid, out.shape)
    return out, detail, StepStatus.RAN, None


def _step_normalize(image, config, context):
    from lunar_reg.preprocess.radiometric import to_uint8

    return (
        to_uint8(image, valid=context.valid),
        {"target": "8-bit 0-255 (paper 4.1.3)"},
        StepStatus.RAN,
        None,
    )


def _step_histogram_match(image, config, context):
    from lunar_reg.preprocess.radiometric import match_histogram

    if context.reference_image is None:
        return (
            image,
            {},
            StepStatus.SKIPPED_MISSING_INPUT,
            "no reference image supplied to match against",
        )
    out = match_histogram(
        image,
        context.reference_image,
        valid=context.valid,
        reference_valid=context.reference_valid,
    )
    return out, {}, StepStatus.RAN, None


def _step_shadow(image, config, context):
    from lunar_reg.preprocess.shadow import estimate_shadow_severity, normalize_shadows

    severity = estimate_shadow_severity(image, valid=context.valid)
    out = normalize_shadows(
        image,
        method=config.shadow_method,
        percentile=config.shadow_percentile,
        gamma=config.shadow_gamma,
        valid=context.valid,
    )
    return (
        out,
        {"method": config.shadow_method, "shadow_severity": round(severity, 4)},
        StepStatus.RAN,
        None,
    )


def _step_clahe(image, config, context):
    from lunar_reg.preprocess.radiometric import apply_clahe

    return (
        apply_clahe(
            image, config.clahe_clip_limit, tuple(config.clahe_tile_grid), valid=context.valid
        ),
        {"clip_limit": config.clahe_clip_limit, "tile_grid": tuple(config.clahe_tile_grid)},
        StepStatus.RAN,
        None,
    )


def _step_invert(image, config, context):
    from lunar_reg.preprocess.radiometric import invert

    return (
        invert(image, valid=context.valid),
        {"formula": "255 - pixel (paper 4.2.2)"},
        StepStatus.RAN,
        None,
    )


def _step_dilate(image, config, context):
    from lunar_reg.preprocess.radiometric import dilate

    return (
        dilate(
            image, config.dilation_kernel_size, config.dilation_kernel_shape, valid=context.valid
        ),
        {"kernel": f"{config.dilation_kernel_shape}{config.dilation_kernel_size}"},
        StepStatus.RAN,
        None,
    )


def _step_log_transform(image, config, context):
    from lunar_reg.preprocess.radiometric import log_transform

    return log_transform(image, valid=context.valid), {}, StepStatus.RAN, None


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
