"""The per-observation GEOMETRY grid that ships inside every Chandrayaan-2 product.

What this file is
-----------------
Every ``*_d_img_d18.zip`` carries, alongside the image, a
``geometry/<level>/<date>/<product>_g_grd_d18.csv`` and its own PDS4 label. The
label declares a four-column delimited table -- ``Longitude``, ``Latitude``,
``Pixel``, ``Scan`` -- and this module reads that declaration rather than
assuming a column order.

The rows form a **rectangular grid of image points**, not a per-scan-line list:
``Pixel`` runs across track and ``Scan`` runs along track, both 0-based, both
sampled every 100 with the final index forced to the last real one so the grid
always reaches the image edge. Two products were measured in-session:

===============  ==================  ===============  ==============
product          image (lines x smp) grid (scan x px)  data rows
===============  ==================  ===============  ==============
OHRC ...1371     101074 x 12000      1012 x 121        122452
TMC-2 nadir      148108 x 4000       1483 x 41         60803
===============  ==================  ===============  ==============

In both, ``max(Scan) == lines - 1`` and ``max(Pixel) == samples - 1``, and the
four grid corners reproduce the label's ``isda:Refined_Corner_Coordinates``
exactly -- which is to say the four corners
:func:`~lunar_reg.ingest.overlap.geographic_to_pixel_transform` fits a
homography to are literally four of these 122452 points. The grid is a strict
superset of the corner footprint, so nothing is lost by preferring it.

Why it is worth preferring
--------------------------
Measured in-session against the two products above, by fitting the four-corner
homography exactly as ``geographic_to_pixel_transform`` does and evaluating it
at every grid point (corners reproduce to ~1e-10 px, so the fit itself is
sound):

* OHRC ...1371  -- median 2554.6 px, max 3412.8 px error (853 m at 0.25 m/px)
* TMC-2 nadir   -- median 2527.3 px, max 3372.9 px error (18.5 km at 5.48 m/px)

Most of that is **not** body curvature. The physical bow of the ground track off
the corner-to-corner chord is only ~106 cross-track px on the TMC-2 strip. The
error is dominated by the homography's projective term: the footprint quad is a
trapezoid (its bottom edge spans 0.794 deg of longitude against the top edge's
0.723 deg), so ``getPerspectiveTransform`` invents an along-track foreshortening
that a pushbroom strip with a constant line period does not have. A plain affine
least-squares fit to the *same* four corners measures median 118.6 px / max
206.3 px on TMC-2 -- an order of magnitude better than the homography. That is
worth knowing on its own, but the grid removes the question entirely.

Trust boundary
--------------
Field names, order and types come from the product's own label, and the label
elements used here are the plain PDS4 ``Table_Delimited`` structure. What is
**not** established is anything the two inspected products did not exercise:
antimeridian wrap, a non-100 sampling step, a grid whose ``Scan`` axis is not
monotonic, and the meaning of the geodetic datum the coordinates are on. Those
are marked UNVERIFIED at the point they matter, not in a blanket disclaimer.

No row is ever silently dropped. Every parse outcome is classified into a
:class:`GridStatus`, counted, and given a retained sample -- see
:class:`GeometryGridDiagnostics`.

Wiring
------
:mod:`lunar_reg.ingest.overlap` is deliberately untouched. :func:`lonlat_to_pixel`
is the replacement for ``geographic_to_pixel_transform`` and
:func:`polygon_to_pixel_window` here has the same return contract as the one
there, so a caller can swap either in. Because of that name collision, this
module's ``polygon_to_pixel_window`` is intentionally *not* re-exported from
``lunar_reg.ingest``; import it from this module explicitly, so it is always
obvious at the call site which of the two is in use.
"""

from __future__ import annotations

import csv
import logging
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import numpy as np

from lunar_reg.ingest.fieldmap import Provenance

logger = logging.getLogger(__name__)

#: Field names declared by ``Field_Delimited/name`` in the geometry labels of
#: both inspected products, in ``field_number`` order. VERIFIED: read from
#: ``ch2_ohr_ncp_20260103T0609041371_g_grd_d18.xml`` and
#: ``ch2_tmc_ncn_20260813T0627378557_g_grd_d18.xml``, and matching the CSV
#: header line byte for byte. The loader still reads the label; this tuple is
#: only the fallback used when a label is not supplied.
GEOMETRY_FIELD_NAMES: tuple[str, ...] = ("Longitude", "Latitude", "Pixel", "Scan")

#: Provenance of that fallback ordering.
GEOMETRY_FIELD_PROVENANCE = Provenance.VERIFIED

#: A longitude span wider than this in a single product's grid implies the grid
#: crosses the 0/360 seam. UNVERIFIED: no inspected product wraps, so the
#: unwrap branch below has never run against real data. It is implemented
#: defensively and reported, never applied silently.
LONGITUDE_WRAP_SPAN_DEG: float = 180.0


class GridStatus(str, Enum):
    """How one CSV row, or one grid cell, turned out.

    ``is_suspicious`` marks the outcomes that warrant a look. A row parsing
    cleanly is expected; a row with the wrong field count is not, and neither is
    a grid position that no row ever filled.
    """

    OK = "ok"
    #: Row had a field count other than the label declared.
    WRONG_FIELD_COUNT = "wrong_field_count"
    #: A field the label typed as ASCII_Real / ASCII_Integer would not parse.
    NON_NUMERIC = "non_numeric"
    #: Latitude outside [-90, 90] or a non-finite coordinate.
    COORDINATE_OUT_OF_RANGE = "coordinate_out_of_range"
    #: Negative Pixel or Scan, or one beyond the image dimensions when those
    #: were supplied.
    INDEX_OUT_OF_RANGE = "index_out_of_range"
    #: Two rows claimed the same (Scan, Pixel) position.
    DUPLICATE_POINT = "duplicate_point"
    #: A position in the (Scan x Pixel) rectangle that no row supplied.
    MISSING_POINT = "missing_point"
    #: Row was blank -- tolerated at end of file, counted regardless.
    EMPTY_ROW = "empty_row"

    @property
    def is_suspicious(self) -> bool:
        return self is not GridStatus.OK


@dataclass
class GeometryGridDiagnostics:
    """Counts and retained samples for every row and cell outcome.

    :meth:`report` is meant to be printed on every load, not only on failure: a
    grid that parsed 122452 of 122452 rows and a grid that parsed 122000 of
    122452 look identical downstream, and only one of them is trustworthy.
    """

    counts: Counter = field(default_factory=Counter)
    samples: dict[str, str] = field(default_factory=dict)
    #: ``records`` as declared by the label's ``Table_Delimited``, if a label
    #: was read.
    declared_records: int | None = None
    #: Data rows actually seen in the CSV, header excluded.
    observed_records: int = 0
    #: ``file_size`` from the label vs the file on disk. These disagree on real
    #: products -- see :attr:`file_size_mismatch`.
    declared_file_size: int | None = None
    observed_file_size: int | None = None
    notes: list[str] = field(default_factory=list)

    def record(self, status: GridStatus, detail: str) -> None:
        self.counts[status.value] += 1
        self.samples.setdefault(status.value, detail)

    @property
    def n_ok(self) -> int:
        return self.counts[GridStatus.OK.value]

    @property
    def n_suspicious(self) -> int:
        return sum(n for k, n in self.counts.items() if GridStatus(k).is_suspicious)

    @property
    def record_count_mismatch(self) -> bool:
        return (
            self.declared_records is not None
            and self.declared_records != self.observed_records
        )

    @property
    def file_size_mismatch(self) -> bool:
        return (
            self.declared_file_size is not None
            and self.observed_file_size is not None
            and self.declared_file_size != self.observed_file_size
        )

    def report(self) -> str:
        lines = [f"geometry grid: {self.observed_records} data row(s) read"]
        if self.declared_records is not None:
            verdict = "MISMATCH" if self.record_count_mismatch else "matches"
            lines.append(
                f"  label declares {self.declared_records} record(s) -- {verdict}"
            )
        if self.file_size_mismatch:
            # Seen for real on the TMC-2 nadir product: the label says 2111975
            # bytes, the file is 2111886, yet the label's md5 matches the file.
            # So the size field is wrong, not the data. Report it; do not treat
            # it as corruption.
            lines.append(
                f"! label file_size {self.declared_file_size} != on-disk "
                f"{self.observed_file_size} -- label metadata bug, not necessarily "
                f"a damaged file (verify with the label's md5_checksum)"
            )
        lines.append("")
        lines.append("outcomes:")
        for status in GridStatus:
            n = self.counts.get(status.value, 0)
            if not n:
                continue
            marker = "  " if status is GridStatus.OK else "! "
            lines.append(f"{marker}{status.value:24s} {n:8d}")
            if status.is_suspicious:
                lines.append(f"      sample: {self.samples.get(status.value, '(none)')}")
        for note in self.notes:
            lines.append(f"NOTE: {note}")
        if self.n_ok == 0:
            lines += [
                "",
                "no usable grid points -- see the outcome breakdown above before",
                "concluding the product has no geometry",
            ]
        return "\n".join(lines)


@dataclass(frozen=True)
class GeometryGrid:
    """A product's ground-coordinate grid, indexed ``[scan_index, pixel_index]``.

    ``scan_lines`` and ``pixels`` are the *image* line and sample indices the
    grid samples, ascending and 0-based. They are not assumed uniform: both
    inspected products step by 100 and then take a short final step to land on
    the last real index (11900 -> 11999, 101000 -> 101073), so the arrays are
    carried explicitly rather than reconstructed from a stride.
    """

    #: Image line index of each grid row, shape ``(n_scan,)``.
    scan_lines: np.ndarray
    #: Image sample index of each grid column, shape ``(n_pixel,)``.
    pixels: np.ndarray
    #: Latitude in degrees, shape ``(n_scan, n_pixel)``.
    lat: np.ndarray
    #: Longitude in degrees, shape ``(n_scan, n_pixel)``. Unwrapped to be
    #: continuous across the grid if a seam crossing was detected.
    lon: np.ndarray
    #: Image dimensions, when a caller supplied them for cross-checking.
    lines: int | None = None
    samples: int | None = None
    product_id: str | None = None
    source: Path | None = None
    #: Field order actually used, and where it came from.
    field_names: tuple[str, ...] = GEOMETRY_FIELD_NAMES
    field_provenance: Provenance = GEOMETRY_FIELD_PROVENANCE
    #: True if longitudes were unwrapped past the 0/360 seam. UNVERIFIED path.
    longitude_unwrapped: bool = False
    diagnostics: GeometryGridDiagnostics = field(default_factory=GeometryGridDiagnostics)

    @property
    def shape(self) -> tuple[int, int]:
        return (int(self.scan_lines.size), int(self.pixels.size))

    @property
    def complete(self) -> bool:
        """Every cell of the ``scan x pixel`` rectangle was filled by a row."""
        return not self.diagnostics.counts.get(GridStatus.MISSING_POINT.value, 0)

    @property
    def covers_full_image(self) -> bool | None:
        """Whether the grid's last indices are the image's last indices.

        ``None`` when the image dimensions were not supplied. False means the
        grid stops short of an edge and every mapping near that edge is an
        extrapolation.
        """
        if self.lines is None or self.samples is None:
            return None
        return (
            int(self.scan_lines[-1]) == self.lines - 1
            and int(self.pixels[-1]) == self.samples - 1
        )

    def corners(self) -> tuple[tuple[float, float], ...]:
        """The four grid corners as ``(lat, lon)`` in UL, UR, LR, LL ring order.

        Same ordering convention as
        :func:`lunar_reg.ingest.overlap.footprint_from_row`, so this can be
        dropped straight into a :class:`~lunar_reg.ingest.overlap.FootprintPolygon`.
        On both inspected products these reproduce the image label's
        ``isda:Refined_Corner_Coordinates`` to the label's 6-decimal rounding.
        """
        idx = ((0, 0), (0, -1), (-1, -1), (-1, 0))
        return tuple((float(self.lat[i, j]), float(self.lon[i, j])) for i, j in idx)


# ---------------------------------------------------------------------------
# Label reading
# ---------------------------------------------------------------------------


def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


@dataclass(frozen=True)
class GeometryLabel:
    """The parts of a ``_g_grd_d18.xml`` this module needs."""

    field_names: tuple[str, ...]
    field_types: tuple[str, ...]
    records: int | None
    file_name: str | None
    file_size: int | None
    md5_checksum: str | None
    product_id: str | None


def read_geometry_label(path: str | Path) -> GeometryLabel:
    """Parse the geometry product's PDS4 label.

    Only documented ``Product_Observational`` / ``Table_Delimited`` elements are
    read: ``Field_Delimited`` (``name``, ``field_number``, ``data_type``),
    ``records``, and the ``File`` block. Fields are returned in ``field_number``
    order, which is what defines the CSV column order -- the loader never
    assumes it.
    """
    path = Path(path)
    root = ET.parse(path).getroot()

    numbered: list[tuple[int, str, str]] = []
    for el in root.iter():
        if _localname(el.tag) != "Field_Delimited":
            continue
        parts = {_localname(c.tag): (c.text or "").strip() for c in el}
        try:
            number = int(parts.get("field_number", ""))
        except ValueError:
            # A field without a usable field_number cannot be positioned, and
            # guessing its column is exactly the failure mode this project
            # forbids. Skip it here; the count check below turns it into a
            # loud mismatch rather than a silent shift.
            continue
        numbered.append((number, parts.get("name", ""), parts.get("data_type", "")))
    numbered.sort()

    records = None
    for el in root.iter():
        if _localname(el.tag) == "Table_Delimited":
            for child in el:
                if _localname(child.tag) == "records":
                    try:
                        records = int((child.text or "").strip())
                    except ValueError:
                        records = None
            break

    file_name = file_size = md5 = None
    for el in root.iter():
        if _localname(el.tag) != "File":
            continue
        parts = {_localname(c.tag): (c.text or "").strip() for c in el}
        file_name = parts.get("file_name") or None
        md5 = parts.get("md5_checksum") or None
        try:
            file_size = int(parts.get("file_size", ""))
        except ValueError:
            file_size = None
        break

    product_id = None
    for el in root.iter():
        if _localname(el.tag) == "logical_identifier":
            product_id = (el.text or "").strip() or None
            break

    return GeometryLabel(
        field_names=tuple(n for _, n, _ in numbered),
        field_types=tuple(t for _, _, t in numbered),
        records=records,
        file_name=file_name,
        file_size=file_size,
        md5_checksum=md5,
        product_id=product_id,
    )


def find_geometry_files(root: str | Path, product_id: str | None = None):
    """Locate ``(csv, label)`` pairs under an extracted product directory.

    Matches the ``*_g_grd_d18.csv`` naming used by the calibrated OHRC and
    TMC-2 bundles. Returns a list of ``(csv_path, label_path_or_None)``.
    """
    root = Path(root)
    pattern = f"*{product_id}*_g_grd_d18.csv" if product_id else "*_g_grd_d18.csv"
    out = []
    for csv_path in sorted(root.rglob(pattern)):
        label = csv_path.with_suffix(".xml")
        out.append((csv_path, label if label.exists() else None))
    return out


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def read_geometry_grid(
    csv_path: str | Path,
    label_path: str | Path | None = None,
    lines: int | None = None,
    samples: int | None = None,
    strict_fields: bool = True,
) -> GeometryGrid:
    """Read a ``_g_grd_d18.csv`` into a :class:`GeometryGrid`.

    ``label_path`` defaults to the CSV path with an ``.xml`` suffix. The label
    supplies the field order; when it is absent the CSV's own header line is
    used, and when that is absent too :data:`GEOMETRY_FIELD_NAMES` is the last
    resort and ``field_provenance`` drops to :attr:`Provenance.DOCUMENTED`.

    ``lines``/``samples`` are the image dimensions from the *image* label. They
    are optional; supplying them enables the index-range check and
    :attr:`GeometryGrid.covers_full_image`.

    Raises ``ValueError`` only for a file that yields no usable point at all --
    a per-row failure is classified and counted, never raised.
    """
    csv_path = Path(csv_path)
    if label_path is None:
        candidate = csv_path.with_suffix(".xml")
        label_path = candidate if candidate.exists() else None

    diag = GeometryGridDiagnostics()
    label = None
    field_names = GEOMETRY_FIELD_NAMES
    provenance = Provenance.DOCUMENTED
    product_id = None

    if label_path is not None:
        label = read_geometry_label(label_path)
        diag.declared_records = label.records
        diag.declared_file_size = label.file_size
        product_id = label.product_id
        if label.field_names:
            field_names = label.field_names
            provenance = Provenance.VERIFIED
        else:
            diag.notes.append(
                f"label {Path(label_path).name} declared no Field_Delimited entries; "
                f"falling back to the CSV header"
            )
    try:
        diag.observed_file_size = csv_path.stat().st_size
    except OSError:
        diag.observed_file_size = None

    with csv_path.open(newline="", encoding="utf-8", errors="replace") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if header is not None and _looks_like_header(header):
            if label is None or not label.field_names:
                field_names = tuple(h.strip() for h in header)
                provenance = Provenance.VERIFIED
            elif tuple(h.strip() for h in header) != tuple(field_names):
                # A header that disagrees with the label means one of the two is
                # describing a different file. Refusing is the only safe move:
                # picking either silently would mislabel every column.
                message = (
                    f"CSV header {tuple(h.strip() for h in header)} disagrees with "
                    f"label fields {tuple(field_names)} in {csv_path.name}"
                )
                if strict_fields:
                    raise ValueError(message)
                diag.notes.append(message + " -- using the label order")
        else:
            # No header: rewind so the first line is treated as data.
            handle.seek(0)
            reader = csv.reader(handle)
            diag.notes.append("no header line found; field order taken from the label")

        index = _field_index(field_names)
        points = _consume_rows(reader, index, len(field_names), lines, samples, diag)

    if not points:
        raise ValueError(
            f"{csv_path.name}: no parseable geometry rows\n{diag.report()}"
        )

    grid = _assemble(points, diag, lines, samples)
    unwrapped = _maybe_unwrap_longitude(grid["lon"], diag)

    result = GeometryGrid(
        scan_lines=grid["scan"],
        pixels=grid["pixel"],
        lat=grid["lat"],
        lon=grid["lon"],
        lines=lines,
        samples=samples,
        product_id=product_id,
        source=csv_path,
        field_names=tuple(field_names),
        field_provenance=provenance,
        longitude_unwrapped=unwrapped,
        diagnostics=diag,
    )

    logger.info(
        "geometry grid %s: %d x %d points from %d row(s), %d suspicious outcome(s)",
        csv_path.name, *result.shape, diag.observed_records, diag.n_suspicious,
    )
    if diag.n_suspicious:
        # One concise line from the library; the caller prints the full report,
        # so it is not emitted twice.
        logger.warning(
            "%s: %d non-OK outcome(s): %s -- call diagnostics.report() for detail",
            csv_path.name,
            diag.n_suspicious,
            ", ".join(
                f"{k}={n}" for k, n in sorted(diag.counts.items())
                if GridStatus(k).is_suspicious
            ),
        )
    return result


def _looks_like_header(row: list[str]) -> bool:
    """A header row is the one whose fields are not all numeric."""
    for cell in row:
        try:
            float(cell)
        except ValueError:
            return True
    return False


def _field_index(field_names) -> dict[str, int]:
    """Column positions for the four fields, matched case-insensitively.

    Raises rather than guessing: a missing column cannot be substituted, and a
    loader that quietly picked column 0 for latitude would produce plausible
    wrong numbers.
    """
    lowered = {name.strip().lower(): i for i, name in enumerate(field_names)}
    index = {}
    for wanted in ("longitude", "latitude", "pixel", "scan"):
        if wanted not in lowered:
            raise ValueError(
                f"geometry table has no {wanted!r} field; declared fields are "
                f"{tuple(field_names)}"
            )
        index[wanted] = lowered[wanted]
    return index


def _consume_rows(reader, index, n_fields, lines, samples, diag):
    """Parse rows into ``(scan, pixel, lat, lon)`` tuples, classifying failures."""
    points: list[tuple[int, int, float, float]] = []
    lon_i, lat_i = index["longitude"], index["latitude"]
    px_i, sc_i = index["pixel"], index["scan"]

    for lineno, row in enumerate(reader, start=2):
        if not row or all(not cell.strip() for cell in row):
            diag.record(GridStatus.EMPTY_ROW, f"line {lineno}")
            continue
        diag.observed_records += 1
        if len(row) != n_fields:
            diag.record(
                GridStatus.WRONG_FIELD_COUNT,
                f"line {lineno}: {len(row)} field(s), expected {n_fields}: {row!r}",
            )
            continue
        try:
            lon = float(row[lon_i])
            lat = float(row[lat_i])
            # The label types these ASCII_Integer, so a fractional value is a
            # contract violation and int() would truncate it silently.
            pixel = int(row[px_i])
            scan = int(row[sc_i])
        except ValueError as exc:
            diag.record(GridStatus.NON_NUMERIC, f"line {lineno}: {exc} in {row!r}")
            continue

        if not (np.isfinite(lon) and np.isfinite(lat)) or not -90.0 <= lat <= 90.0:
            diag.record(
                GridStatus.COORDINATE_OUT_OF_RANGE,
                f"line {lineno}: lat={lat} lon={lon}",
            )
            continue
        if pixel < 0 or scan < 0 or (samples is not None and pixel >= samples) \
                or (lines is not None and scan >= lines):
            diag.record(
                GridStatus.INDEX_OUT_OF_RANGE,
                f"line {lineno}: pixel={pixel} scan={scan} "
                f"(image {lines}x{samples})",
            )
            continue

        points.append((scan, pixel, lat, lon))
    return points


def _assemble(points, diag, lines, samples):
    """Build the rectangular arrays from scattered ``(scan, pixel, ...)`` rows.

    Row order is not assumed. Both inspected products are scan-major with
    ascending pixel, but positioning by value rather than by arrival order costs
    nothing and turns a reordered file from a silent corruption into a correct
    read.
    """
    arr = np.asarray(points, dtype=np.float64)
    scan_vals = np.unique(arr[:, 0]).astype(np.int64)
    pixel_vals = np.unique(arr[:, 1]).astype(np.int64)

    lat = np.full((scan_vals.size, pixel_vals.size), np.nan)
    lon = np.full((scan_vals.size, pixel_vals.size), np.nan)

    scan_pos = {v: i for i, v in enumerate(scan_vals.tolist())}
    pixel_pos = {v: j for j, v in enumerate(pixel_vals.tolist())}

    for scan, pixel, la, lo in points:
        i, j = scan_pos[scan], pixel_pos[pixel]
        if not np.isnan(lat[i, j]):
            diag.record(
                GridStatus.DUPLICATE_POINT,
                f"scan={scan} pixel={pixel} appears more than once",
            )
            continue
        lat[i, j] = la
        lon[i, j] = lo
        diag.record(GridStatus.OK, "")

    missing = np.argwhere(np.isnan(lat))
    for i, j in missing:
        diag.record(
            GridStatus.MISSING_POINT,
            f"no row for scan={scan_vals[i]} pixel={pixel_vals[j]}",
        )
    if missing.size:
        diag.notes.append(
            f"{len(missing)} grid position(s) unfilled -- the grid is NOT a complete "
            f"rectangle and interpolation near those cells will return NaN"
        )

    if lines is not None and scan_vals[-1] != lines - 1:
        diag.notes.append(
            f"grid stops at scan {scan_vals[-1]} but the image has {lines} line(s); "
            f"mapping beyond that line is extrapolation"
        )
    if samples is not None and pixel_vals[-1] != samples - 1:
        diag.notes.append(
            f"grid stops at pixel {pixel_vals[-1]} but the image has {samples} "
            f"sample(s); mapping beyond that sample is extrapolation"
        )

    return {"scan": scan_vals, "pixel": pixel_vals, "lat": lat, "lon": lon}


def _maybe_unwrap_longitude(lon: np.ndarray, diag) -> bool:
    """Make longitudes continuous if the grid straddles the 0/360 seam.

    UNVERIFIED: neither inspected product wraps (OHRC spans 23.0-27.7 deg,
    TMC-2 140.9-142.7 deg), so this branch has never executed on real data. It
    is deliberately conditional and reported rather than applied unconditionally,
    because shifting longitudes on a product that does not need it would corrupt
    every subsequent lookup.
    """
    finite = lon[np.isfinite(lon)]
    if finite.size == 0:
        return False
    if float(finite.max() - finite.min()) <= LONGITUDE_WRAP_SPAN_DEG:
        return False
    lon[np.isfinite(lon) & (lon > LONGITUDE_WRAP_SPAN_DEG)] -= 360.0
    diag.notes.append(
        "longitudes span more than 180 deg and were unwrapped to a continuous "
        "range -- UNVERIFIED code path, no inspected product exercises it"
    )
    return True


# ---------------------------------------------------------------------------
# Forward and inverse mapping
# ---------------------------------------------------------------------------


def pixel_to_lonlat(grid: GeometryGrid, line, sample):
    """Ground coordinates of image positions, by bilinear interpolation.

    ``line``/``sample`` are image indices (not grid indices) and may be arrays.
    Returns ``(lon, lat)`` arrays; positions outside the grid's index range, or
    falling in a cell with a missing corner, come back NaN rather than clamped,
    so an out-of-grid query is visible instead of quietly wrong.
    """
    line = np.asarray(line, dtype=np.float64)
    sample = np.asarray(sample, dtype=np.float64)

    i, v = _cell_and_fraction(grid.scan_lines, line)
    j, u = _cell_and_fraction(grid.pixels, sample)

    valid = np.isfinite(v) & np.isfinite(u)
    i = np.where(valid, i, 0)
    j = np.where(valid, j, 0)

    def interp(values):
        a = values[i, j] * (1 - u) * (1 - v)
        b = values[i, j + 1] * u * (1 - v)
        c = values[i + 1, j] * (1 - u) * v
        d = values[i + 1, j + 1] * u * v
        return np.where(valid, a + b + c + d, np.nan)

    return interp(grid.lon), interp(grid.lat)


def _cell_and_fraction(axis: np.ndarray, query: np.ndarray):
    """Index of the containing cell and the 0..1 position within it."""
    n = axis.size
    idx = np.searchsorted(axis, query, side="right") - 1
    idx = np.clip(idx, 0, n - 2)
    lo = axis[idx].astype(np.float64)
    hi = axis[idx + 1].astype(np.float64)
    frac = (query - lo) / (hi - lo)
    outside = (query < axis[0]) | (query > axis[-1])
    return idx, np.where(outside, np.nan, frac)


@dataclass(frozen=True)
class PixelLookup:
    """Result of mapping ground coordinates into image space.

    ``line``/``sample`` are float image indices; NaN where the lookup failed.
    ``inside`` is True only where the point fell within the grid's own footprint
    -- a point outside it is reported, not extrapolated.
    """

    line: np.ndarray
    sample: np.ndarray
    inside: np.ndarray
    #: Max remaining |residual| in degrees from the inverse-bilinear solve, per
    #: point. Large values mean the solve did not converge for that point.
    residual_deg: np.ndarray

    @property
    def n_inside(self) -> int:
        return int(np.count_nonzero(self.inside))


def lonlat_to_pixel(
    grid: GeometryGrid,
    lat,
    lon,
    max_iterations: int = 20,
    tolerance_deg: float = 1e-10,
) -> PixelLookup:
    """Map ground coordinates to image ``(line, sample)`` using the real grid.

    This is the drop-in alternative to
    :func:`lunar_reg.ingest.overlap.geographic_to_pixel_transform`. It cannot
    return a 3x3 matrix, because the whole point is that the true mapping is not
    projective; it returns per-point image coordinates instead.

    Method: locate the grid cell containing the point via a KD-tree over the
    grid nodes, then solve the inverse of the cell's bilinear map by Newton
    iteration. Within a cell -- 100 lines by 100 samples on both inspected
    products -- the ground coordinates are close enough to bilinear that this
    converges in a handful of steps.

    Points outside the grid footprint get ``inside=False`` and NaN coordinates.
    Extrapolating a pushbroom strip's geometry past its own footprint is not
    something this module will do silently.

    Cost, measured in-session on the OHRC grid (1012 x 121, 5000 random query
    points): ~22,600 points/s, with a worst-case round-trip error of 2e-9 px at
    grid nodes and 1.6e-6 px for interior points. That is comfortable for
    footprint windows and tie-point lists; a caller mapping millions of points
    should batch through :func:`pixel_to_lonlat` in the forward direction
    instead, which is fully vectorised.
    """
    from scipy.spatial import cKDTree

    lat = np.atleast_1d(np.asarray(lat, dtype=np.float64))
    lon = np.atleast_1d(np.asarray(lon, dtype=np.float64))
    if lat.shape != lon.shape:
        raise ValueError(f"lat shape {lat.shape} != lon shape {lon.shape}")
    if grid.longitude_unwrapped:
        lon = np.where(lon > LONGITUDE_WRAP_SPAN_DEG, lon - 360.0, lon)

    n_scan, n_pixel = grid.shape
    line = np.full(lat.shape, np.nan)
    sample = np.full(lat.shape, np.nan)
    inside = np.zeros(lat.shape, dtype=bool)
    residual = np.full(lat.shape, np.nan)

    # Cell corners, indexed [i, j] for the cell spanning grid rows i..i+1.
    nodes = np.column_stack([grid.lon.ravel(), grid.lat.ravel()])
    finite = np.isfinite(nodes).all(axis=1)
    if not finite.any():
        return PixelLookup(line, sample, inside, residual)
    tree = cKDTree(nodes[finite])
    node_ids = np.flatnonzero(finite)

    flat_lat = lat.ravel()
    flat_lon = lon.ravel()
    flat_line = line.ravel()
    flat_sample = sample.ravel()
    flat_inside = inside.ravel()
    flat_res = residual.ravel()

    # A handful of nearest nodes is enough: the containing cell always touches
    # the nearest node, but on a strongly sheared grid the *nearest* node alone
    # can sit on a cell the point misses, so neighbouring candidates are tried.
    k = min(4, node_ids.size)
    _, nearest = tree.query(np.column_stack([flat_lon, flat_lat]), k=k)
    nearest = np.atleast_2d(nearest.reshape(flat_lat.size, k))

    for q in range(flat_lat.size):
        target = (flat_lon[q], flat_lat[q])
        if not (np.isfinite(target[0]) and np.isfinite(target[1])):
            continue
        best = None
        for node in nearest[q]:
            gi, gj = divmod(int(node_ids[node]), n_pixel)
            for i in (gi - 1, gi):
                for j in (gj - 1, gj):
                    if not (0 <= i < n_scan - 1 and 0 <= j < n_pixel - 1):
                        continue
                    solved = _invert_cell(grid, i, j, target, max_iterations, tolerance_deg)
                    if solved is None:
                        continue
                    u, v, res = solved
                    contained = -1e-9 <= u <= 1 + 1e-9 and -1e-9 <= v <= 1 + 1e-9
                    if contained:
                        best = (i, j, u, v, res, True)
                        break
                    if best is None or res < best[4]:
                        best = (i, j, u, v, res, False)
                if best is not None and best[5]:
                    break
            if best is not None and best[5]:
                break
        if best is None:
            continue
        i, j, u, v, res, contained = best
        flat_res[q] = res
        if not contained:
            continue
        s0, s1 = float(grid.scan_lines[i]), float(grid.scan_lines[i + 1])
        p0, p1 = float(grid.pixels[j]), float(grid.pixels[j + 1])
        flat_line[q] = s0 + v * (s1 - s0)
        flat_sample[q] = p0 + u * (p1 - p0)
        flat_inside[q] = True

    return PixelLookup(line, sample, inside, residual)


def _invert_cell(grid, i, j, target, max_iterations, tolerance_deg):
    """Solve the bilinear cell map for ``(u, v)`` at ``target = (lon, lat)``.

    Returns ``(u, v, residual_deg)``, or ``None`` if a corner is missing or the
    Jacobian is singular. ``u`` runs across track, ``v`` along track.
    """
    # Scalar arithmetic, not numpy: this runs once per candidate cell per query
    # point, and at that size array allocation dominates the actual maths.
    a0, a1 = float(grid.lon[i, j]), float(grid.lat[i, j])
    x10, y10 = float(grid.lon[i, j + 1]), float(grid.lat[i, j + 1])
    x01, y01 = float(grid.lon[i + 1, j]), float(grid.lat[i + 1, j])
    x11, y11 = float(grid.lon[i + 1, j + 1]), float(grid.lat[i + 1, j + 1])
    for value in (a0, a1, x10, y10, x01, y01, x11, y11):
        if value != value:  # NaN from a missing grid point
            return None

    b0, b1 = x10 - a0, y10 - a1
    c0, c1 = x01 - a0, y01 - a1
    d0 = x11 - x10 - x01 + a0
    d1 = y11 - y10 - y01 + a1
    tx, ty = float(target[0]), float(target[1])

    u = v = 0.5
    for _ in range(max_iterations):
        f0 = a0 + b0 * u + c0 * v + d0 * u * v - tx
        f1 = a1 + b1 * u + c1 * v + d1 * u * v - ty
        residual = max(abs(f0), abs(f1))
        if residual < tolerance_deg:
            return u, v, residual
        j00, j01 = b0 + d0 * v, c0 + d0 * u
        j10, j11 = b1 + d1 * v, c1 + d1 * u
        det = j00 * j11 - j01 * j10
        if abs(det) < 1e-18:
            # A degenerate cell (collapsed or reflected) has no unique inverse.
            # Reporting no solution is correct; a pseudo-inverse would return a
            # confident answer to a question with no single right one.
            return None
        u -= (j11 * f0 - j01 * f1) / det
        v -= (-j10 * f0 + j00 * f1) / det
        # Newton on a bilinear map can wander far outside the cell before
        # settling; clamping loosely keeps it where the local model still means
        # something without forbidding a true near-edge solution.
        u = min(max(u, -1.0), 2.0)
        v = min(max(v, -1.0), 2.0)

    f0 = a0 + b0 * u + c0 * v + d0 * u * v - tx
    f1 = a1 + b1 * u + c1 * v + d1 * u * v - ty
    return u, v, max(abs(f0), abs(f1))


#: Pixel distance within which a solved coordinate is treated as landing exactly
#: on an integer index. Measured round-trip error of the inverse solve on the two
#: real products is ~1e-6 px, so this is three orders of magnitude above the noise
#: and far below anything that could move a window boundary meaningfully.
PIXEL_SNAP_TOLERANCE: float = 1e-3


def _snap(value: float) -> float:
    nearest = round(float(value))
    return float(nearest) if abs(value - nearest) < PIXEL_SNAP_TOLERANCE else float(value)


def polygon_to_pixel_window(grid: GeometryGrid, polygon, densify: int = 8):
    """Pixel-space bounding window of a lat/lon polygon, using the real grid.

    Same return contract as
    :func:`lunar_reg.ingest.overlap.polygon_to_pixel_window` --
    ``(row_off, col_off, height, width)`` clipped to the product, or ``None`` --
    so a caller can swap one for the other.

    ``polygon`` is a sequence of ``(lat, lon)``. Edges are densified before
    mapping because the grid map is *not* projective: a straight edge in ground
    coordinates is curved in pixel space, and taking only the vertices can
    understate the window. ``densify`` is the number of segments each edge is
    split into.

    Returns ``None`` when no vertex lands inside the grid footprint. That is a
    reported outcome, not a silent empty crop -- inspect
    :attr:`PixelLookup.inside` via :func:`lonlat_to_pixel` for the detail.
    """
    ring = [tuple(pt) for pt in polygon]
    if len(ring) >= 2 and ring[0] == ring[-1]:
        ring = ring[:-1]
    if len(ring) < 3:
        return None

    lats: list[float] = []
    lons: list[float] = []
    for k in range(len(ring)):
        (lat0, lon0) = ring[k]
        (lat1, lon1) = ring[(k + 1) % len(ring)]
        for t in np.linspace(0.0, 1.0, max(1, densify), endpoint=False):
            lats.append(lat0 + t * (lat1 - lat0))
            lons.append(lon0 + t * (lon1 - lon0))

    lookup = lonlat_to_pixel(grid, np.array(lats), np.array(lons))
    if not lookup.inside.any():
        return None

    rows = lookup.line[lookup.inside]
    cols = lookup.sample[lookup.inside]

    # Grid points are pixel *centres*, so the exclusive stop bound is one past
    # the last covered pixel -- same convention as overlap.polygon_to_pixel_window.
    # Snap first: a vertex that is exactly a grid node comes back from the Newton
    # solve as 11999 - 1e-9, and flooring that loses the product's last column.
    row0 = int(np.floor(_snap(rows.min())))
    row1 = int(np.floor(_snap(rows.max()))) + 1
    col0 = int(np.floor(_snap(cols.min())))
    col1 = int(np.floor(_snap(cols.max()))) + 1

    height = grid.lines if grid.lines is not None else int(grid.scan_lines[-1]) + 1
    width = grid.samples if grid.samples is not None else int(grid.pixels[-1]) + 1
    row0 = max(0, min(row0, height))
    row1 = max(0, min(row1, height))
    col0 = max(0, min(col0, width))
    col1 = max(0, min(col1, width))

    if row1 <= row0 or col1 <= col0:
        return None
    return (row0, col0, row1 - row0, col1 - col0)
