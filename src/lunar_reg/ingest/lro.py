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
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

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
    "PRODUCT_ID", "INSTRUMENT_ID", "INSTRUMENT_HOST_NAME", "MISSION_NAME",
    "TARGET_NAME", "START_TIME", "STOP_TIME",
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
    image_path: Path
    fmt: str
    values: dict[str, Any] = field(default_factory=dict)
    keywords: dict[str, str] = field(default_factory=dict)
    resolved: dict[str, str] = field(default_factory=dict)
    unresolved: list[str] = field(default_factory=list)
    sensor: str = "LRO_NAC"

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
        return LROProduct(
            label_path=parsed.label_path,
            image_path=parsed.image_path,
            fmt=PDS4,
            values=parsed.values,
            resolved=parsed.resolved,
            unresolved=parsed.unresolved,
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


def _pds3_image_path(label_path: Path, keywords: dict[str, str]) -> Path:
    """Resolve ``^IMAGE`` to a file, or fall back to a sibling ``.IMG``.

    ``^IMAGE`` may be ``("file.img",1)``, ``"file.img"``, or a bare record
    number for an attached label (in which case the data is in the label file
    itself).
    """
    pointer = keywords.get("^IMAGE", "")
    match = re.search(r'"([^"]+)"', pointer)
    if match:
        return label_path.parent / match.group(1)
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
    return {
        "product_id": product["product_id"],
        "sensor": product.sensor,
        "archive": "lro",
        "label_path": str(product.label_path),
        "image_path": str(product.image_path),
        "lines": product["lines"],
        "samples": product["samples"],
        "bands": product["bands"] or 1,
        "array_kind": None,
        "axis_order": None,
        "data_type": product["sample_type"],
        "numpy_dtype": None,
        "megapixels": (
            product["lines"] * product["samples"] / 1e6
            if product["lines"] and product["samples"] else None
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
        "footprint_resolved": product["min_lat"] is not None,
        "unresolved_fields": ",".join(product.unresolved),
    }


def scan_lro_directory(root: str | Path, strict: bool = False):
    """Parse every LRO label under ``root`` into a manifest DataFrame."""
    import pandas as pd

    from lunar_reg.ingest.manifest import COLUMNS

    root = Path(root)
    candidates: set[Path] = set()
    for pattern in ("*.lbl", "*.LBL", "*.xml", "*.XML"):
        candidates.update(root.rglob(pattern))

    rows = []
    for path in sorted(candidates):
        try:
            rows.append(lro_to_row(read_lro_label(path)))
        except Exception as exc:  # noqa: BLE001 - skip unreadable labels
            if strict:
                raise
            logger.warning("could not parse %s: %s", path.name, exc)

    frame = pd.DataFrame(rows, columns=list(COLUMNS))
    for col in ("start_time", "stop_time"):
        frame[col] = pd.to_datetime(frame[col], errors="coerce", utc=True)
    logger.info("scanned %d LRO product(s) from %s", len(frame), root)
    return frame
