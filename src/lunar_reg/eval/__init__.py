"""Evaluation metrics: accuracy, robustness, and spatial distribution."""

from lunar_reg.eval.conditioning import (
    EXTRAPOLATION_GATE_PX,
    ConditioningMetrics,
    bootstrap_conditioning,
    conditioning_map,
)
from lunar_reg.eval.error_budget import (
    ErrorBudget,
    attribute_error,
    preprocessing_sweep,
    transform_rms_px,
)
from lunar_reg.eval.metrics import (
    RegistrationMetrics,
    compute_metrics,
    residuals,
    rmse,
)
from lunar_reg.eval.uniformity import (
    PROFILE_GRIDS,
    UNIFORMITY_GATE,
    UniformityMetrics,
    cell_counts,
    clark_evans_index,
    compute_uniformity,
    enforce_uniformity,
    uniformity_profile,
)

__all__ = [
    "EXTRAPOLATION_GATE_PX",
    "PROFILE_GRIDS",
    "UNIFORMITY_GATE",
    "ConditioningMetrics",
    "ErrorBudget",
    "RegistrationMetrics",
    "UniformityMetrics",
    "attribute_error",
    "bootstrap_conditioning",
    "cell_counts",
    "clark_evans_index",
    "compute_metrics",
    "compute_uniformity",
    "conditioning_map",
    "enforce_uniformity",
    "preprocessing_sweep",
    "residuals",
    "rmse",
    "transform_rms_px",
    "uniformity_profile",
]
