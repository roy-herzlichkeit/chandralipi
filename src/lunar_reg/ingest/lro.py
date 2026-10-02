"""LRO NAC reference products.

LRO NAC is the primary reference set: public, no login, and at ~0.5 m/px it sits
close enough to OHRC's ~0.25 m/px to keep the scale ratio manageable.

Format is detected, not assumed
-------------------------------
LROC has distributed data in more than one container over the mission's life,
and **this project has not inspected a real LROC download**. Rather than assume
PDS3 or PDS4, :func:`detect_format` sniffs the file and dispatches accordingly.
Both paths were validated in-session against GDAL 3.12 using labels hand-written
to the documented PDS3 and PDS4 schemas:

* PDS3 detached label (``.LBL`` + ``.IMG``) -> GDAL ``PDS`` driver, read correctly.
* PDS4 detached label (``.xml`` + ``.IMG``) -> GDAL ``PDS4`` driver, read correctly.

In both cases opening the raw ``.IMG`` fails or picks the wrong driver, so the
label is always the entry point.

What is still unverified
------------------------
Which format LROC actually serves for a given product type, and the label
keywords carrying illumination geometry. PDS3 keyword *parsing* here is generic
-- every keyword in the label is captured -- so nothing is invented; but the
mapping from keyword to manifest column for geometry is marked UNVERIFIED and
will resolve to ``None`` until confirmed against a real download.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from lunar_reg.provenance import ValueSource

logger = logging.getLogger(__name__)

PDS3 = "pds3"
PDS4 = "pds4"
ISIS3 = "isis3"

_PDS3_LABEL_SUFFIXES = {".lbl", ".lbl_", ".txt"}
_PDS4_LABEL_SUFFIXES = {".xml"}

#: ``KEY = VALUE`` on one line. PDS3 labels are ODL; this handles the flat
#: keyword form. Values spanning multiple lines or nested GROUP/OBJECT blocks
#: are captured by key but their structure is not reconstructed.
_PDS3_KEYWORD = re.compile(r"^\s*([\^\w:]+)\s*=\s*(.+?)\s*$")

#: Standard PDS3 keywords for array geometry. Part of the PDS3 standard, and
#: exercised against GDAL's PDS driver in this project's probe.
PDS3_STRUCTURE_KEYS = ("LINES", "LINE_SAMPLES", "SAMPLE_BITS", "SAMPLE_TYPE", "BANDS")

#: Commonly-present standard PDS3 identification/time keywords. Standard, but
#: presence in any given product is not guaranteed.
PDS3_COMMON_KEYS = (
    "PRODUCT_ID",
    "INSTRUMENT_ID",
    "INSTRUMENT_HOST_NAME",
    "MISSION_NAME",
    "TARGET_NAME",
    "START_TIME",
    "STOP_TIME",
)

#: UNVERIFIED. Candidate PDS3 keywords for illumination geometry. These are
#: guesses; no real LROC label has been inspected. :func:`read_lro_label`
#: reports which (if any) actually matched.
PDS3_GEOMETRY_KEYS_UNVERIFIED: dict[str, tuple[str, ...]] = {
    "sun_azimuth_deg": ("SUB_SOLAR_AZIMUTH", "SOLAR_AZIMUTH", "SUN_AZIMUTH"),
    "sun_elevation_deg": ("SUB_SOLAR_ELEVATION", "SOLAR_ELEVATION", "SUN_ELEVATION"),
    "incidence_angle_deg": ("INCIDENCE_ANGLE",),
    "emission_angle_deg": ("EMISSION_ANGLE",),
    "phase_angle_deg": ("PHASE_ANGLE",),
}

#: UNVERIFIED. Candidate PDS3 keywords for footprint corners.
PDS3_FOOTPRINT_KEYS_UNVERIFIED: dict[str, tuple[str, ...]] = {
    "min_lat": ("MINIMUM_LATITUDE",),
    "max_lat": ("MAXIMUM_LATITUDE",),
    "min_lon": ("WESTERNMOST_LONGITUDE", "MINIMUM_LONGITUDE"),
    "max_lon": ("EASTERNMOST_LONGITUDE", "MAXIMUM_LONGITUDE"),
}


def detect_format(path: str | Path) -> str | None:
    """Sniff a label's container format.

    Returns ``"pds3"``, ``"pds4"``, ``"isis3"``, or ``None``. Content is
    inspected rather than trusting the extension, because ``.IMG`` and ``.LBL``
    are used by several planetary formats.
    """
    path = Path(path)
    try:
        head = path.open("rb").read(2048)
    except OSError as exc:
        logger.warning("cannot read %s: %s", path, exc)
        return None

    text = head.decode("ascii", errors="ignore").lstrip()
    if text.startswith("<?xml") or "Product_Observational" in text:
        return PDS4
    if "PDS_VERSION_ID" in text:
        return PDS3
    if re.search(r"Object\s*=\s*IsisCube", text, re.IGNORECASE):
        return ISIS3
    return None


def parse_pds3_keywords(label_path: str | Path, max_bytes: int = 1 << 20) -> dict[str, str]:
    """Capture every ``KEY = VALUE`` pair in a PDS3 label.

    Deliberately generic: it invents no keyword names, it reports what the file
    contains. Reading stops at ``END`` or ``max_bytes`` so an attached label on a
    multi-GB ``.IMG`` does not pull in the image data.
    """
    label_path = Path(label_path)
    keywords: dict[str, str] = {}
    read = 0
    with label_path.open("r", encoding="latin-1", errors="ignore") as handle:
        for line in handle:
            read += len(line)
            if read > max_bytes:
                logger.warning("stopped parsing %s after %d bytes", label_path.name, max_bytes)
                break
            if line.strip() == "END":
                break
            match = _PDS3_KEYWORD.match(line)
            if match:
                key, value = match.group(1), match.group(2).strip().strip('"')
                keywords.setdefault(key.upper(), value)
    return keywords


@dataclass
class LROProduct:
    """An LRO reference product, whatever container it arrived in."""

    label_path: Path
    image_path: Path | None
    fmt: str
    values: dict[str, Any] = field(default_factory=dict)
    keywords: dict[str, str] = field(default_factory=dict)
    resolved: dict[str, str] = field(default_factory=dict)
    unresolved: list[str] = field(default_factory=list)
    sensor: str = "LRO_NAC"
    #: Map georeference read from the PDS4 cart block (C10); ``None`` when the
    #: label has none (the reason is then appended to ``unresolved``).
    georef: GeoReference | None = None

    def __getitem__(self, key: str) -> Any:
        return self.values.get(key)

    @property
    def geometry_resolved(self) -> bool:
        return any(k in self.resolved for k in PDS3_GEOMETRY_KEYS_UNVERIFIED)


def _as_float(value: str | None) -> float | None:
    if value is None:
        return None
    # PDS3 values often carry a unit suffix, e.g. "34.5 <deg>".
    match = re.match(r"[-+]?[\d.eE+-]+", value.strip())
    try:
        return float(match.group(0)) if match else None
    except ValueError:
        return None


def _as_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Map georeference from the PDS4 cart block (CONTRACTS C10,
# Phase_1/LLD/lro_georeference.md). GDAL's transform for these labels reads the
# deg/pixel ``pixel_resolution_x`` as metres, so geometry comes from the label.
# ---------------------------------------------------------------------------

POLAR_STEREOGRAPHIC = "Polar Stereographic"
EQUIRECTANGULAR = "Equirectangular"

#: Label paths (local names, ``pds4._resolve`` syntax) of the fields every
#: supported projection needs. ``pixel_scale_*`` is m/pixel; the sibling
#: ``pixel_resolution_*`` is deg/pixel and is never read.
_CART_COMMON: dict[str, str] = {
    "pixel_scale_x": "Cartography/pixel_scale_x",
    "pixel_scale_y": "Cartography/pixel_scale_y",
    "upperleft_corner_x": "Cartography/upperleft_corner_x",
    "upperleft_corner_y": "Cartography/upperleft_corner_y",
    "a_axis_radius": "Cartography/a_axis_radius",
    "west_bounding_coordinate": "Cartography/west_bounding_coordinate",
    "east_bounding_coordinate": "Cartography/east_bounding_coordinate",
    "north_bounding_coordinate": "Cartography/north_bounding_coordinate",
    "south_bounding_coordinate": "Cartography/south_bounding_coordinate",
}

#: Projection-specific parameters: local name -> path, per projection name.
_CART_PROJECTION: dict[str, dict[str, str]] = {
    POLAR_STEREOGRAPHIC: {
        "longitude_of_central_meridian": "Polar_Stereographic/longitude_of_central_meridian",
        "latitude_of_projection_origin": "Polar_Stereographic/latitude_of_projection_origin",
    },
    EQUIRECTANGULAR: {
        "longitude_of_central_meridian": "Equirectangular/longitude_of_central_meridian",
        "standard_parallel_1": "Equirectangular/standard_parallel_1",
    },
}

#: Points sampled along each raster edge when fitting the upper-left x sign (LLD §3).
SIGN_FIT_POINTS_PER_EDGE = 100
SIGN_FIT_POINTS_PER_EDGE_SOURCE = ValueSource.INFERRED


class LabelGeoreferenceError(ValueError):
    """The label cannot be turned into a :class:`GeoReference` (missing or unsupported fields)."""


def _fmt(value: float) -> str:
    """Compact number for a proj4 string: ``-69.3``, ``1737400``, ``-90``."""
    return f"{float(value):.12g}"


def _geographic_proj4(crs_proj4: str) -> str:
    """The sphere lon/lat CRS matching ``crs_proj4``'s ``+R``."""
    match = re.search(r"\+R=(\S+)", crs_proj4)
    if match is None:
        raise LabelGeoreferenceError(f"no +R in proj4 string {crs_proj4!r}")
    return f"+proj=longlat +R={match.group(1)} +no_defs"


def _warp(src: str, dst: str, xs, ys) -> tuple[np.ndarray, np.ndarray]:
    """Vectorised CRS transform through GDAL/PROJ, keeping the broadcast input shape."""
    from rasterio.warp import transform

    xs, ys = np.broadcast_arrays(np.asarray(xs, dtype=np.float64), np.asarray(ys, dtype=np.float64))
    shape = xs.shape
    if xs.size == 0:
        return np.empty(shape, np.float64), np.empty(shape, np.float64)
    out_x, out_y = transform(src, dst, xs.ravel().tolist(), ys.ravel().tolist())
    return (
        np.asarray(out_x, dtype=np.float64).reshape(shape),
        np.asarray(out_y, dtype=np.float64).reshape(shape),
    )


@dataclass(frozen=True)
class GeoReference:
    """A map-projected raster's georeference, read from its label (C10).

    Pixel-corner convention: ``(col, row) = (0, 0)`` is the outer upper-left
    corner of the first pixel; ``x = x0 + col * psx`` and ``y = y0 - row * psy``.
    Coordinate arguments are keyword-only because the legacy
    ``geometry_grid.lonlat_to_pixel(grid, lat, lon)`` takes latitude first.
    """

    crs_proj4: str
    x0_m: float
    y0_m: float
    pixel_size_x_m: float
    pixel_size_y_m: float
    width: int
    height: int
    source: ValueSource
    note: str = ""

    def pixel_to_xy(self, *, col, row) -> tuple[np.ndarray, np.ndarray]:
        col = np.asarray(col, dtype=np.float64)
        row = np.asarray(row, dtype=np.float64)
        return self.x0_m + col * self.pixel_size_x_m, self.y0_m - row * self.pixel_size_y_m

    def xy_to_pixel(self, *, x, y) -> tuple[np.ndarray, np.ndarray]:
        x = np.asarray(x, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        return (x - self.x0_m) / self.pixel_size_x_m, (self.y0_m - y) / self.pixel_size_y_m

    def lonlat_to_pixel(self, *, lon, lat) -> tuple[np.ndarray, np.ndarray]:
        x, y = _warp(_geographic_proj4(self.crs_proj4), self.crs_proj4, lon, lat)
        return self.xy_to_pixel(x=x, y=y)

    def pixel_to_lonlat(self, *, col, row) -> tuple[np.ndarray, np.ndarray]:
        x, y = self.pixel_to_xy(col=col, row=row)
        return _warp(self.crs_proj4, _geographic_proj4(self.crs_proj4), x, y)

    def affine(self):
        from affine import Affine

        return Affine(self.pixel_size_x_m, 0.0, self.x0_m, 0.0, -self.pixel_size_y_m, self.y0_m)

    def as_dict(self) -> dict:
        return {
            "crs_proj4": self.crs_proj4,
            "x0_m": float(self.x0_m),
            "y0_m": float(self.y0_m),
            "pixel_size_x_m": float(self.pixel_size_x_m),
            "pixel_size_y_m": float(self.pixel_size_y_m),
            "width": int(self.width),
            "height": int(self.height),
            "source": self.source.value,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, d: dict) -> GeoReference:
        return cls(
            crs_proj4=str(d["crs_proj4"]),
            x0_m=float(d["x0_m"]),
            y0_m=float(d["y0_m"]),
            pixel_size_x_m=float(d["pixel_size_x_m"]),
            pixel_size_y_m=float(d["pixel_size_y_m"]),
            width=int(d["width"]),
            height=int(d["height"]),
            source=ValueSource(d["source"]),
            note=str(d.get("note", "")),
        )


def _bbox_residual_m(
    crs_proj4: str,
    x0: float,
    y0: float,
    psx: float,
    psy: float,
    width: int,
    height: int,
    bounds: tuple[float, float, float, float],
    radius_m: float,
) -> float:
    """Metres between the raster boundary's lon/lat box and the label's (LLD §3).

    ``bounds`` = (west, east, north, south) in degrees. Longitudes are compared
    in [0, 360), wrapped to the shorter way round.
    """
    t = np.linspace(0.0, 1.0, SIGN_FIT_POINTS_PER_EDGE)
    cols = np.r_[t * width, np.full_like(t, width), t * width, np.zeros_like(t)]
    rows = np.r_[np.zeros_like(t), t * height, np.full_like(t, height), t * height]
    lon, lat = _warp(crs_proj4, _geographic_proj4(crs_proj4), x0 + cols * psx, y0 - rows * psy)
    if not (np.all(np.isfinite(lon)) and np.all(np.isfinite(lat))):
        return float("inf")
    lon = np.mod(lon, 360.0)
    west, east, north, south = bounds

    def dlon(a: float, b: float) -> float:
        return abs((np.mod(a, 360.0) - np.mod(b, 360.0) + 180.0) % 360.0 - 180.0)

    d_lon = max(dlon(lon.min(), west), dlon(lon.max(), east))
    d_lat = max(abs(float(lat.max()) - north), abs(float(lat.min()) - south))
    mean_lat = np.radians(0.5 * (north + south))
    deg = np.pi / 180.0
    return float(np.hypot(d_lon * radius_m * np.cos(mean_lat) * deg, d_lat * radius_m * deg))


def georeference_from_label(label_path: str | Path) -> GeoReference:
    """Georeference a map-projected PDS4 product from its own ``cart:`` block (C10).

    Never uses GDAL's transform: for LROC NAC ortho labels GDAL takes the
    deg/pixel ``pixel_resolution_x`` as the pixel size. The upper-left x sign
    is chosen by fitting the raster boundary to ``Bounding_Coordinates``
    (``Phase_1/LLD/lro_georeference.md`` §3); ``source`` is ``DOCUMENTED`` when
    the written value fits better and ``INFERRED`` when the flipped sign does.
    Raises :class:`LabelGeoreferenceError` listing every missing local name.
    """
    import xml.etree.ElementTree as ET

    from lunar_reg.ingest.pds4 import _read_axes, _resolve

    label_path = Path(label_path)
    try:
        root = ET.parse(label_path).getroot()
    except ET.ParseError as exc:
        raise LabelGeoreferenceError(f"{label_path.name}: not parseable XML: {exc}") from exc

    projection, _ = _resolve(root, ("Cartography/map_projection_name",))
    if projection is not None and projection not in _CART_PROJECTION:
        raise LabelGeoreferenceError(
            f"{label_path.name}: unsupported map_projection_name {projection!r} "
            f"(supported: {', '.join(_CART_PROJECTION)})"
        )
    wanted = dict(_CART_COMMON)
    if projection is not None:
        wanted.update(_CART_PROJECTION[projection])

    missing: list[str] = [] if projection is not None else ["map_projection_name"]
    raw: dict[str, float] = {}
    for name, path in wanted.items():
        text, _ = _resolve(root, (path,))
        value = _as_float(text)
        if value is None:
            missing.append(name)
        else:
            raw[name] = value
    axes = {a.name.lower(): a.elements for a in _read_axes(root)}
    for axis in ("Line", "Sample"):
        if axis.lower() not in axes:
            missing.append(f"Axis_Array {axis}")
    if missing:
        raise LabelGeoreferenceError(
            f"{label_path.name}: cannot georeference, missing label field(s): {', '.join(missing)}"
        )

    if raw["a_axis_radius"] <= 0:
        raise LabelGeoreferenceError(
            f"{label_path.name}: non-positive a_axis_radius ({raw['a_axis_radius']} km)"
        )
    radius_m = raw["a_axis_radius"] * 1000.0
    cm = raw["longitude_of_central_meridian"]
    if projection == POLAR_STEREOGRAPHIC:
        lat_ts = raw["latitude_of_projection_origin"]
        lat_0 = -90.0 if lat_ts < 0 else 90.0
        crs = (
            f"+proj=stere +lat_0={_fmt(lat_0)} +lat_ts={_fmt(lat_ts)} +lon_0={_fmt(cm)} "
            f"+R={_fmt(radius_m)} +units=m +no_defs"
        )
    else:
        crs = (
            f"+proj=eqc +lat_ts={_fmt(raw['standard_parallel_1'])} +lon_0={_fmt(cm)} "
            f"+R={_fmt(radius_m)} +units=m +no_defs"
        )

    psx, psy = raw["pixel_scale_x"], raw["pixel_scale_y"]
    if psx <= 0 or psy <= 0:
        raise LabelGeoreferenceError(
            f"{label_path.name}: non-positive pixel_scale_x/y ({psx}, {psy})"
        )
    width, height = int(axes["sample"]), int(axes["line"])
    bounds = (
        raw["west_bounding_coordinate"],
        raw["east_bounding_coordinate"],
        raw["north_bounding_coordinate"],
        raw["south_bounding_coordinate"],
    )
    written_x, y0 = raw["upperleft_corner_x"], raw["upperleft_corner_y"]
    from rasterio.errors import CRSError

    try:
        as_written = _bbox_residual_m(crs, written_x, y0, psx, psy, width, height, bounds, radius_m)
        flipped = _bbox_residual_m(crs, -written_x, y0, psx, psy, width, height, bounds, radius_m)
    except (CRSError, ValueError) as exc:
        if isinstance(exc, LabelGeoreferenceError):
            raise
        raise LabelGeoreferenceError(
            f"{label_path.name}: PROJ rejected the label projection {crs!r}: {exc}"
        ) from exc
    keep = as_written <= flipped
    chosen, other = (as_written, flipped) if keep else (flipped, as_written)
    note = (
        f"ul_x sign {'as written' if keep else 'flipped'}; "
        f"bbox residual {chosen:.1f} m (other sign {other:.1f} m)"
    )
    geo = GeoReference(
        crs_proj4=crs,
        x0_m=written_x if keep else -written_x,
        y0_m=y0,
        pixel_size_x_m=psx,
        pixel_size_y_m=psy,
        width=width,
        height=height,
        source=ValueSource.DOCUMENTED if keep else ValueSource.INFERRED,
        note=note,
    )
    logger.info("%s: georeference %s (%s)", label_path.name, geo.source.value, note)
    return geo


#: Largest raster-vs-label bound disagreement, in pixels, still counted as agreement (LLD §2).
RASTER_LABEL_TOLERANCE_PX = 1.5
RASTER_LABEL_TOLERANCE_PX_SOURCE = ValueSource.INFERRED

_PDS3_BOUND_KEYS = (
    "MAXIMUM_LATITUDE",
    "MINIMUM_LATITUDE",
    "WESTERNMOST_LONGITUDE",
    "EASTERNMOST_LONGITUDE",
)


def georeference_from_raster(path: str | Path) -> GeoReference:
    """Georeference a map-projected raster from its GDAL tags (C10, P1.24).

    Accepts a north-up sphere ``stere``/``eqc`` CRS only. ``source`` is
    ``DOCUMENTED`` when a PDS3 label (``path`` itself when it is a ``.lbl``,
    else ``<stem>.lbl``) carries all four bounding keywords and the raster's
    outer corners agree with them within
    :data:`RASTER_LABEL_TOLERANCE_PX` pixels; otherwise ``INFERRED`` with the
    reason in ``note``. Never for the NAC PDS4 orthos, whose GDAL transform is
    wrong (S12): those use :func:`georeference_from_label`.
    """
    import rasterio
    from rasterio.errors import RasterioError

    path = Path(path)
    try:
        with rasterio.open(path) as ds:
            crs, transform, width, height = ds.crs, ds.transform, ds.width, ds.height
    except (OSError, RasterioError) as exc:
        raise LabelGeoreferenceError(f"{path.name}: cannot open raster: {exc}") from exc
    if crs is None:
        raise LabelGeoreferenceError(f"{path.name}: raster has no CRS")
    proj4 = crs.to_proj4().replace("+no_defs=True", "+no_defs")
    if not ("+proj=stere" in proj4 or "+proj=eqc" in proj4) or "+R=" not in proj4:
        raise LabelGeoreferenceError(
            f"{path.name}: unsupported CRS {proj4!r} (need +proj=stere or +proj=eqc on a +R sphere)"
        )
    t = transform
    if not (t.b == 0 and t.d == 0 and t.a > 0 and t.e < 0):
        raise LabelGeoreferenceError(
            f"{path.name}: transform is not north-up (a={t.a}, b={t.b}, d={t.d}, e={t.e})"
        )
    psx, psy = float(t.a), float(-t.e)
    geo = GeoReference(
        crs_proj4=proj4,
        x0_m=float(t.c),
        y0_m=float(t.f),
        pixel_size_x_m=psx,
        pixel_size_y_m=psy,
        width=int(width),
        height=int(height),
        source=ValueSource.INFERRED,
        note="raster tags not cross-checked (no PDS3 bounding keywords)",
    )

    label = path if path.suffix.lower() == ".lbl" else path.with_suffix(".lbl")
    keywords = parse_pds3_keywords(label) if label.exists() else {}
    bounds = {k: _as_float(keywords.get(k)) for k in _PDS3_BOUND_KEYS}
    if any(v is None for v in bounds.values()):
        logger.info("%s: georeference %s (%s)", path.name, geo.source.value, geo.note)
        return geo

    radius_m = float(re.search(r"\+R=(\S+)", proj4).group(1))
    lon, lat = geo.pixel_to_lonlat(
        col=np.array([0.0, width, 0.0, width]), row=np.array([0.0, 0.0, height, height])
    )
    if not (np.all(np.isfinite(lon)) and np.all(np.isfinite(lat))):
        return replace(geo, note="raster corners do not project to lon/lat; not cross-checked")
    lon = np.mod(lon, 360.0)

    def dlon(a: float, b: float) -> float:
        return abs((np.mod(a, 360.0) - np.mod(b, 360.0) + 180.0) % 360.0 - 180.0)

    deg = np.pi / 180.0
    mean_lat = np.radians(0.5 * (bounds["MAXIMUM_LATITUDE"] + bounds["MINIMUM_LATITUDE"]))
    d_lat_m = (
        max(
            abs(float(lat.max()) - bounds["MAXIMUM_LATITUDE"]),
            abs(float(lat.min()) - bounds["MINIMUM_LATITUDE"]),
        )
        * radius_m
        * deg
    )
    d_lon_m = (
        max(
            dlon(float(lon.min()), bounds["WESTERNMOST_LONGITUDE"]),
            dlon(float(lon.max()), bounds["EASTERNMOST_LONGITUDE"]),
        )
        * radius_m
        * np.cos(mean_lat)
        * deg
    )
    residual_m = float(max(d_lat_m, d_lon_m))
    residual_px = residual_m / min(psx, psy)
    if residual_px <= RASTER_LABEL_TOLERANCE_PX:
        geo = replace(
            geo,
            source=ValueSource.DOCUMENTED,
            note=(
                f"raster tags agree with PDS3 label bounds within {residual_m:.1f} m "
                f"({residual_px:.2f} px)"
            ),
        )
    else:
        geo = replace(
            geo,
            note=(
                f"raster tags disagree with PDS3 label bounds ({label.name}) by {residual_m:.1f} m "
                f"({residual_px:.2f} px > {RASTER_LABEL_TOLERANCE_PX} px)"
            ),
        )
    logger.info("%s: georeference %s (%s)", path.name, geo.source.value, geo.note)
    return geo


def read_lro_label(label_path: str | Path) -> LROProduct:
    """Read an LRO reference label, dispatching on detected format.

    PDS4 labels are delegated to :func:`lunar_reg.ingest.pds4.read_label` so both
    archives share one field map and one provenance mechanism.
    """
    label_path = Path(label_path)
    fmt = detect_format(label_path)

    if fmt == PDS4:
        from lunar_reg.ingest.pds4 import read_label

        parsed = read_label(label_path, sensor="LRO_NAC")
        values = dict(parsed.values)
        resolved = dict(parsed.resolved)
        unresolved = list(parsed.unresolved)
        values["lines"] = parsed.lines
        values["samples"] = parsed.samples
        values["bands"] = parsed.bands
        _read_pds4_bounds(label_path, values, resolved, unresolved)
        try:
            georef = georeference_from_label(label_path)
        except LabelGeoreferenceError as exc:
            georef = None
            unresolved.append(f"georef: {exc}")
        return LROProduct(
            label_path=parsed.label_path,
            image_path=parsed.image_path,
            fmt=PDS4,
            values=values,
            resolved=resolved,
            unresolved=unresolved,
            georef=georef,
        )

    if fmt != PDS3:
        raise ValueError(
            f"{label_path.name}: unrecognised label format "
            f"({fmt or 'no PDS_VERSION_ID or XML header found'}). "
            f"Supported: PDS3 detached label, PDS4 XML label."
        )

    keywords = parse_pds3_keywords(label_path)
    values: dict[str, Any] = {}
    resolved: dict[str, str] = {}
    unresolved: list[str] = []

    for key in PDS3_STRUCTURE_KEYS + PDS3_COMMON_KEYS:
        if key in keywords:
            values[key.lower()] = keywords[key]
            resolved[key.lower()] = key
        else:
            unresolved.append(key.lower())

    for name, candidates in (
        *PDS3_GEOMETRY_KEYS_UNVERIFIED.items(),
        *PDS3_FOOTPRINT_KEYS_UNVERIFIED.items(),
    ):
        for candidate in candidates:
            if candidate in keywords:
                values[name] = _as_float(keywords[candidate])
                resolved[name] = candidate
                break
        else:
            values[name] = None
            unresolved.append(name)

    values["start_time"] = _as_datetime(keywords.get("START_TIME"))
    values["stop_time"] = _as_datetime(keywords.get("STOP_TIME"))
    values["lines"] = int(_as_float(keywords.get("LINES")) or 0) or None
    values["samples"] = int(_as_float(keywords.get("LINE_SAMPLES")) or 0) or None
    values["bands"] = int(_as_float(keywords.get("BANDS")) or 1) or 1
    values["product_id"] = keywords.get("PRODUCT_ID") or label_path.stem

    return LROProduct(
        label_path=label_path,
        image_path=_pds3_image_path(label_path, keywords),
        fmt=PDS3,
        values=values,
        keywords=keywords,
        resolved=resolved,
        unresolved=unresolved,
    )


#: Manifest footprint column -> PDS4 ``cart:Bounding_Coordinates`` element (LLD §5).
PDS4_BOUND_PATHS: dict[str, str] = {
    "min_lat": "Bounding_Coordinates/south_bounding_coordinate",
    "max_lat": "Bounding_Coordinates/north_bounding_coordinate",
    "min_lon": "Bounding_Coordinates/west_bounding_coordinate",
    "max_lon": "Bounding_Coordinates/east_bounding_coordinate",
}


def _read_pds4_bounds(
    label_path: Path, values: dict[str, Any], resolved: dict[str, str], unresolved: list[str]
) -> None:
    """Fill ``min/max_lat/lon`` from the four ``*_bounding_coordinate`` fields, in place."""
    import xml.etree.ElementTree as ET

    from lunar_reg.ingest.pds4 import _resolve

    root = ET.parse(label_path).getroot()
    for name, path in PDS4_BOUND_PATHS.items():
        text, matched = _resolve(root, (path,))
        value = _as_float(text)
        values[name] = value
        if value is None or matched is None:
            unresolved.append(name)
        else:
            resolved[name] = matched


def _pds3_image_path(label_path: Path, keywords: dict[str, str]) -> Path | None:
    """Resolve ``^IMAGE`` to a file, or fall back to a sibling ``.IMG``.

    ``^IMAGE`` may be ``("file.img",1)``, ``"file.img"``, or a bare record
    number for an attached label (in which case the data is in the label file
    itself). A pointer naming a file outside the label's directory is refused
    (``None``).
    """
    from lunar_reg.ingest.pds4 import resolve_contained

    pointer = keywords.get("^IMAGE", "")
    match = re.search(r'"([^"]+)"', pointer)
    if match:
        contained = resolve_contained(label_path, match.group(1))
        if contained is None:
            logger.warning(
                "label %s points ^IMAGE at %r outside its own directory; refusing it",
                label_path.name,
                match.group(1),
            )
        return contained
    if pointer.strip().isdigit():
        return label_path  # attached label: data lives in this same file
    for suffix in (".img", ".IMG"):
        candidate = label_path.with_suffix(suffix)
        if candidate.exists():
            return candidate
    return label_path.with_suffix(".IMG")


def open_lro_product(path: str | Path):
    """Open an LRO product for windowed reading, via its label.

    As with PDS4, the label is the entry point: GDAL resolves a bare ``.IMG``
    by extension and gets the wrong driver.

    Warning: never take geometry from the opened dataset's GDAL transform (it
    reads the deg/pixel ``pixel_resolution_x`` as metres); callers that need
    geometry use ``LROProduct.georef`` (:func:`georeference_from_label`).
    """
    import rasterio

    path = Path(path)
    if path.suffix.lower() in {".img"}:
        for suffix in (*_PDS3_LABEL_SUFFIXES, *_PDS4_LABEL_SUFFIXES):
            for cased in (suffix, suffix.upper()):
                candidate = path.with_suffix(cased)
                if candidate.exists():
                    logger.info("opening via label %s", candidate.name)
                    return rasterio.open(candidate)
        logger.warning("no sibling label for %s; GDAL will guess by extension", path.name)
    return rasterio.open(path)


def lro_to_row(product: LROProduct) -> dict:
    """Flatten an :class:`LROProduct` into a manifest row.

    Column names match :data:`lunar_reg.ingest.manifest.COLUMNS` so LRO
    reference products and Chandrayaan-2 products land in one table.
    """
    from lunar_reg.ingest.manifest import product_type_of

    return {
        "product_id": product["product_id"],
        "sensor": product.sensor,
        "archive": "lro",
        "label_path": str(product.label_path),
        "image_path": None if product.image_path is None else str(product.image_path),
        "lines": product["lines"],
        "samples": product["samples"],
        "bands": product["bands"] or 1,
        "array_kind": None,
        "axis_order": None,
        "data_type": product["sample_type"],
        "numpy_dtype": None,
        "megapixels": (
            product["lines"] * product["samples"] / 1e6
            if product["lines"] and product["samples"]
            else None
        ),
        "start_time": product["start_time"],
        "stop_time": product["stop_time"],
        "sun_azimuth_deg": product["sun_azimuth_deg"],
        "sun_elevation_deg": product["sun_elevation_deg"],
        "incidence_angle_deg": product["incidence_angle_deg"],
        "emission_angle_deg": product["emission_angle_deg"],
        "phase_angle_deg": product["phase_angle_deg"],
        "min_lat": product["min_lat"],
        "max_lat": product["max_lat"],
        "min_lon": product["min_lon"],
        "max_lon": product["max_lon"],
        "geometry_resolved": product.geometry_resolved,
        "footprint_resolved": all(
            product[k] is not None for k in ("min_lat", "max_lat", "min_lon", "max_lon")
        ),
        "unresolved_fields": ",".join(product.unresolved),
        "product_type": product_type_of(product.label_path),
    }


def scan_lro_directory(root: str | Path, strict: bool = False, with_diagnostics: bool = False):
    """Parse every LRO data label under ``root`` into a manifest DataFrame.

    Same statuses as :func:`lunar_reg.ingest.manifest.scan_directory`: non-data
    labels are ``NOT_A_DATA_PRODUCT``, unreadable ones ``PARSE_ERROR`` (raised
    instead when ``strict``), a missing ``root`` is ``ROOT_MISSING``. Returns the
    frame, or ``(frame, ScanDiagnostics)`` when ``with_diagnostics``.
    """
    import pandas as pd

    from lunar_reg.ingest.manifest import COLUMNS, ScanDiagnostics, ScanStatus, product_type_of

    diag = ScanDiagnostics()
    root = Path(root)
    candidates: set[Path] = set()
    if not root.exists():
        diag.record(ScanStatus.ROOT_MISSING, f"{root}: no such directory")
    else:
        for pattern in ("*.lbl", "*.LBL", "*.xml", "*.XML"):
            candidates.update(root.rglob(pattern))

    rows = []
    for path in sorted(candidates):
        kind = product_type_of(path)
        if kind != "data":
            diag.record(ScanStatus.NOT_A_DATA_PRODUCT, f"{path}: product_type={kind}")
            continue
        try:
            rows.append(lro_to_row(read_lro_label(path)))
        except Exception as exc:  # noqa: BLE001 - one bad label must not stop the scan
            if strict:
                raise
            diag.record(ScanStatus.PARSE_ERROR, f"{path}: {type(exc).__name__}: {exc}")
            continue
        diag.record(ScanStatus.PARSED, str(path))

    frame = pd.DataFrame(rows, columns=list(COLUMNS))
    for col in ("start_time", "stop_time"):
        frame[col] = pd.to_datetime(frame[col], errors="coerce", utc=True)
    logger.info("scanned %d LRO product(s) from %s: %s", len(frame), root, diag.counts)
    if with_diagnostics:
        return frame, diag
    return frame
