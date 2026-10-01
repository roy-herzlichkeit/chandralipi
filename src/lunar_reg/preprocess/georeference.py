"""Georeferencing: put source and reference into one spatial frame.

Step 4.1.1 of Makharia et al. The paper states the direction and the concrete
projections for its main pair::

    "The OHRC datasets used a Selenographic projection, whereas the LROC NAC
     had a projection of Equirectangular Moon. It was necessary to align the
     geographic projections; therefore, the OHRC datasets' spatial coordinates
     were georeferenced to match LROC NAC."

So: **the source is reprojected onto the reference's CRS**, not the other way
round, and not both onto a third frame.

What this step needs, and often will not have
---------------------------------------------
Real reprojection needs a CRS and a geotransform on both datasets. The PDS4
products this project has opened so far carry neither -- GDAL reports
``NotGeoreferencedWarning`` and returns an identity transform. When that is the
case this step cannot run, and :func:`georeference` says so explicitly rather
than passing the array through as if it had succeeded. A silent no-op here
would make the whole pipeline look like it georeferenced when it did not.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

from lunar_reg.constants import MOON_RADIUS_M
from lunar_reg.preprocess.pipeline import StepStatus
from lunar_reg.provenance import ValueSource

logger = logging.getLogger(__name__)

#: Lunar CRSs as proj4 strings. Built from the IAU mean radius rather than an
#: EPSG code so they work on any PROJ build; this PROJ also carries the
#: ``IAU_2015`` authority, which :func:`lunar_crs` prefers when available.
LUNAR_PROJ4 = {
    "geographic": f"+proj=longlat +R={MOON_RADIUS_M:.1f} +no_defs",
    "equirectangular": f"+proj=eqc +R={MOON_RADIUS_M:.1f} +no_defs",
    "north_polar_stereographic": (
        f"+proj=stere +lat_0=90 +lat_ts=90 +R={MOON_RADIUS_M:.1f} +no_defs"
    ),
    "south_polar_stereographic": (
        f"+proj=stere +lat_0=-90 +lat_ts=-90 +R={MOON_RADIUS_M:.1f} +no_defs"
    ),
}

#: Projection names the paper attributes to each sensor. "Selenographic" is a
#: body-fixed lat/lon frame, i.e. geographic on the lunar sphere.
PAPER_PROJECTION_ALIASES = {
    "selenographic": "geographic",
    "equirectangular moon": "equirectangular",
    "equirectangular": "equirectangular",
}


def lunar_crs(kind: str = "equirectangular"):
    """A :class:`rasterio.crs.CRS` on the lunar sphere.

    ``kind`` accepts the keys of :data:`LUNAR_PROJ4` or the paper's own names
    ("Selenographic", "Equirectangular Moon").
    """
    from rasterio.crs import CRS

    key = PAPER_PROJECTION_ALIASES.get(kind.strip().lower(), kind.strip().lower())
    if key not in LUNAR_PROJ4:
        raise ValueError(f"unknown projection {kind!r}; expected one of {sorted(LUNAR_PROJ4)}")
    return CRS.from_proj4(LUNAR_PROJ4[key])


@dataclass
class GeoreferenceResult:
    """Outcome of a georeferencing attempt.

    ``status`` classifies the outcome (:class:`~lunar_reg.preprocess.pipeline.StepStatus`):
    RAN when reprojected, SKIPPED_MISSING_INPUT when a dataset or its
    georeferencing is absent, NOOP when the CRSs already agree, FAILED when the
    image does not match the source dataset's grid. ``pixel_transform`` maps an
    input pixel centre to an output pixel centre (3x3, only when RAN and both
    transforms are affine); ``pixel_transform_fit_rms_px`` is the RMS residual of
    the affine fit to the CRS-to-CRS mapping over the source grid.

    Provenance (``ValueSource`` values): ``pixel_transform_source`` is
    ``inferred`` for the cross-CRS least-squares fit and ``unknown`` whenever
    ``pixel_transform`` is None; ``pixel_transform_fit_rms_px_source`` is
    ``computed`` when the residual exists and ``unknown`` otherwise.
    """

    image: np.ndarray
    applied: bool
    reason: str = ""
    src_crs: str | None = None
    dst_crs: str | None = None
    status: StepStatus | None = None
    src_transform: Any = None
    dst_transform: Any = None
    pixel_transform: np.ndarray | None = None
    pixel_transform_fit_rms_px: float | None = None
    pixel_transform_source: str | None = None
    pixel_transform_fit_rms_px_source: str | None = None

    def __post_init__(self) -> None:
        if self.status is None:
            self.status = StepStatus.RAN if self.applied else StepStatus.SKIPPED_MISSING_INPUT
        if self.pixel_transform is None:
            self.pixel_transform_source = ValueSource.UNKNOWN.value
        elif self.pixel_transform_source is None:
            self.pixel_transform_source = ValueSource.COMPUTED.value
        if self.pixel_transform_fit_rms_px is None:
            self.pixel_transform_fit_rms_px_source = ValueSource.UNKNOWN.value
        elif self.pixel_transform_fit_rms_px_source is None:
            self.pixel_transform_fit_rms_px_source = ValueSource.COMPUTED.value

    @property
    def skipped(self) -> bool:
        return not self.applied


def is_georeferenced(dataset) -> bool:
    """Whether a dataset carries both a CRS and a non-identity transform."""
    from rasterio.transform import IDENTITY

    return dataset.crs is not None and dataset.transform != IDENTITY


def _affine_matrix(transform) -> np.ndarray:
    """A rasterio ``Affine`` as a 3x3 float64 matrix (pixel corner -> world)."""
    return np.array(
        [
            [transform.a, transform.b, transform.c],
            [transform.d, transform.e, transform.f],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )


def _pixel_transform(
    src_dataset, ref_dataset, n: int = 5
) -> tuple[np.ndarray | None, float | None]:
    """Input pixel centre -> reference-grid pixel centre, as a 3x3 affine.

    Equals ``inv(dst_affine) @ src_affine`` (pixel-centre convention) when both
    datasets share a CRS. Across CRSs the mapping is not affine, so ``C`` in
    ``inv(dst_affine) @ C @ src_affine`` is a least-squares affine fit of the
    CRS transform over an ``n x n`` grid of source pixel centres, and the fit's
    RMS residual (output pixels) is returned with it (Q-P1.09-2). Returns
    ``(None, None)`` when either transform is not an ``Affine`` or too few grid
    points survive the CRS transform.
    """
    from rasterio.transform import Affine
    from rasterio.warp import transform as warp_transform

    if not isinstance(src_dataset.transform, Affine) or not isinstance(
        ref_dataset.transform, Affine
    ):
        return None, None
    cols = np.linspace(0.0, src_dataset.width - 1.0, n)
    rows = np.linspace(0.0, src_dataset.height - 1.0, n)
    xx, yy = (a.ravel() for a in np.meshgrid(cols, rows))
    src_h = np.vstack([xx + 0.5, yy + 0.5, np.ones_like(xx)])
    world = _affine_matrix(src_dataset.transform) @ src_h
    wx, wy = warp_transform(src_dataset.crs, ref_dataset.crs, world[0], world[1])
    dst = np.linalg.inv(_affine_matrix(ref_dataset.transform)) @ np.vstack(
        [np.asarray(wx), np.asarray(wy), np.ones_like(xx)]
    )
    dx, dy = dst[0] - 0.5, dst[1] - 0.5
    ok = np.isfinite(dx) & np.isfinite(dy)
    if ok.sum() < 3:
        return None, None
    design = np.column_stack([xx[ok], yy[ok], np.ones(int(ok.sum()))])
    coef_x, *_ = np.linalg.lstsq(design, dx[ok], rcond=None)
    coef_y, *_ = np.linalg.lstsq(design, dy[ok], rcond=None)
    matrix = np.array([coef_x, coef_y, [0.0, 0.0, 1.0]], dtype=np.float64)
    resid = np.hypot(design @ coef_x - dx[ok], design @ coef_y - dy[ok])
    return matrix, float(np.sqrt(np.mean(resid**2)))


def reproject_valid_mask(valid: np.ndarray, src_dataset, ref_dataset) -> np.ndarray:
    """Move a validity mask (True = real data) from the source grid onto the reference grid.

    Nearest-neighbour on a uint8 copy with fixed nodata semantics (0 = invalid
    on both sides), independent of ``src_dataset.nodata``: a dataset whose
    nodata value is 1 would otherwise turn every True pixel into nodata.
    Reference pixels no source pixel reaches are False. Both datasets must be
    georeferenced; the mask must match the source grid.
    """
    from rasterio.warp import Resampling, reproject

    mask = np.asarray(valid, dtype=bool)
    expected = (src_dataset.height, src_dataset.width)
    if mask.shape != expected:
        raise ValueError(f"valid mask shape {mask.shape} != source grid {expected}")
    destination = np.zeros((ref_dataset.height, ref_dataset.width), dtype=np.uint8)
    reproject(
        source=mask.astype(np.uint8),
        destination=destination,
        src_transform=src_dataset.transform,
        src_crs=src_dataset.crs,
        src_nodata=0,
        dst_transform=ref_dataset.transform,
        dst_crs=ref_dataset.crs,
        dst_nodata=0,
        resampling=Resampling.nearest,
    )
    return destination > 0


def georeference(
    image: np.ndarray,
    src_dataset=None,
    ref_dataset=None,
    resampling: str = "cubic",
) -> GeoreferenceResult:
    """Reproject ``image`` from its dataset's CRS onto the reference's grid.

    Returns a :class:`GeoreferenceResult` whose ``applied`` flag says whether
    anything actually happened and whose ``status`` classifies why not. When
    either dataset lacks georeferencing the array comes back untouched with
    ``applied=False`` and a ``reason`` -- the caller must not treat that as a
    successful georeference.

    When it runs, the output lies on the reference grid (``ref.transform``,
    ``ref.crs``, shape ``(ref.height, ref.width)``) as float32; pixels no source
    pixel reaches are NaN. Source pixels equal to ``src_dataset.nodata`` (0 when
    the dataset declares none) are treated as nodata.
    """
    if src_dataset is None or ref_dataset is None:
        return GeoreferenceResult(
            image,
            False,
            "no source and/or reference dataset supplied; georeferencing needs both",
            status=StepStatus.SKIPPED_MISSING_INPUT,
        )

    if not is_georeferenced(src_dataset):
        return GeoreferenceResult(
            image,
            False,
            "source has no CRS/geotransform (PDS4 products commonly carry neither); "
            "reprojection impossible -- downstream steps still run, but the pair is "
            "NOT in a common spatial frame",
            status=StepStatus.SKIPPED_MISSING_INPUT,
        )
    if not is_georeferenced(ref_dataset):
        return GeoreferenceResult(
            image,
            False,
            "reference has no CRS/geotransform; reprojection impossible",
            status=StepStatus.SKIPPED_MISSING_INPUT,
        )

    if src_dataset.crs == ref_dataset.crs:
        return GeoreferenceResult(
            image,
            False,
            "source and reference already share a CRS; nothing to do",
            src_crs=str(src_dataset.crs),
            dst_crs=str(ref_dataset.crs),
            status=StepStatus.NOOP,
            src_transform=src_dataset.transform,
            dst_transform=ref_dataset.transform,
        )

    image = np.asarray(image)
    expected = (src_dataset.height, src_dataset.width)
    if tuple(image.shape[-2:]) != expected:
        return GeoreferenceResult(
            image,
            False,
            f"image shape {tuple(image.shape)} does not match the source dataset grid "
            f"(height, width) = {expected}",
            src_crs=str(src_dataset.crs),
            dst_crs=str(ref_dataset.crs),
            status=StepStatus.FAILED,
            src_transform=src_dataset.transform,
            dst_transform=ref_dataset.transform,
        )

    from rasterio.warp import Resampling, reproject

    height, width = ref_dataset.height, ref_dataset.width
    dst_shape = (*image.shape[:-2], height, width)
    destination = np.full(dst_shape, np.nan, dtype=np.float32)
    src_nodata = 0 if src_dataset.nodata is None else src_dataset.nodata
    reproject(
        source=image,
        destination=destination,
        src_transform=src_dataset.transform,
        src_crs=src_dataset.crs,
        src_nodata=src_nodata,
        dst_transform=ref_dataset.transform,
        dst_crs=ref_dataset.crs,
        dst_nodata=np.nan,
        resampling=getattr(Resampling, resampling, Resampling.cubic),
    )
    matrix, fit_rms = _pixel_transform(src_dataset, ref_dataset)
    logger.info(
        "georeferenced %s -> %s (%dx%d -> %dx%d)",
        src_dataset.crs,
        ref_dataset.crs,
        src_dataset.height,
        src_dataset.width,
        height,
        width,
    )
    return GeoreferenceResult(
        destination,
        True,
        "reprojected onto the reference grid",
        src_crs=str(src_dataset.crs),
        dst_crs=str(ref_dataset.crs),
        status=StepStatus.RAN,
        src_transform=src_dataset.transform,
        dst_transform=ref_dataset.transform,
        pixel_transform=matrix,
        pixel_transform_fit_rms_px=fit_rms,
        # A least-squares fit of a non-affine CRS mapping (Q-P1.09-2 a): INFERRED.
        pixel_transform_source=ValueSource.INFERRED.value if matrix is not None else None,
    )
