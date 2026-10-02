"""Reading PDS4/PDS3 products and turning them into tractable work units.

Metadata trust
--------------
Every mapped label field carries a :class:`Provenance`; ``lunar-reg fields``
prints the current breakdown (saved output: ``docs/results/fields_20261002.txt``,
"27 mapped fields: 5 documented, 2 unverified, 20 verified"). Per field group,
as recorded in :mod:`lunar_reg.ingest.fieldmap`:

* identification and array structure -- VERIFIED by a label written to the
  documented PDS4 schema and read back by GDAL's PDS4 driver; ``instrument``,
  ``target``, ``start_time``, ``stop_time`` and ``array_offset`` are
  DOCUMENTED (standard PDS4 elements, not exercised here);
* sun azimuth, sun elevation, incidence and the eight footprint corners --
  VERIFIED 2026-09-05 against a real Chandrayaan-2 OHRC label with
  ``lunar-reg probe-label``;
* the IIRS first-band centre wavelength and width -- VERIFIED 2026-10-02 against
  a real IIRS label (``docs/probes/ch2_iir_nci_20221226T0416479474_d_img_d32.txt``);
* emission and phase angle -- UNVERIFIED: absent from the probed OHRC label, so
  their candidate paths are still guesses.

Geodesy on footprints uses the lunar sphere returned by
:func:`lunar_reg.constants.moon_datum` (re-exported here as ``moon_datum``).

:mod:`lunar_reg.ingest.geometry_grid` reads the per-observation ground-coordinate
grid that every Chandrayaan-2 product bundles, whose own PDS4 label declares its
columns, so that geometry is read rather than inferred from four corners. Prefer
it over the four-corner footprint wherever it is available.
"""

from lunar_reg.constants import moon_datum
from lunar_reg.ingest.fieldmap import (
    ALL_FIELDS,
    UNVERIFIED_FIELD_NAMES,
    Field,
    Provenance,
)
from lunar_reg.ingest.geometry_grid import (
    GEOMETRY_FIELD_NAMES,
    GeometryGrid,
    GeometryGridDiagnostics,
    GeometryLabel,
    GridStatus,
    PixelLookup,
    find_geometry_files,
    lonlat_to_pixel,
    pixel_to_lonlat,
    read_geometry_grid,
    read_geometry_label,
)
from lunar_reg.ingest.lro import (
    LROProduct,
    detect_format,
    open_lro_product,
    read_lro_label,
    scan_lro_directory,
)
from lunar_reg.ingest.manifest import (
    build_manifest,
    manifest_summary,
    read_manifest,
    scan_directory,
    write_manifest,
)
from lunar_reg.ingest.overlap import (
    FootprintPolygon,
    OverlapDiagnostics,
    OverlapResult,
    OverlapStatus,
    crop_to_overlap,
    find_overlapping_pairs,
    footprint_from_row,
    intersect,
    polygon_to_wkt,
)
from lunar_reg.ingest.pds4 import PDS4Product, open_product, read_label
from lunar_reg.ingest.probe import format_report, probe_label, suggest_fieldmap
from lunar_reg.ingest.tiling import Tile, iter_tiles, plan_tiles

__all__ = [
    "ALL_FIELDS",
    "Field",
    "FootprintPolygon",
    "GEOMETRY_FIELD_NAMES",
    "GeometryGrid",
    "GeometryGridDiagnostics",
    "GeometryLabel",
    "GridStatus",
    "LROProduct",
    "OverlapDiagnostics",
    "OverlapResult",
    "OverlapStatus",
    "PDS4Product",
    "PixelLookup",
    "Provenance",
    "Tile",
    "UNVERIFIED_FIELD_NAMES",
    "build_manifest",
    "crop_to_overlap",
    "detect_format",
    "find_geometry_files",
    "find_overlapping_pairs",
    "footprint_from_row",
    "format_report",
    "intersect",
    "iter_tiles",
    "lonlat_to_pixel",
    "manifest_summary",
    "moon_datum",
    "open_lro_product",
    "open_product",
    "pixel_to_lonlat",
    "plan_tiles",
    "polygon_to_wkt",
    "probe_label",
    "read_geometry_grid",
    "read_geometry_label",
    "read_label",
    "read_lro_label",
    "read_manifest",
    "scan_directory",
    "scan_lro_directory",
    "suggest_fieldmap",
    "write_manifest",
]
