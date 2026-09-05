"""Discover a real label's structure instead of guessing at it.

The geometry and mission-specific entries in :mod:`lunar_reg.ingest.fieldmap`
are unverified placeholders. This module is how they get replaced with fact: it
dumps the actual element tree of a real PDS4 label, highlights the elements that
look like illumination or coordinate values, and emits a ready-to-paste
:class:`~lunar_reg.ingest.fieldmap.Field` block.

Workflow once a real product is in hand::

    lunar-reg probe-label data/raw/<product>.xml --suggest

Then paste the emitted block over the UNVERIFIED section of ``fieldmap.py``,
and the loader and manifest pick it up with no other change.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _namespace(tag: str) -> str | None:
    return tag[1:].split("}", 1)[0] if tag.startswith("{") else None


#: Substrings that suggest an element carries illumination geometry.
_ILLUMINATION_HINTS = ("solar", "sun", "incidence", "emission", "phase", "illum")
#: Substrings that suggest an element carries a coordinate.
_COORDINATE_HINTS = ("latitude", "longitude", "lat", "lon", "corner", "coordinate")
#: Substrings that suggest an element carries a time.
_TIME_HINTS = ("time", "date", "utc", "sclk")


@dataclass(frozen=True)
class LabelElement:
    """One leaf element found in a label."""

    path: str
    localname: str
    namespace: str | None
    value: str
    is_numeric: bool

    @property
    def category(self) -> str | None:
        low = self.localname.lower()
        if any(h in low for h in _ILLUMINATION_HINTS):
            return "illumination"
        if any(h in low for h in _COORDINATE_HINTS):
            return "coordinate"
        if any(h in low for h in _TIME_HINTS):
            return "time"
        return None


def probe_label(label_path: str | Path) -> list[LabelElement]:
    """Return every leaf element in a label, with its full ancestor path."""
    root = ET.parse(Path(label_path)).getroot()
    found: list[LabelElement] = []

    def walk(el: ET.Element, chain: tuple[str, ...]) -> None:
        here = (*chain, _localname(el.tag))
        children = list(el)
        if not children:
            text = (el.text or "").strip()
            if text:
                try:
                    float(text)
                    numeric = True
                except ValueError:
                    numeric = False
                found.append(
                    LabelElement(
                        path="/".join(here),
                        localname=_localname(el.tag),
                        namespace=_namespace(el.tag),
                        value=text,
                        is_numeric=numeric,
                    )
                )
        for child in children:
            walk(child, here)

    walk(root, ())
    return found


def namespaces_in(label_path: str | Path) -> dict[str, int]:
    """Namespace URIs present in a label, with element counts.

    A mission's own namespace showing up here (alongside the base
    ``pds.nasa.gov/pds4/pds/v1``) is the signal that mission-specific geometry
    exists and where to look for it.
    """
    counts: dict[str, int] = {}
    for el in ET.parse(Path(label_path)).getroot().iter():
        ns = _namespace(el.tag) or "(none)"
        counts[ns] = counts.get(ns, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


def format_report(label_path: str | Path, show_all: bool = False) -> str:
    """Human-readable structure dump, grouped by what the elements look like."""
    label_path = Path(label_path)
    elements = probe_label(label_path)
    namespaces = namespaces_in(label_path)

    lines = [f"label: {label_path}", f"leaf elements: {len(elements)}", "", "namespaces:"]
    lines += [f"  {n:70s} {c:5d} elements" for n, c in namespaces.items()]

    for category, heading in (
        ("illumination", "ILLUMINATION-LIKE (candidates for sun angle fields)"),
        ("coordinate", "COORDINATE-LIKE (candidates for footprint fields)"),
        ("time", "TIME-LIKE (candidates for acquisition time)"),
    ):
        hits = [e for e in elements if e.category == category]
        lines += ["", f"{heading}: {len(hits)}"]
        lines += [f"  {e.path}\n      = {e.value[:60]}" for e in hits] or ["  (none found)"]

    if show_all:
        lines += ["", f"ALL {len(elements)} LEAF ELEMENTS:"]
        lines += [f"  {e.path} = {e.value[:50]}" for e in elements]

    return "\n".join(lines)


def suggest_fieldmap(label_path: str | Path) -> str:
    """Emit a ``Field`` block matching what this label actually contains.

    Paste over the UNVERIFIED section of :mod:`lunar_reg.ingest.fieldmap`. The
    emitted paths are the real ones from this product, so the resulting entries
    are ``Provenance.VERIFIED`` for this mission -- adjust if other products
    from the same instrument differ.
    """
    elements = probe_label(label_path)

    def pick(*hints: str) -> list[LabelElement]:
        return [
            e for e in elements
            if e.is_numeric and any(h in e.localname.lower() for h in hints)
        ]

    wanted = (
        ("sun_azimuth_deg", ("azimuth",)),
        ("sun_elevation_deg", ("elevation",)),
        ("incidence_angle_deg", ("incidence",)),
        ("emission_angle_deg", ("emission",)),
        ("phase_angle_deg", ("phase",)),
    )

    lines = [
        "# Generated by `lunar-reg probe-label --suggest` from:",
        f"#   {Path(label_path).name}",
        "# Paths below are read from a real product, so they are VERIFIED for it.",
        "# Confirm they hold across other products from the same instrument.",
        "GEOMETRY_FIELDS: tuple[Field, ...] = (",
    ]
    for name, hints in wanted:
        hits = pick(*hints)
        if hits:
            best = hits[0]
            trail = "/".join(best.path.split("/")[-2:])
            lines.append(
                f'    Field("{name}", ("{trail}",), Provenance.VERIFIED, dtype="float"),'
            )
        else:
            lines.append(f"    # {name}: NOT FOUND in this label -- omit or check manually.")
    lines.append(")")

    coords = [e for e in elements if e.category == "coordinate" and e.is_numeric]
    lines += ["", f"# {len(coords)} coordinate-like numeric element(s) found:"]
    lines += [f"#   {e.path} = {e.value}" for e in coords] or ["#   (none)"]
    return "\n".join(lines)
