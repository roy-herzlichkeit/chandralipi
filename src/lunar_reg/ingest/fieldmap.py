"""Declarative map from PDS4 label elements to manifest fields.

Why this file exists
--------------------
PDS4 labels are heavily namespaced XML. The *structural* parts are a published
standard and are safe to code against. The *geometry and mission* parts live in
discipline dictionaries and mission-specific namespaces whose element names
differ per mission, and guessing them produces a loader that silently returns
``None`` -- or worse, plausible wrong numbers.

So every field carries an explicit :class:`Provenance`, and the loader records
which candidate path actually matched. Nothing here is trusted silently.

What has actually been verified
-------------------------------
The fields marked :attr:`Provenance.VERIFIED` were confirmed in-session by
hand-writing a PDS4 label to the documented schema and having GDAL's
independent PDS4 driver read it back correctly (right shape, dtype, and pixel
values). That is real cross-validation of the structural layer.

The fields marked :attr:`Provenance.UNVERIFIED` are **placeholders**. No
Chandrayaan-2 or LRO product has been inspected. Their candidate paths are
starting guesses, not knowledge, and the manifest reports them as unresolved
until a real label confirms or replaces them. Run ``lunar-reg probe-label`` on
a real product to generate the correct mapping -- see
:mod:`lunar_reg.ingest.probe`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Provenance(str, Enum):
    """How much the mapping for a field can be trusted."""

    #: Documented PDS4 standard, and exercised against GDAL's PDS4 driver in
    #: this project. Safe to rely on.
    VERIFIED = "verified"
    #: Documented in the PDS4 Information Model, but not exercised here. The
    #: element name is standard; presence in any given product is not.
    DOCUMENTED = "documented"
    #: Mission- or discipline-specific. The candidate paths are GUESSES.
    #: Must be confirmed against a real label before the value is trusted.
    UNVERIFIED = "unverified"


@dataclass(frozen=True)
class Field:
    """One manifest column and the label paths that might supply it.

    ``paths`` are matched by *local* element name (namespace stripped), tried in
    order. A path may be a single name (``"logical_identifier"``, matched
    anywhere in the tree) or a slash-joined ancestor chain
    (``"Time_Coordinates/start_date_time"``) which additionally requires those
    ancestors, so a name that recurs in several contexts can be disambiguated.
    """

    name: str
    paths: tuple[str, ...]
    provenance: Provenance
    dtype: str = "str"  # str | int | float | datetime
    note: str = ""

    @property
    def trusted(self) -> bool:
        return self.provenance is not Provenance.UNVERIFIED


# ---------------------------------------------------------------------------
# Structural / identification fields.
#
# These come from the PDS4 Product_Observational schema. `logical_identifier`,
# `file_name`, `Axis_Array/elements`, `data_type` and `axis_index_order` were
# all exercised against GDAL's PDS4 driver in this project's probe.
# ---------------------------------------------------------------------------
IDENTIFICATION_FIELDS: tuple[Field, ...] = (
    Field("product_id", ("Identification_Area/logical_identifier",), Provenance.VERIFIED),
    Field("version_id", ("Identification_Area/version_id",), Provenance.VERIFIED),
    Field("title", ("Identification_Area/title",), Provenance.VERIFIED),
    Field(
        "information_model_version",
        ("Identification_Area/information_model_version",),
        Provenance.VERIFIED,
        note="Useful when a parse fails -- IM version drives schema differences.",
    ),
    Field(
        "instrument",
        ("Observing_System_Component/name",),
        Provenance.DOCUMENTED,
        note="Observing_System may list several components (spacecraft AND "
        "instrument); the loader keeps all and the sensor is inferred separately.",
    ),
    Field("target", ("Target_Identification/name",), Provenance.DOCUMENTED),
)

# ---------------------------------------------------------------------------
# Time. Standard PDS4, in Observation_Area/Time_Coordinates.
# ---------------------------------------------------------------------------
TIME_FIELDS: tuple[Field, ...] = (
    Field(
        "start_time",
        ("Time_Coordinates/start_date_time",),
        Provenance.DOCUMENTED,
        dtype="datetime",
        note="ISO 8601, nominally UTC with a trailing Z.",
    ),
    Field(
        "stop_time",
        ("Time_Coordinates/stop_date_time",),
        Provenance.DOCUMENTED,
        dtype="datetime",
    ),
)

# ---------------------------------------------------------------------------
# Array structure. All VERIFIED -- the probe confirmed GDAL reads a label built
# to exactly this shape, for both Array_2D_Image and Array_3D_Spectrum.
#
# NOTE the ordering hazard: axis_index_order plus the sequence of Axis_Array
# elements is what determines band interleave for a 3D cube. Reading a
# band-sequential cube as band-interleaved produces NO error, just wrong
# numbers -- this was demonstrated in-session. Never assume an interleave.
# ---------------------------------------------------------------------------
ARRAY_FIELDS: tuple[Field, ...] = (
    Field("file_name", ("File/file_name",), Provenance.VERIFIED),
    Field(
        "data_type",
        ("Element_Array/data_type",),
        Provenance.VERIFIED,
        note="PDS4 enumeration, e.g. UnsignedLSB2, IEEE754LSBSingle.",
    ),
    Field("axis_index_order", ("axis_index_order",), Provenance.VERIFIED),
    Field("array_offset", ("offset",), Provenance.DOCUMENTED, dtype="int"),
)

# ---------------------------------------------------------------------------
# Geometry -- illumination and footprint.
#
# VERIFIED 2026-09-05 against a real Chandrayaan-2 OHRC label
# (ch2_ohr_ncp_20260103T0609041371_d_img_d18.xml, calibrated collection),
# using `lunar-reg probe-label`.
#
# The sun angles and all eight corner coordinates resolved. They live in ISRO's
# own Mission_Area namespace (https://isda.issdc.gov.in/pds4/isda/v1), not in
# the PDS4 geometry discipline dictionary:
#
#   Observation_Area/Mission_Area/Product_Parameters/sun_azimuth
#   Observation_Area/Mission_Area/Product_Parameters/sun_elevation
#   Observation_Area/Mission_Area/Geometry_Parameters/System_Level_Coordinates/*
#
# Three fields did NOT resolve and remain UNVERIFIED below: incidence (present
# under a different name, now added), emission and phase angle (absent from this
# label entirely -- one label is not evidence of absence across the archive).
#
# The pipeline's illumination handling does not depend on these values -- CLAHE
# and shadow suppression are unconditional -- so an unresolved geometry block
# degrades reporting, not registration.
# ---------------------------------------------------------------------------
GEOMETRY_FIELDS: tuple[Field, ...] = (
    Field(
        "sun_azimuth_deg",
        ("sun_azimuth", "sub_solar_azimuth", "solar_azimuth", "SUB_SOLAR_AZIMUTH"),
        Provenance.VERIFIED,
        dtype="float",
        note="Resolves from Mission_Area/Product_Parameters/sun_azimuth "
        "(observed 342.040290 on the reference OHRC label). The azimuth "
        "REFERENCE DIRECTION is still unconfirmed -- the label does not state "
        "whether it is clockwise from north -- and that matters for any angular "
        "difference between two acquisitions.",
    ),
    Field(
        "sun_elevation_deg",
        ("sun_elevation", "sub_solar_elevation", "solar_elevation"),
        Provenance.VERIFIED,
        dtype="float",
        note="Resolves from Mission_Area/Product_Parameters/sun_elevation "
        "(observed 6.729185). Confirmed complementary with solar_incidence on "
        "that label: 6.729185 + 83.270815 = 90 exactly.",
    ),
    Field(
        "incidence_angle_deg",
        ("solar_incidence", "incidence_angle", "INCIDENCE_ANGLE"),
        Provenance.VERIFIED,
        dtype="float",
        note="ISRO names this `solar_incidence`, not `incidence_angle` -- the "
        "original guess missed it. Observed 83.270815, exactly 90 minus the "
        "sun elevation on the same label.",
    ),
    Field(
        "emission_angle_deg",
        ("emission_angle", "EMISSION_ANGLE"),
        Provenance.UNVERIFIED,
        dtype="float",
        note="NOT PRESENT in the reference OHRC label. Proxy for viewpoint "
        "difference between acquisitions. One label is not evidence of absence "
        "across the archive; re-probe a TMC-2 or IIRS product before removing.",
    ),
    Field(
        "phase_angle_deg",
        ("phase_angle", "PHASE_ANGLE"),
        Provenance.UNVERIFIED,
        dtype="float",
        note="NOT PRESENT in the reference OHRC label. See emission_angle_deg.",
    ),
)

#: Footprint corners. VERIFIED 2026-09-05: all eight resolved from the reference
#: OHRC label under
#: ``Observation_Area/Mission_Area/Geometry_Parameters/System_Level_Coordinates``,
#: named exactly ``upper_left_latitude`` and so on.
#:
#: Corner *ordering* is also now settled, and it is not the order the names
#: suggest. ``corner1..corner4`` are upper-left, upper-right, lower-**left**,
#: lower-**right**, so traversing them in numeric order describes a
#: self-intersecting bow-tie rather than a ring.
#: :func:`lunar_reg.ingest.overlap.footprint_from_row` already accounts for this
#: by traversing 1, 2, 4, 3, and that was checked against the real label: the
#: correct traversal gives 78.89 km^2 for a 3 km x 25 km OHRC strip, against
#: 0.07 km^2 for the naive one. Do not "simplify" that reordering away.
#:
#: The label also carries a second, identical copy of the same four corners
#: under ``Refined_Corner_Coordinates``. On the reference product the two agree
#: to every decimal place, so which one is authoritative when they diverge is
#: UNKNOWN -- this loader reads ``System_Level_Coordinates``.
FOOTPRINT_FIELDS: tuple[Field, ...] = (
    # Generated rather than written out: 8 near-identical entries.
    *(
        Field(
            f"{corner}_{short}",
            (f"{position}_{full}", f"{corner.replace('corner', 'corner_')}_{full}"),
            Provenance.VERIFIED,
            dtype="float",
        )
        for corner, position in (
            ("corner1", "upper_left"),
            ("corner2", "upper_right"),
            ("corner3", "lower_left"),
            ("corner4", "lower_right"),
        )
        for short, full in (("lat", "latitude"), ("lon", "longitude"))
    ),
)

ALL_FIELDS: tuple[Field, ...] = (
    IDENTIFICATION_FIELDS + TIME_FIELDS + ARRAY_FIELDS + GEOMETRY_FIELDS + FOOTPRINT_FIELDS
)

FIELDS_BY_NAME: dict[str, Field] = {f.name: f for f in ALL_FIELDS}

#: Fields whose mapping is a guess. The manifest reports these separately so an
#: unresolved geometry block is visible rather than silently absent.
UNVERIFIED_FIELD_NAMES: tuple[str, ...] = tuple(
    f.name for f in ALL_FIELDS if f.provenance is Provenance.UNVERIFIED
)


def summary() -> str:
    """Human-readable provenance breakdown, for the CLI and for reports."""
    counts: dict[str, int] = {}
    for f in ALL_FIELDS:
        counts[f.provenance.value] = counts.get(f.provenance.value, 0) + 1
    lines = [f"{len(ALL_FIELDS)} mapped fields: " + ", ".join(
        f"{n} {k}" for k, n in sorted(counts.items())
    )]
    lines.append("")
    lines.append("UNVERIFIED (candidate paths are guesses; confirm before trusting):")
    for f in ALL_FIELDS:
        if f.provenance is Provenance.UNVERIFIED:
            lines.append(f"  {f.name:22s} <- {' | '.join(f.paths)}")
    return "\n".join(lines)
