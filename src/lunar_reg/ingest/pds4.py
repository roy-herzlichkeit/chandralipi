"""PDS4 product access for OHRC / TMC-2 / IIRS.

A PDS4 product is a detached pair: an XML label plus a flat binary ``.IMG``.
GDAL's ``PDS4`` driver reads these when pointed at the **label**, which is the
route this module takes -- it gives windowed reads for free, and windowed reads
are the only reason large OHRC strips are workable at all.

Two facts established by probing GDAL 3.12 in this project:

1. **Open the label, never the ``.IMG``.** GDAL's extension table maps ``.img``
   to ``HFA`` (ERDAS Imagine), not to a planetary driver. Handing it the binary
   gets the wrong driver or an error.
2. **GDAL surfaces no label metadata as ordinary tags.** ``ds.tags()`` is empty
   for a PDS4 dataset; the full label is available in the ``xml:PDS4`` metadata
   domain, and everything else has to be parsed from the XML. Hence this module.

Trust boundary
--------------
Array structure (sizes, dtype, axis order, file name) is read against the
documented PDS4 schema and was cross-checked against GDAL's own reader. Geometry
and illumination fields are **not** verified -- see
:mod:`lunar_reg.ingest.fieldmap`. Anything derived from them is reported as
unresolved until a real label is probed.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from lunar_reg.ingest.fieldmap import ALL_FIELDS, Field, Provenance

logger = logging.getLogger(__name__)

_IMG_SUFFIXES = {".img", ".qub", ".dat"}
_LABEL_SUFFIXES = {".xml", ".lbl"}

#: PDS4 element_array data_type values -> numpy dtype strings.
#: These are the documented PDS4 enumerations; UnsignedLSB2 and IEEE754LSBSingle
#: were confirmed end-to-end against GDAL in this project's probe.
PDS4_DTYPES: dict[str, str] = {
    "UnsignedByte": "u1",
    "SignedByte": "i1",
    "UnsignedLSB2": "<u2",
    "UnsignedLSB4": "<u4",
    "UnsignedMSB2": ">u2",
    "UnsignedMSB4": ">u4",
    "SignedLSB2": "<i2",
    "SignedLSB4": "<i4",
    "SignedMSB2": ">i2",
    "SignedMSB4": ">i4",
    "IEEE754LSBSingle": "<f4",
    "IEEE754LSBDouble": "<f8",
    "IEEE754MSBSingle": ">f4",
    "IEEE754MSBDouble": ">f8",
}


def _localname(tag: str) -> str:
    """Strip the XML namespace, leaving the bare element name."""
    return tag.rsplit("}", 1)[-1]


def _iter_with_ancestors(root: ET.Element):
    """Yield ``(element, ancestor_localname_tuple)`` for the whole tree."""
    stack: list[tuple[ET.Element, tuple[str, ...]]] = [(root, ())]
    while stack:
        el, ancestors = stack.pop()
        yield el, ancestors
        chain = (*ancestors, _localname(el.tag))
        stack.extend((child, chain) for child in el)


def _resolve(root: ET.Element, paths: tuple[str, ...]) -> tuple[str | None, str | None]:
    """First value matching any candidate path.

    Returns ``(value, matched_path)``; ``(None, None)`` when nothing matched, so
    the caller can distinguish "absent from this label" from "mapped wrong".
    """
    for path in paths:
        parts = path.split("/")
        want = parts[-1]
        required = parts[:-1]
        for el, ancestors in _iter_with_ancestors(root):
            if _localname(el.tag) != want:
                continue
            if required and not _chain_contains(ancestors, required):
                continue
            if el.text and el.text.strip():
                return el.text.strip(), path
    return None, None


def _chain_contains(ancestors: tuple[str, ...], required: list[str]) -> bool:
    """Whether ``required`` appears in order (not necessarily contiguously)."""
    it = iter(ancestors)
    return all(any(a == r for a in it) for r in required)


def _coerce(value: str | None, dtype: str) -> Any:
    if value is None:
        return None
    try:
        if dtype == "float":
            return float(value)
        if dtype == "int":
            return int(float(value))
        if dtype == "datetime":
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        logger.debug("could not coerce %r to %s", value, dtype)
        return None
    return value


@dataclass
class AxisInfo:
    """One ``Axis_Array`` entry."""

    name: str
    elements: int
    sequence_number: int


@dataclass
class PDS4Product:
    """A PDS4 product's label metadata, with provenance tracking.

    ``resolved`` records which candidate path supplied each field, and
    ``unresolved`` lists mapped fields that no path matched. Both exist so a
    caller can tell a genuinely absent value from a wrong mapping.
    """

    label_path: Path
    image_path: Path
    values: dict[str, Any] = field(default_factory=dict)
    axes: list[AxisInfo] = field(default_factory=list)
    array_kind: str | None = None
    resolved: dict[str, str] = field(default_factory=dict)
    unresolved: list[str] = field(default_factory=list)
    sensor: str | None = None

    def __getitem__(self, key: str) -> Any:
        return self.values.get(key)

    @property
    def product_id(self) -> str | None:
        return self.values.get("product_id")

    @property
    def lines(self) -> int | None:
        return self._axis("Line")

    @property
    def samples(self) -> int | None:
        return self._axis("Sample")

    @property
    def bands(self) -> int:
        return self._axis("Band") or 1

    def _axis(self, name: str) -> int | None:
        for ax in self.axes:
            if ax.name.lower() == name.lower():
                return ax.elements
        return None

    @property
    def axis_order(self) -> str | None:
        """Axis names in label sequence, e.g. ``"Band,Line,Sample"``.

        For a 3D cube this *is* the interleave, and getting it wrong returns
        wrong pixels with no error. Never assume it; read it.
        """
        if not self.axes:
            return None
        return ",".join(a.name for a in sorted(self.axes, key=lambda a: a.sequence_number))

    @property
    def is_hyperspectral(self) -> bool:
        return self.bands > 1

    @property
    def numpy_dtype(self) -> str | None:
        return PDS4_DTYPES.get(self.values.get("data_type") or "")

    @property
    def geometry_resolved(self) -> bool:
        """Whether any unverified geometry field actually matched.

        ``False`` is the expected state until a real label has been probed.
        """
        return any(
            k in self.resolved
            for k in ("sun_azimuth_deg", "sun_elevation_deg", "incidence_angle_deg")
        )

    @property
    def megapixels(self) -> float | None:
        if self.lines is None or self.samples is None:
            return None
        return self.lines * self.samples / 1e6


#: Substring -> sensor key. Matched against the logical identifier and filename.
#: Derived from the instrument names in the problem statement, NOT from an
#: inspected product; a real product ID may not contain these tokens.
_SENSOR_TOKENS: tuple[tuple[str, str], ...] = (
    ("OHR", "OHRC"),
    ("IIR", "IIRS"),
    ("TMC", "TMC2"),
    ("NAC", "LRO_NAC"),
)


def guess_sensor(*texts: str | None) -> str | None:
    """Best-effort sensor identification from identifiers and filenames.

    Heuristic, not authoritative: prefer the ``sensor`` argument to
    :func:`read_label` when the caller already knows.
    """
    joined = " ".join(t for t in texts if t).upper()
    for token, sensor in _SENSOR_TOKENS:
        if token in joined:
            return sensor
    return None


def _find_image(label_path: Path, file_name: str | None) -> Path:
    if file_name:
        candidate = label_path.parent / file_name
        if candidate.exists():
            return candidate
        logger.warning(
            "label %s names data file %r which is not present next to it",
            label_path.name, file_name,
        )
        return candidate
    for p in sorted(label_path.parent.glob(label_path.stem + ".*")):
        if p.suffix.lower() in _IMG_SUFFIXES:
            return p
    return label_path.with_suffix(".img")


def read_label(
    label_path: str | Path,
    fields: tuple[Field, ...] = ALL_FIELDS,
    sensor: str | None = None,
) -> PDS4Product:
    """Parse a PDS4 XML label.

    Every mapped field is attempted; whichever candidate path matched is
    recorded in :attr:`PDS4Product.resolved`, and fields that matched nothing
    land in :attr:`PDS4Product.unresolved`. Unverified fields failing to resolve
    is the *expected* outcome until the mapping is confirmed against a real
    product -- it is logged at debug level, not as an error.
    """
    label_path = Path(label_path)
    root = ET.parse(label_path).getroot()

    values: dict[str, Any] = {}
    resolved: dict[str, str] = {}
    unresolved: list[str] = []

    for f in fields:
        raw, matched = _resolve(root, f.paths)
        values[f.name] = _coerce(raw, f.dtype)
        if matched is not None:
            resolved[f.name] = matched
        else:
            unresolved.append(f.name)

    axes = _read_axes(root)
    array_kind = _read_array_kind(root)

    product = PDS4Product(
        label_path=label_path,
        image_path=_find_image(label_path, values.get("file_name")),
        values=values,
        axes=axes,
        array_kind=array_kind,
        resolved=resolved,
        unresolved=unresolved,
        sensor=sensor or guess_sensor(values.get("product_id"), label_path.name),
    )

    missing_unverified = [
        n for n in unresolved
        if (fm := next((f for f in fields if f.name == n), None))
        and fm.provenance is Provenance.UNVERIFIED
    ]
    if missing_unverified:
        logger.debug(
            "%s: %d unverified field(s) did not resolve (%s). Expected until the "
            "mapping is confirmed -- run `lunar-reg probe-label` on a real product.",
            label_path.name, len(missing_unverified), ", ".join(missing_unverified[:4]),
        )
    return product


def _read_axes(root: ET.Element) -> list[AxisInfo]:
    """Read every ``Axis_Array``. Structural PDS4; verified against GDAL."""
    axes: list[AxisInfo] = []
    for el in root.iter():
        if _localname(el.tag) != "Axis_Array":
            continue
        parts = {_localname(c.tag): (c.text or "").strip() for c in el}
        try:
            axes.append(
                AxisInfo(
                    name=parts.get("axis_name", "?"),
                    elements=int(parts["elements"]),
                    sequence_number=int(parts.get("sequence_number", len(axes) + 1)),
                )
            )
        except (KeyError, ValueError):
            logger.warning("skipping malformed Axis_Array in label")
    return sorted(axes, key=lambda a: a.sequence_number)


def _read_array_kind(root: ET.Element) -> str | None:
    """The ``Array_*`` element name, e.g. ``Array_2D_Image``/``Array_3D_Spectrum``."""
    for el in root.iter():
        name = _localname(el.tag)
        if name.startswith("Array_"):
            return name
    return None


def open_product(path: str | Path):
    """Open a product for windowed reading, returning the rasterio dataset.

    Pass the **label**. If handed a ``.IMG`` this looks for the sibling label
    and uses that instead, because GDAL resolves the ``.img`` extension to the
    ERDAS ``HFA`` driver rather than to ``PDS4``.

    The caller owns the handle; use it as a context manager. Nothing is read
    into memory here -- see :mod:`lunar_reg.ingest.tiling`.
    """
    import rasterio

    path = Path(path)
    if path.suffix.lower() in _IMG_SUFFIXES:
        for suffix in _LABEL_SUFFIXES:
            candidate = path.with_suffix(suffix)
            if candidate.exists():
                logger.info("opening via label %s rather than %s", candidate.name, path.name)
                path = candidate
                break
        else:
            logger.warning(
                "no sibling label found for %s; GDAL will pick a driver by "
                "extension (.img resolves to HFA, not PDS4)", path.name,
            )
    return rasterio.open(path)


def label_xml_from_dataset(dataset) -> str | None:
    """Recover the full label XML from an already-open PDS4 dataset.

    GDAL exposes it in the ``xml:PDS4`` metadata domain (confirmed in-session).
    Useful when a dataset is open and re-reading the label file is wasteful.
    """
    tags = dataset.tags(ns="xml:PDS4")
    return tags.get("xml:PDS4") or next(iter(tags.values()), None)
