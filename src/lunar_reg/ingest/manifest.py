"""One table describing every product available to the pipeline.

Scanning directories of labels into a DataFrame and persisting it as Parquet is
what makes pair selection cheap: footprint overlap, sensor pairing and sun-angle
difference all become table operations instead of repeated XML parsing.

Honesty columns
---------------
Two columns exist specifically so that unverified metadata cannot masquerade as
fact:

``geometry_resolved``
    ``True`` only if at least one illumination field actually matched a path in
    that product's label. ``False`` is the expected value until the mapping in
    :mod:`lunar_reg.ingest.fieldmap` is confirmed against a real product.
``unresolved_fields``
    Comma-joined names of every mapped field that matched nothing.

Filter on ``geometry_resolved`` before using any sun-angle column, and never
report a sun-angle-conditioned result from rows where it is ``False``.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from pathlib import Path

from lunar_reg.ingest.pds4 import PDS4Product, read_label

logger = logging.getLogger(__name__)

#: Label suffixes scanned by :func:`scan_directory`.
LABEL_GLOBS: tuple[str, ...] = ("*.xml", "*.XML", "*.lbl", "*.LBL")

#: Column order for the manifest.
COLUMNS: tuple[str, ...] = (
    "product_id", "sensor", "archive", "label_path", "image_path",
    "lines", "samples", "bands", "array_kind", "axis_order", "data_type", "numpy_dtype",
    "megapixels", "start_time", "stop_time",
    "sun_azimuth_deg", "sun_elevation_deg", "incidence_angle_deg",
    "emission_angle_deg", "phase_angle_deg",
    # The four real corners, carried through rather than reduced to a box.
    # MEASURED 2026-09-05: collapsing a rotated pushbroom footprint to its
    # lat/lon bounding box inflates its area by 3.9-4.2x on real OHRC strips
    # (78.9 -> 309.0 km^2) and 2.2-2.3x on real TMC-2 frames. The manifest used
    # to keep only the box, so every overlap computed from a manifest was that
    # much too large. The box is retained because it is still the only geometry
    # available when a label resolves no corners.
    *(f"corner{i}_{c}" for i in range(1, 5) for c in ("lat", "lon")),
    "min_lat", "max_lat", "min_lon", "max_lon",
    "geometry_resolved", "footprint_resolved", "unresolved_fields",
)


def _corners(product: PDS4Product) -> tuple[float | None, ...]:
    """Bounding box from whichever corner fields resolved, else all ``None``."""
    lats = [product[f"corner{i}_lat"] for i in range(1, 5)]
    lons = [product[f"corner{i}_lon"] for i in range(1, 5)]
    lats = [v for v in lats if v is not None]
    lons = [v for v in lons if v is not None]
    if not lats or not lons:
        return (None, None, None, None)
    return (min(lats), max(lats), min(lons), max(lons))


def product_to_row(product: PDS4Product, archive: str = "chandrayaan2") -> dict:
    """Flatten one parsed product into a manifest row."""
    min_lat, max_lat, min_lon, max_lon = _corners(product)
    return {
        "product_id": product.product_id,
        "sensor": product.sensor,
        "archive": archive,
        "label_path": str(product.label_path),
        "image_path": str(product.image_path),
        "lines": product.lines,
        "samples": product.samples,
        "bands": product.bands,
        "array_kind": product.array_kind,
        "axis_order": product.axis_order,
        "data_type": product["data_type"],
        "numpy_dtype": product.numpy_dtype,
        "megapixels": product.megapixels,
        "start_time": product["start_time"],
        "stop_time": product["stop_time"],
        "sun_azimuth_deg": product["sun_azimuth_deg"],
        "sun_elevation_deg": product["sun_elevation_deg"],
        "incidence_angle_deg": product["incidence_angle_deg"],
        "emission_angle_deg": product["emission_angle_deg"],
        "phase_angle_deg": product["phase_angle_deg"],
        **{
            f"corner{i}_{short}": product[f"corner{i}_{short}"]
            for i in range(1, 5)
            for short in ("lat", "lon")
        },
        "min_lat": min_lat,
        "max_lat": max_lat,
        "min_lon": min_lon,
        "max_lon": max_lon,
        "geometry_resolved": product.geometry_resolved,
        "footprint_resolved": min_lat is not None,
        "unresolved_fields": ",".join(product.unresolved),
    }


def build_manifest(products: Iterable[PDS4Product], archive: str = "chandrayaan2"):
    """Assemble parsed products into a :class:`pandas.DataFrame`."""
    import pandas as pd

    rows = [product_to_row(p, archive) for p in products]
    frame = pd.DataFrame(rows, columns=list(COLUMNS))
    for col in ("start_time", "stop_time"):
        frame[col] = pd.to_datetime(frame[col], errors="coerce", utc=True)
    return frame


def find_labels(root: str | Path, globs: Sequence[str] = LABEL_GLOBS) -> list[Path]:
    """Every label file under ``root``, recursively and de-duplicated."""
    root = Path(root)
    found: set[Path] = set()
    for pattern in globs:
        found.update(root.rglob(pattern))
    return sorted(found)


def scan_directory(
    root: str | Path,
    archive: str = "chandrayaan2",
    sensor: str | None = None,
    strict: bool = False,
):
    """Parse every label under ``root`` into a manifest DataFrame.

    Unparseable labels are logged and skipped so one malformed product cannot
    abort a scan of hundreds; pass ``strict=True`` to raise instead.
    """
    labels = find_labels(root)
    logger.info("scanning %d label(s) under %s", len(labels), root)

    products: list[PDS4Product] = []
    failed: list[tuple[Path, str]] = []
    for path in labels:
        try:
            products.append(read_label(path, sensor=sensor))
        except Exception as exc:  # noqa: BLE001 - one bad label must not stop the scan
            if strict:
                raise
            failed.append((path, f"{type(exc).__name__}: {exc}"))
            logger.warning("could not parse %s: %s", path.name, exc)

    frame = build_manifest(products, archive=archive)
    if failed:
        logger.warning("%d of %d label(s) failed to parse", len(failed), len(labels))
    if len(frame) and not frame["geometry_resolved"].any():
        logger.warning(
            "no product resolved any illumination field. The geometry mapping in "
            "fieldmap.py is still unverified -- run `lunar-reg probe-label` on one "
            "of these labels and paste the suggested block in."
        )
    return frame


def write_manifest(frame, path: str | Path) -> Path:
    """Persist a manifest to Parquet, creating parent directories."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)
    logger.info("wrote manifest with %d row(s) to %s", len(frame), path)
    return path


def read_manifest(path: str | Path):
    """Load a manifest previously written by :func:`write_manifest`."""
    import pandas as pd

    return pd.read_parquet(path)


def manifest_summary(frame) -> str:
    """Short text summary, including how much metadata is still unverified."""
    if len(frame) == 0:
        return "manifest is empty"

    lines = [f"{len(frame)} product(s)"]
    for sensor, count in frame["sensor"].value_counts(dropna=False).items():
        lines.append(f"  {str(sensor):10s} {count}")

    geom = int(frame["geometry_resolved"].sum())
    foot = int(frame["footprint_resolved"].sum())
    lines += [
        "",
        f"illumination metadata resolved: {geom}/{len(frame)}",
        f"footprint metadata resolved:    {foot}/{len(frame)}",
    ]
    if geom == 0 or foot == 0:
        lines += [
            "",
            "WARNING: unresolved geometry means the fieldmap is still guessing.",
            "Run: lunar-reg probe-label <a real label> --suggest",
        ]
    return "\n".join(lines)
