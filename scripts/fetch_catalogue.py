"""Build a product manifest from archive *catalogues*, without downloading imagery.

Why this exists
---------------
Until now the only way to learn where a Chandrayaan-2 product sits was to
download it and parse its label. That is how three disjoint regions of the Moon
ended up in ``data/raw`` and why no cross-instrument pair was ever possible: the
selection decision was made after the bytes had already been paid for.

Both archives expose a catalogue that returns footprint polygons with no pixels
attached. The whole Chandrayaan-2 optical catalogue is a few megabytes. This
module turns those catalogues into the same manifest shape that
:mod:`lunar_reg.ingest.manifest` produces from real labels, so that
``find_overlapping_pairs`` can run *before* anything is fetched.

Provenance, and what these rows are NOT
---------------------------------------
A catalogue row is weaker evidence than a parsed PDS4 label, and the two must
never be confused in a results table. Every row therefore carries:

``source``
    ``"issdc_wfs"`` or ``"ode_rest"`` -- which catalogue the row came from.
``footprint_resolved``
    ``True``: the footprint is a real polygon from the archive, not a guess.
``geometry_resolved``
    Sun/viewing geometry usable? **Always ``False`` for ISSDC rows.**
    VERIFIED 2026-09-28: every ISSDC record sampled returns
    ``INC_ANGLE = EMI_ANGLE = PHA_ANGLE = 0``. A zero incidence angle at -69
    degrees latitude is geometrically impossible, so these are unpopulated
    placeholders, not measurements. They are dropped rather than carried.
    ODE rows do carry real angles and are marked ``True``.

Columns that can only come from the file itself -- ``lines``, ``samples``,
``bands``, ``data_type``, ``image_path`` -- are left ``None``. They are filled in
later by rescanning the downloaded labels through ``manifest.build_manifest``.
Do not treat a catalogue manifest as a substitute for that pass.

Coordinate systems
------------------
VERIFIED 2026-09-28 against three OHRC products independently measured by this
project from their real PDS4 labels (78.89 / 78.96 / 79.33 km^2): the ISSDC
polar layers are published in **metres**, not degrees.

======================  ==========================================
``EPSG:100009``         equatorial, degrees (lon, lat)
``EPSG:100010``         north polar stereographic, metres
``EPSG:100011``         south polar stereographic, metres
======================  ==========================================

The inverse projection below reproduced those three footprints to within
0.008 degrees of latitude and 0.7 percent of area. Mixing the two silently
yields plausible wrong numbers, which is the specific hazard this docstring
exists to prevent.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import urllib.parse
import urllib.request
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

#: IAU mean lunar radius, metres. Matches ``ingest.footprint.moon_datum``.
MOON_RADIUS_M = 1737400.0

#: ISSDC GeoServer CRS codes, confirmed from live GetCapabilities 2026-09-28.
CRS_EQUATORIAL = 100009
CRS_NORTH_POLAR = 100010
CRS_SOUTH_POLAR = 100011

ODE_ENDPOINT = "https://oderest.rsl.wustl.edu/live2/"

#: LROC product types, read from ODE's own ``query=iipy`` dump on 2026-09-28.
#: Do not add entries here from memory -- rerun that query instead.
ODE_PRODUCT_TYPES: dict[str, str] = {
    "CDRNAC4": "NAC calibrated (NOT map-projected -- crs is None)",
    "EDRNAC4": "NAC raw (NOT map-projected)",
    "CDRWAM4": "WAC calibrated, mono",
    "SDNDTM": "NAC digital terrain map + map-projected orthoimages",
    "SDPPHO": "NAC map-projected photometric products",
    "BDRNPL": "NAC polar mosaics",
}


class RowOutcome(Enum):
    """Why a catalogue record did or did not become a manifest row.

    ``suspicious`` marks outcomes that probably indicate a bug or an archive
    change rather than an ordinary absence, so that the report can separate
    "nothing was there" from "something is wrong".
    """

    OK = ("ok", False)
    NO_GEOMETRY = ("record carried no geometry", True)
    EMPTY_RING = ("geometry present but ring was empty", True)
    MISSING_ID = ("record had no product identifier", True)
    OUTSIDE_BOX = ("footprint outside the requested box", False)
    DEGENERATE_FOOTPRINT = ("footprint collapsed to zero area", True)

    def __init__(self, description: str, suspicious: bool) -> None:
        self.description = description
        self.suspicious = suspicious


@dataclass
class Diagnostics:
    """Counts plus one retained sample per outcome.

    Printed on every run, not only on failure: a silent zero is how a broken
    field mapping hides.
    """

    counts: Counter = field(default_factory=Counter)
    samples: dict[RowOutcome, str] = field(default_factory=dict)

    def record(self, outcome: RowOutcome, sample: str) -> None:
        self.counts[outcome] += 1
        self.samples.setdefault(outcome, sample)

    def report(self) -> str:
        if not self.counts:
            return "  (no records seen)"
        lines = []
        for outcome in RowOutcome:
            n = self.counts.get(outcome, 0)
            if not n:
                continue
            flag = "  <-- SUSPICIOUS" if outcome.suspicious else ""
            lines.append(f"  {outcome.name:<22} {n:>6}  {outcome.description}{flag}")
            if outcome is not RowOutcome.OK and outcome in self.samples:
                lines.append(f"  {'':<22}         e.g. {self.samples[outcome]}")
        return "\n".join(lines)


def inverse_polar_stereographic(
    x: float, y: float, *, south: bool, radius: float = MOON_RADIUS_M
) -> tuple[float, float]:
    """Projected metres -> ``(lat, lon)`` degrees, spherical, k0=1, lon_0=0.

    VERIFIED 2026-09-28 against three OHRC products this project had already
    measured from their PDS4 labels; agreement was 0.008 degrees in latitude and
    0.7 percent in area. The residual is small and systematic, consistent with
    the catalogue polygon being slightly generalised relative to the label
    corners. It is agreement, not identity.
    """
    rho = math.hypot(x, y)
    if rho == 0.0:
        return (-90.0 if south else 90.0, 0.0)
    c = 2.0 * math.atan2(rho, 2.0 * radius)
    if south:
        return math.degrees(math.asin(-math.cos(c))), math.degrees(math.atan2(x, y))
    return math.degrees(math.asin(math.cos(c))), math.degrees(math.atan2(x, -y))


def _outer_ring(geometry: dict) -> list[list[float]] | None:
    """First ring of a Polygon/MultiPolygon, or ``None`` if there isn't one."""
    coords = geometry.get("coordinates") if geometry else None
    if not coords:
        return None
    try:
        while isinstance(coords[0][0][0], list):
            coords = coords[0]
        return coords[0]
    except (IndexError, TypeError):
        return None


def _ring_to_latlon(ring, crs_code: int) -> list[tuple[float, float]]:
    """Ring vertices -> ``(lat, lon)`` pairs, honouring the layer's CRS."""
    if crs_code == CRS_EQUATORIAL:
        return [(pt[1], pt[0]) for pt in ring]
    south = crs_code == CRS_SOUTH_POLAR
    return [inverse_polar_stereographic(pt[0], pt[1], south=south) for pt in ring]


def _crs_code(document: dict) -> int:
    """EPSG code from a GeoJSON ``crs`` member; defaults to equatorial."""
    name = ((document.get("crs") or {}).get("properties") or {}).get("name", "")
    tail = name.rsplit(":", 1)[-1]
    return int(tail) if tail.isdigit() else CRS_EQUATORIAL


def _spherical_area_km2(latlon: list[tuple[float, float]], radius: float = MOON_RADIUS_M) -> float:
    """Spherical polygon area via the shoelace form of the spherical excess."""
    ring = latlon + [latlon[0]] if latlon[0] != latlon[-1] else latlon
    total = 0.0
    for (lat1, lon1), (lat2, lon2) in zip(ring[:-1], ring[1:], strict=True):
        total += math.radians(lon2 - lon1) * (
            2.0 + math.sin(math.radians(lat1)) + math.sin(math.radians(lat2))
        )
    return abs(total * radius * radius / 2.0) / 1e6


def read_issdc_catalogue(
    path: Path,
    sensor: str,
    diagnostics: Diagnostics,
    box: tuple[float, float, float, float] | None = None,
) -> Iterator[dict]:
    """Rows from one ISSDC WFS GeoJSON file saved from the map-browse session.

    Field names are those the live service returns; they were read off real
    records on 2026-09-28 and must not be edited from memory. Re-run the WFS
    query and inspect a feature's ``properties`` if the archive changes.
    """
    document = json.loads(path.read_text())
    crs_code = _crs_code(document)
    for feature in document.get("features", []):
        properties = feature.get("properties") or {}
        product_id = properties.get("PRODUCT_ID")
        if not product_id:
            diagnostics.record(RowOutcome.MISSING_ID, f"{path.name}: feature without PRODUCT_ID")
            continue
        ring = _outer_ring(feature.get("geometry") or {})
        if ring is None:
            diagnostics.record(RowOutcome.NO_GEOMETRY, product_id)
            continue
        if not ring:
            diagnostics.record(RowOutcome.EMPTY_RING, product_id)
            continue

        latlon = _ring_to_latlon(ring, crs_code)
        lats = [p[0] for p in latlon]
        lons = [p[1] for p in latlon]
        area = _spherical_area_km2(latlon)
        if area <= 0.0:
            diagnostics.record(RowOutcome.DEGENERATE_FOOTPRINT, product_id)
            continue
        if box and not _intersects(lats, lons, box):
            diagnostics.record(RowOutcome.OUTSIDE_BOX, product_id)
            continue

        diagnostics.record(RowOutcome.OK, product_id)
        yield {
            "product_id": product_id,
            "sensor": sensor,
            "archive": "chandrayaan2",
            "source": "issdc_wfs",
            "source_crs": crs_code,
            "start_time": properties.get("OBS_ST_TIME"),
            "stop_time": properties.get("OBS_ED_TIME"),
            "download_name": properties.get("DOWNLOAD"),
            "browse_name": properties.get("BROWSE"),
            "footprint_area_km2": area,
            # Deliberately absent: see the module docstring. ISSDC publishes
            # INC/EMI/PHA as 0, which is a placeholder, not a measurement.
            "incidence_angle_deg": None,
            "emission_angle_deg": None,
            "phase_angle_deg": None,
            "geometry_resolved": False,
            "footprint_resolved": True,
            "unresolved_fields": "incidence_angle_deg,emission_angle_deg,phase_angle_deg",
            **_corner_columns(latlon),
            "min_lat": min(lats), "max_lat": max(lats),
            "min_lon": min(lons), "max_lon": max(lons),
        }


def _corner_columns(latlon: list[tuple[float, float]]) -> dict[str, float | None]:
    """First four ring vertices as ``cornerN_lat`` / ``cornerN_lon``.

    A catalogue ring is closed and may carry more than four vertices, so this is
    the footprint's first four corners, not necessarily the label's UL/UR/BL/BR
    in that order. Downstream code should prefer the polygon.
    """
    out: dict[str, float | None] = {}
    for i in range(1, 5):
        if i - 1 < len(latlon):
            out[f"corner{i}_lat"], out[f"corner{i}_lon"] = latlon[i - 1]
        else:
            out[f"corner{i}_lat"] = out[f"corner{i}_lon"] = None
    return out


def _intersects(lats, lons, box: tuple[float, float, float, float]) -> bool:
    """Bounding-box overlap test. Antimeridian- and pole-naive by design.

    Near the poles a lat/lon box spans every longitude and this test degenerates
    into "overlaps everything". Callers working within a few degrees of a pole
    must filter in projected coordinates instead.
    """
    min_lat, max_lat, min_lon, max_lon = box
    if max(lats) < min_lat or min(lats) > max_lat:
        return False
    return not (max(lons) < min_lon or min(lons) > max_lon)


def query_ode(
    product_type: str,
    box: tuple[float, float, float, float],
    *,
    limit: int = 1000,
    timeout: int = 180,
) -> list[dict]:
    """LRO products whose footprint meets ``box``; raw ODE records.

    ``results=m`` keeps the payload to metadata. Asking for ``fmp`` returns the
    per-product file list too and overruns a few megabytes quickly -- a 1000-row
    request truncated mid-JSON during development.
    """
    if product_type not in ODE_PRODUCT_TYPES:
        raise ValueError(
            f"{product_type!r} is not a verified ODE product type; "
            f"known: {sorted(ODE_PRODUCT_TYPES)}"
        )
    min_lat, max_lat, min_lon, max_lon = box
    query = urllib.parse.urlencode({
        "query": "product", "results": "m", "output": "JSON",
        "odemetadb": "moon", "ihid": "LRO", "iid": "LROC", "pt": product_type,
        "minlat": min_lat, "maxlat": max_lat,
        "westernlon": min_lon, "easternlon": max_lon,
        "limit": limit,
    })
    with urllib.request.urlopen(f"{ODE_ENDPOINT}?{query}", timeout=timeout) as response:
        payload = json.loads(response.read().decode())
    results = payload.get("ODEResults", {})
    if results.get("Status") != "Success":
        raise RuntimeError(f"ODE returned {results.get('Status')}: {results.get('Error')}")
    products = (results.get("Products") or {}).get("Product") or []
    return [products] if isinstance(products, dict) else products


def ode_rows(records: list[dict], sensor: str, diagnostics: Diagnostics) -> Iterator[dict]:
    """ODE records -> manifest rows. Field names as ODE returns them."""
    for record in records:
        product_id = record.get("pdsid") or record.get("Product_name")
        if not product_id:
            diagnostics.record(RowOutcome.MISSING_ID, "ODE record without pdsid")
            continue
        try:
            lats = [float(record["Minimum_latitude"]), float(record["Maximum_latitude"])]
            lons = [float(record["Westernmost_longitude"]), float(record["Easternmost_longitude"])]
        except (KeyError, TypeError, ValueError):
            diagnostics.record(RowOutcome.NO_GEOMETRY, str(product_id))
            continue

        diagnostics.record(RowOutcome.OK, str(product_id))
        yield {
            "product_id": product_id,
            "sensor": sensor,
            "archive": "lro",
            "source": "ode_rest",
            "source_crs": None,
            "start_time": record.get("UTC_start_time"),
            "stop_time": record.get("UTC_stop_time"),
            "download_name": None,
            "browse_name": None,
            "footprint_area_km2": None,
            "incidence_angle_deg": _as_float(record.get("Incidence_angle")),
            "emission_angle_deg": _as_float(record.get("Emission_angle")),
            "phase_angle_deg": _as_float(record.get("Phase_angle")),
            # ODE publishes real illumination geometry, unlike ISSDC.
            "geometry_resolved": record.get("Incidence_angle") not in (None, ""),
            "footprint_resolved": True,
            "unresolved_fields": "",
            **{f"corner{i}_{c}": None for i in range(1, 5) for c in ("lat", "lon")},
            "min_lat": min(lats), "max_lat": max(lats),
            "min_lon": min(lons), "max_lon": max(lons),
            "footprint_wkt": record.get("Footprint_C0_geometry"),
        }


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--issdc-dir", type=Path, required=True,
                        help="directory of *.geojson files saved from the ISSDC map-browse session")
    parser.add_argument("--box", nargs=4, type=float, required=True,
                        metavar=("MIN_LAT", "MAX_LAT", "MIN_LON", "MAX_LON"))
    parser.add_argument("--ode-pt", action="append", default=[],
                        help=f"LRO product type to include; one of {sorted(ODE_PRODUCT_TYPES)}")
    parser.add_argument("--output", type=Path, required=True, help="manifest parquet path")
    parser.add_argument("--skip-ode", action="store_true", help="ISSDC only; no network")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    box = tuple(args.box)  # type: ignore[assignment]
    rows: list[dict] = []

    print(f"Region: lat {box[0]} .. {box[1]},  lon {box[2]} .. {box[3]}\n")

    print("ISSDC catalogue")
    issdc_diag = Diagnostics()
    files = sorted(args.issdc_dir.glob("*.geojson"))
    if not files:
        print(f"  no *.geojson under {args.issdc_dir} -- nothing to read")
    for path in files:
        sensor = _sensor_from_filename(path.name)
        before = len(rows)
        rows.extend(read_issdc_catalogue(path, sensor, issdc_diag, box))
        print(f"  {path.name:<46} sensor={sensor:<6} kept {len(rows) - before}")
    print(issdc_diag.report())

    if not args.skip_ode and args.ode_pt:
        print("\nODE / LRO catalogue")
        ode_diag = Diagnostics()
        for product_type in args.ode_pt:
            records = query_ode(product_type, box)
            before = len(rows)
            rows.extend(ode_rows(records, f"LRO_{product_type}", ode_diag))
            print(f"  {product_type:<10} returned {len(records):>5}  kept {len(rows) - before}")
        print(ode_diag.report())

    if not rows:
        print("\nNo rows. Manifest not written.")
        return 1

    import pandas as pd

    frame = pd.DataFrame(rows)

    # A product straddling a projection boundary is published in BOTH the
    # equatorial and the polar layer, so the same PRODUCT_ID arrives twice.
    # Keep the equatorial copy: its coordinates are native degrees and have not
    # been through the inverse projection, so it carries one less assumption.
    before = len(frame)
    frame["_prefer"] = (frame["source_crs"] != CRS_EQUATORIAL).astype(int)
    frame = (
        frame.sort_values(["product_id", "_prefer"])
        .drop_duplicates(subset=["product_id", "archive"], keep="first")
        .drop(columns="_prefer")
        .reset_index(drop=True)
    )
    if before != len(frame):
        print(
            f"\nDe-duplicated {before - len(frame)} rows "
            "published in more than one projection layer"
        )

    # ISSDC publishes "2021-10-23T00:27:46Z"; ODE publishes
    # "2022-06-18T11:53:28.071000Z". Both are ISO 8601 but they differ in
    # sub-second precision, and pandas >= 3 will not infer one format across
    # the mix -- without format="ISO8601" every row silently becomes NaT.
    for column in ("start_time", "stop_time"):
        frame[column] = pd.to_datetime(
            frame[column], errors="coerce", utc=True, format="ISO8601"
        )
        bad = int(frame[column].isna().sum())
        if bad:
            print(f"  WARNING: {column} unparseable on {bad}/{len(frame)} rows")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(args.output, index=False)

    print(f"\nWrote {len(frame)} rows -> {args.output}")
    print("\nBy sensor:")
    for sensor, group in frame.groupby("sensor"):
        resolved = int(group["geometry_resolved"].sum())
        print(f"  {sensor:<16} {len(group):>5} rows   illumination usable on {resolved}")
    print(
        "\nNOTE: rows are catalogue-derived. lines/samples/bands/data_type are absent\n"
        "      and must be filled by rescanning real labels through\n"
        "      lunar_reg.ingest.manifest.build_manifest after download."
    )
    return 0


def _sensor_from_filename(name: str) -> str:
    """Sensor tag from an ISSDC layer filename, e.g. ...ch2_ohr_cal... -> OHRC."""
    lowered = name.lower()
    for token, sensor in (("ohr", "OHRC"), ("tmc", "TMC2"), ("iir", "IIRS"), ("sar", "DFSAR")):
        if token in lowered:
            return sensor
    return "UNKNOWN"


if __name__ == "__main__":
    raise SystemExit(main())
