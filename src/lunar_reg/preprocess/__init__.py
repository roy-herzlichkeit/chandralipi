"""Preprocessing: the Makharia et al. (arXiv:2509.04775) pipeline, ablatable.

Core steps (paper 4.1): georeferencing, resolution resampling, intensity
normalisation. Specialised steps (paper 4.2) differ per sensor pair -- CLAHE,
inversion and dilation for OHRC/NAC; histogram matching, shadow normalisation
and log transform for IIRS/WAC.

The paper's full text was read for this package. It specifies the structure and
a few exact values; most numeric parameters are not stated and the defaults here
are ours. See :mod:`lunar_reg.preprocess.params` and check
``PreprocessResult.uses_placeholders`` before calling a run paper-matched.
"""

from lunar_reg.preprocess.config import (
    STEP_ORDER,
    PreprocessConfig,
    ablation_configs,
    iirs_wac_config,
    minimal_config,
    ohrc_nac_config,
)
from lunar_reg.preprocess.georeference import GeoreferenceResult, georeference, lunar_crs
from lunar_reg.preprocess.hyperspectral import (
    iirs_to_panchromatic,
    incremental_band_pca,
    reduce_bands,
    select_bands,
    select_reference_band,
)
from lunar_reg.preprocess.params import (
    ALL_PARAMS,
    PLACEHOLDER_PARAM_NAMES,
    Param,
    ParamSource,
    provenance_report,
)
from lunar_reg.preprocess.pipeline import (
    PreprocessContext,
    PreprocessResult,
    StepRecord,
    run_ablation,
    run_pipeline,
)
from lunar_reg.preprocess.radiometric import (
    apply_clahe,
    dilate,
    invert,
    log_transform,
    match_histogram,
    normalize_intensity,
    standard_chain,
    suppress_shadows,
    to_uint8,
)
from lunar_reg.preprocess.resample import match_scale, paper_target_gsd, to_common_gsd
from lunar_reg.preprocess.shadow import (
    estimate_shadow_severity,
    normalize_shadows,
    shadow_fraction,
    shadow_mask,
)

__all__ = [
    "ALL_PARAMS",
    "PLACEHOLDER_PARAM_NAMES",
    "STEP_ORDER",
    "GeoreferenceResult",
    "Param",
    "ParamSource",
    "PreprocessConfig",
    "PreprocessContext",
    "PreprocessResult",
    "StepRecord",
    "ablation_configs",
    "apply_clahe",
    "dilate",
    "estimate_shadow_severity",
    "georeference",
    "iirs_to_panchromatic",
    "iirs_wac_config",
    "incremental_band_pca",
    "invert",
    "log_transform",
    "lunar_crs",
    "match_histogram",
    "match_scale",
    "minimal_config",
    "normalize_intensity",
    "normalize_shadows",
    "ohrc_nac_config",
    "paper_target_gsd",
    "provenance_report",
    "reduce_bands",
    "run_ablation",
    "run_pipeline",
    "select_bands",
    "select_reference_band",
    "shadow_fraction",
    "shadow_mask",
    "standard_chain",
    "suppress_shadows",
    "to_common_gsd",
    "to_uint8",
]
