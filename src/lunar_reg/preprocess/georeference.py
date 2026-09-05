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

import numpy as np

from lunar_reg.constants import MOON_RADIUS_M

logger = logging.getLogger(__name__)

#: Lunar CRSs as proj4 strings. Built from the IAU mean radius rather than an
#: EPSG code so they work on any PROJ build; this PROJ also carries the
#: ``IAU_2015`` authority, which :func:`lunar_crs` prefers when available.
LUNAR_PROJ4 = {
    "geographic": f"+proj=longlat +R={MOON_RADIUS_M:.1f} +no_defs",
    "equirectangular": f"+proj=eqc +R={MOON_RADIUS_M:.1f} +no_defs",
    "north_polar_stereographic":
        f"+proj=stere +lat_0=90 +lat_ts=90 +R={MOON_RADIUS_M:.1f} +no_defs",
    "south_polar_stereographic":
        f"+proj=stere +lat_0=-90 +lat_ts=-90 +R={MOON_RADIUS_M:.1f} +no_defs",
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
    """Outcome of a georeferencing attempt."""

    image: np.ndarray
    applied: bool
    reason: str = ""
    src_crs: str | None = None
    dst_crs: str | None = None

    @property
    def skipped(self) -> bool:
        return not self.applied


def is_georeferenced(dataset) -> bool:
    """Whether a dataset carries both a CRS and a non-identity transform."""
    from rasterio.transform import IDENTITY

    return dataset.crs is not None and dataset.transform != IDENTITY


def georeference(
    image: np.ndarray,
    src_dataset=None,
    ref_dataset=None,
    resampling: str = "cubic",
) -> GeoreferenceResult:
    """Reproject ``image`` from its dataset's CRS onto the reference's CRS.

    Returns a :class:`GeoreferenceResult` whose ``applied`` flag says whether
    anything actually happened. When either dataset lacks georeferencing the
    array comes back untouched with ``applied=False`` and a ``reason`` -- the
    caller must not treat that as a successful georeference.
    """
    if src_dataset is None or ref_dataset is None:
        return GeoreferenceResult(
            image, False,
            "no source and/or reference dataset supplied; georeferencing needs both",
        )

    if not is_georeferenced(src_dataset):
        return GeoreferenceResult(
            image, False,
            "source has no CRS/geotransform (PDS4 products commonly carry neither); "
            "reprojection impossible -- downstream steps still run, but the pair is "
            "NOT in a common spatial frame",
        )
    if not is_georeferenced(ref_dataset):
        return GeoreferenceResult(
            image, False, "reference has no CRS/geotransform; reprojection impossible"
        )

    if src_dataset.crs == ref_dataset.crs:
        return GeoreferenceResult(
            image, False, "source and reference already share a CRS; nothing to do",
            src_crs=str(src_dataset.crs), dst_crs=str(ref_dataset.crs),
        )

    from rasterio.warp import Resampling, calculate_default_transform, reproject

    transform, width, height = calculate_default_transform(
        src_dataset.crs, ref_dataset.crs,
        src_dataset.width, src_dataset.height, *src_dataset.bounds,
    )
    destination = np.zeros((height, width), dtype=image.dtype)
    reproject(
        source=image,
        destination=destination,
        src_transform=src_dataset.transform,
        src_crs=src_dataset.crs,
        dst_transform=transform,
        dst_crs=ref_dataset.crs,
        resampling=getattr(Resampling, resampling, Resampling.cubic),
    )
    logger.info(
        "georeferenced %s -> %s (%dx%d -> %dx%d)",
        src_dataset.crs, ref_dataset.crs,
        src_dataset.height, src_dataset.width, height, width,
    )
    return GeoreferenceResult(
        destination, True, "reprojected onto the reference CRS",
        src_crs=str(src_dataset.crs), dst_crs=str(ref_dataset.crs),
    )
