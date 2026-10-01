"""Sun geometry for an image: SPICE first, ODE and a DTM fit as cross-checks (C13, G14).

Where the Sun stood when a frame was taken decides which slopes are lit and
which fall into shadow, so two images of the same ground under different suns
look different. Three independent sources give that geometry here:

``sun_from_spice`` (primary)
    The Sun's position in the Moon's body-fixed frame (``IAU_MOON``) at the
    image time, from the NAIF *generic* kernels only (leap seconds, planetary
    constants, DE440s ephemeris). Illumination at a ground point depends only on
    where the Sun and Moon are and how the Moon is oriented, so no spacecraft
    kernel is needed. Azimuth clockwise from north, ``ValueSource.COMPUTED``.
``sun_from_ode_metadata`` (cross-check A)
    ODE's per-product ``Incidence_angle`` gives the elevation
    (``90 - incidence``, ``DOCUMENTED``); ODE has no azimuth.
``fit_sun_azimuth`` (cross-check B)
    A Lambertian hillshade of a terrain model (:func:`lambert_shade`) is
    correlated with the image for every azimuth; the best-correlated azimuth is
    an inferred estimate in the *grid* frame (clockwise from image-up).
    :func:`north_to_grid_azimuth` converts the SPICE value to that frame.

ISRO's OHRC labels carry ``sun_azimuth``/``sun_elevation``
(:func:`sun_from_label`), but no file we hold documents the azimuth's reference
direction, so their frame is ``"label_unverified"``.

``spiceypy`` is an optional extra (``pip install -e ".[spice]"``) imported only
inside :func:`sun_from_spice`.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from lunar_reg.constants import MOON_RADIUS_M
from lunar_reg.provenance import ValueSource

logger = logging.getLogger(__name__)

#: The three NAIF generic kernels :func:`sun_from_spice` loads (LSK, PCK, DE SPK).
SPICE_KERNELS: tuple[str, ...] = ("naif0012.tls", "pck00011.tpc", "de440s.bsp")

#: Sphere radius (km) of the surface point handed to SPICE; ``constants.MOON_RADIUS_M``
#: (IAU mean radius, the sphere every PDS product here uses).
SURFACE_RADIUS_KM: float = MOON_RADIUS_M / 1000.0
SURFACE_RADIUS_KM_SOURCE = ValueSource.DOCUMENTED

#: ``fit_sun_azimuth``: the second peak is the best NCC at least this far (circular
#: degrees) from the peak (Phase_1/LLD/sun_geometry.md §1).
SECOND_PEAK_MIN_SEPARATION_DEG: float = 20.0
SECOND_PEAK_MIN_SEPARATION_DEG_SOURCE = ValueSource.INFERRED

#: Latitude step (degrees) used to find grid north numerically.
_NORTH_STEP_DEG = 1e-4

#: Kernel paths already passed to ``furnsh`` in this process.
_LOADED_KERNELS: set[str] = set()

FRAME_NORTH = "north_clockwise"
FRAME_GRID = "grid_up_clockwise"
FRAME_LABEL = "label_unverified"


@dataclass(frozen=True)
class SunGeometry:
    azimuth_deg: float | None
    elevation_deg: float | None
    azimuth_source: ValueSource
    elevation_source: ValueSource
    azimuth_frame: str  # "north_clockwise" | "grid_up_clockwise" | "label_unverified"
    note: str = ""

    def as_tuple(self) -> tuple[float, float] | None:
        """``(azimuth, elevation)`` when both are known, else None."""
        if self.azimuth_deg is None or self.elevation_deg is None:
            return None
        return (float(self.azimuth_deg), float(self.elevation_deg))

    def as_dict(self) -> dict:
        return {
            "azimuth_deg": None if self.azimuth_deg is None else float(self.azimuth_deg),
            "elevation_deg": None if self.elevation_deg is None else float(self.elevation_deg),
            "azimuth_source": self.azimuth_source.value,
            "elevation_source": self.elevation_source.value,
            "azimuth_frame": self.azimuth_frame,
            "note": self.note,
        }


@dataclass
class AzimuthFit:
    """Hillshade-vs-image correlation over azimuth (grid frame; :data:`AZIMUTH_FIT_SOURCE`)."""

    azimuth_deg: float
    ncc_peak: float
    azimuths: np.ndarray
    ncc: np.ndarray
    second_peak_deg: float
    second_peak_ncc: float
    peak_margin: float
    n_valid_px: int


#: Provenance of every :class:`AzimuthFit` number: a fit, not a measurement (G14).
AZIMUTH_FIT_SOURCE = ValueSource.INFERRED


# ---------------------------------------------------------------------------
# Hillshade and azimuth fit (cross-check B)
# ---------------------------------------------------------------------------


def _slope_aspect(dtm: np.ndarray, posting_m: float) -> tuple[np.ndarray, np.ndarray]:
    """Slope and aspect (radians); aspect clockwise from image-up, rows run southward."""
    gy, gx = np.gradient(np.asarray(dtm, dtype=np.float64), float(posting_m))
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    return slope, aspect


def _shade(
    slope: np.ndarray, aspect: np.ndarray, azimuth_deg: float, elevation_deg: float
) -> np.ndarray:
    az = math.radians(float(azimuth_deg))
    el = math.radians(float(elevation_deg))
    shade = math.sin(el) * np.cos(slope) + math.cos(el) * np.sin(slope) * np.cos(az - aspect)
    return np.clip(shade, 0.0, 1.0)


def lambert_shade(dtm, posting_m, azimuth_deg, elevation_deg) -> np.ndarray:
    """Lambertian brightness of ``dtm`` under a sun at (azimuth, elevation), float32 in [0, 1].

    ``azimuth_deg`` is clockwise from image-up (rows increase southward, columns
    eastward). No cast shadows. NaN where ``dtm`` is not finite (and where the
    gradient touches such a cell).
    """
    dtm = np.asarray(dtm, dtype=np.float64)
    slope, aspect = _slope_aspect(dtm, posting_m)
    shade = _shade(slope, aspect, azimuth_deg, elevation_deg)
    shade[~np.isfinite(dtm)] = np.nan
    return shade.astype(np.float32)


def _ncc(a: np.ndarray, b: np.ndarray) -> float:
    """Pearson correlation of two 1-D arrays; NaN when either is constant."""
    a = a - a.mean()
    b = b - b.mean()
    denom = math.sqrt(float(np.dot(a, a)) * float(np.dot(b, b)))
    if denom == 0.0 or not math.isfinite(denom):
        return float("nan")
    return float(np.dot(a, b)) / denom


def _circular_distance(a, b) -> np.ndarray:
    return np.abs((np.asarray(a, dtype=np.float64) - b + 180.0) % 360.0 - 180.0)


def fit_sun_azimuth(
    dtm, posting_m, image, elevation_deg, *, valid=None, step_deg=1.0
) -> AzimuthFit:
    """Azimuth (clockwise from image-up) whose hillshade best correlates with ``image``.

    Raises ``ValueError`` when ``image`` and ``dtm`` (or ``valid``) differ in
    shape, or when fewer than two pixels are valid, or when no azimuth gives a
    finite correlation (e.g. a flat DTM).
    """
    dtm = np.asarray(dtm, dtype=np.float64)
    image = np.asarray(image, dtype=np.float64)
    if dtm.shape != image.shape:
        raise ValueError(f"dtm shape {dtm.shape} != image shape {image.shape}")
    slope, aspect = _slope_aspect(dtm, posting_m)
    mask = np.isfinite(dtm) & np.isfinite(image) & np.isfinite(slope) & np.isfinite(aspect)
    if valid is not None:
        valid = np.asarray(valid, dtype=bool)
        if valid.shape != dtm.shape:
            raise ValueError(f"valid shape {valid.shape} != dtm shape {dtm.shape}")
        mask &= valid
    n_valid = int(mask.sum())
    if n_valid < 2:
        raise ValueError(f"fit_sun_azimuth: {n_valid} valid pixel(s); need at least 2")

    s, a, img = slope[mask], aspect[mask], image[mask]
    azimuths = np.arange(0.0, 360.0, float(step_deg))
    ncc = np.array([_ncc(_shade(s, a, az, elevation_deg), img) for az in azimuths])
    if not np.any(np.isfinite(ncc)):
        raise ValueError("fit_sun_azimuth: no azimuth gives a finite correlation (flat input?)")
    i_peak = int(np.nanargmax(ncc))
    peak_deg = float(azimuths[i_peak])
    far = (_circular_distance(azimuths, peak_deg) >= SECOND_PEAK_MIN_SEPARATION_DEG) & np.isfinite(
        ncc
    )
    if np.any(far):
        i_second = int(np.flatnonzero(far)[np.argmax(ncc[far])])
        second_deg, second_ncc = float(azimuths[i_second]), float(ncc[i_second])
    else:
        second_deg, second_ncc = float("nan"), float("nan")
    return AzimuthFit(
        azimuth_deg=peak_deg,
        ncc_peak=float(ncc[i_peak]),
        azimuths=azimuths,
        ncc=ncc,
        second_peak_deg=second_deg,
        second_peak_ncc=second_ncc,
        peak_margin=float(ncc[i_peak]) - second_ncc,
        n_valid_px=n_valid,
    )


# ---------------------------------------------------------------------------
# Archive metadata (cross-check A, ISRO label)
# ---------------------------------------------------------------------------


def _as_float(value) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def sun_from_ode_metadata(json_path, product_name) -> SunGeometry:
    """Elevation ``90 - Incidence_angle`` from an ODE JSON query result; no azimuth."""
    json_path = Path(json_path)
    doc = json.loads(json_path.read_text())
    records = ((doc.get("ODEResults") or {}).get("Products") or {}).get("Product") or []
    if isinstance(records, dict):
        records = [records]
    wanted = str(product_name).upper()
    for index, record in enumerate(records):
        name = str(record.get("Product_name", ""))
        if not name.upper().startswith(wanted):
            continue
        incidence = _as_float(record.get("Incidence_angle"))
        where = f"{json_path} ODEResults.Products.Product[{index}] Product_name={name}"
        if incidence is None:
            return SunGeometry(
                None,
                None,
                ValueSource.UNKNOWN,
                ValueSource.UNKNOWN,
                FRAME_GRID,
                note=f"{where}: Incidence_angle missing or not a number "
                f"({record.get('Incidence_angle')!r})",
            )
        return SunGeometry(
            azimuth_deg=None,
            elevation_deg=90.0 - incidence,
            azimuth_source=ValueSource.UNKNOWN,
            elevation_source=ValueSource.DOCUMENTED,
            azimuth_frame=FRAME_GRID,
            note=f"{where}: elevation = 90 - Incidence_angle ({incidence})",
        )
    return SunGeometry(
        None,
        None,
        ValueSource.UNKNOWN,
        ValueSource.UNKNOWN,
        FRAME_GRID,
        note=f"no ODE record for {product_name}",
    )


def sun_from_label(product) -> SunGeometry:
    """OHRC label ``sun_azimuth_deg``/``sun_elevation_deg``; azimuth frame not documented."""
    azimuth = _as_float(product["sun_azimuth_deg"])
    elevation = _as_float(product["sun_elevation_deg"])
    label = getattr(product, "label_path", None)
    missing = [
        name
        for name, value in (("sun_azimuth_deg", azimuth), ("sun_elevation_deg", elevation))
        if value is None
    ]
    note = f"label {label}" if label is not None else "label"
    if missing:
        note += f"; missing: {', '.join(missing)}"
    return SunGeometry(
        azimuth_deg=azimuth,
        elevation_deg=elevation,
        azimuth_source=ValueSource.DOCUMENTED if azimuth is not None else ValueSource.UNKNOWN,
        elevation_source=ValueSource.DOCUMENTED if elevation is not None else ValueSource.UNKNOWN,
        azimuth_frame=FRAME_LABEL,
        note=note,
    )


# ---------------------------------------------------------------------------
# SPICE (primary)
# ---------------------------------------------------------------------------


def azimuth_elevation_from_vector(
    sun_body_xyz, lat_deg: float, lon_deg: float
) -> tuple[float, float]:
    """(azimuth clockwise from north in [0, 360), elevation), degrees, of a body-fixed vector.

    ``sun_body_xyz`` points from the surface point (lat, lon east-positive, on a
    sphere) towards the Sun, in body-fixed coordinates; its length is ignored.
    """
    s = np.asarray(sun_body_xyz, dtype=np.float64).reshape(3)
    norm = float(np.linalg.norm(s))
    if not math.isfinite(norm) or norm == 0.0:
        raise ValueError(f"sun vector must be finite and non-zero, got {s.tolist()}")
    s = s / norm
    phi, lam = math.radians(float(lat_deg)), math.radians(float(lon_deg))
    up = np.array([math.cos(phi) * math.cos(lam), math.cos(phi) * math.sin(lam), math.sin(phi)])
    east = np.array([-math.sin(lam), math.cos(lam), 0.0])
    north = np.array(
        [-math.sin(phi) * math.cos(lam), -math.sin(phi) * math.sin(lam), math.cos(phi)]
    )
    elevation = math.degrees(math.asin(max(-1.0, min(1.0, float(s @ up)))))
    azimuth = math.degrees(math.atan2(float(s @ east), float(s @ north))) % 360.0
    return azimuth, elevation


def _furnsh_once(spiceypy, kernels_dir: Path) -> list[str]:
    paths = [kernels_dir / name for name in SPICE_KERNELS]
    missing = [str(p) for p in paths if not p.is_file()]
    if missing:
        raise FileNotFoundError(
            f"SPICE kernel(s) missing: {', '.join(missing)} "
            "(scripts/fetch_public.py --only spice_lsk,spice_pck,spice_de440s)"
        )
    for path in paths:
        key = str(path.resolve())
        if key not in _LOADED_KERNELS:
            spiceypy.furnsh(key)
            _LOADED_KERNELS.add(key)
    return [p.name for p in paths]


def sun_from_spice(utc: str, lat_deg: float, lon_deg: float, kernels_dir) -> SunGeometry:
    """Sun azimuth/elevation at (lat, lon) at ``utc`` from the NAIF generic kernels.

    ``utc`` is an ISO 8601 UTC string; a trailing ``Z`` is dropped before
    ``str2et``. Raises ``ImportError`` without spiceypy and ``FileNotFoundError``
    naming any missing kernel.
    """
    try:
        import spiceypy
    except ImportError as exc:
        raise ImportError(
            "sun_from_spice needs spiceypy, the optional `spice` extra: "
            '.venv/bin/python -m pip install -e ".[spice]"'
        ) from exc
    names = _furnsh_once(spiceypy, Path(kernels_dir))
    utc_text = str(utc).strip()
    if utc_text.endswith("Z"):
        utc_text = utc_text[:-1]
    et = spiceypy.str2et(utc_text)
    sun, _ = spiceypy.spkpos("SUN", et, "IAU_MOON", "LT+S", "MOON")
    phi, lam = math.radians(float(lat_deg)), math.radians(float(lon_deg))
    point = SURFACE_RADIUS_KM * np.array(
        [math.cos(phi) * math.cos(lam), math.cos(phi) * math.sin(lam), math.sin(phi)]
    )
    azimuth, elevation = azimuth_elevation_from_vector(
        np.asarray(sun, dtype=np.float64) - point, lat_deg, lon_deg
    )
    return SunGeometry(
        azimuth_deg=azimuth,
        elevation_deg=elevation,
        azimuth_source=ValueSource.COMPUTED,
        elevation_source=ValueSource.COMPUTED,
        azimuth_frame=FRAME_NORTH,
        note=f"SPICE {', '.join(names)}; utc {utc_text}; IAU_MOON, LT+S; "
        f"sphere R={SURFACE_RADIUS_KM} km at lat {lat_deg}, lon {lon_deg}",
    )


def north_to_grid_azimuth(az_north, lat_deg, lon_deg, proj4) -> float:
    """Convert an azimuth clockwise from north to clockwise from grid-up in ``proj4``.

    Grid north is found numerically: the map direction from (lat, lon) to
    (lat + 1e-4, lon). Geographic coordinates use the sphere of ``proj4``'s ``+R``.
    """
    from lunar_reg.ingest.lro import _geographic_proj4, _warp

    xs, ys = _warp(
        _geographic_proj4(proj4),
        proj4,
        [float(lon_deg), float(lon_deg)],
        [float(lat_deg), float(lat_deg) + _NORTH_STEP_DEG],
    )
    dx, dy = float(xs[1] - xs[0]), float(ys[1] - ys[0])
    north_grid = math.degrees(math.atan2(dx, dy))
    return (float(az_north) - north_grid) % 360.0
