"""Reading PDS4/PDS3 products and turning them into tractable work units.

Metadata trust
--------------
Array structure is read against the documented PDS4/PDS3 schemas and was
cross-checked against GDAL's own drivers. Illumination and footprint geometry
are **unverified** -- no real Chandrayaan-2 or LRO product has been inspected
by this project. See :mod:`lunar_reg.ingest.fieldmap` for the provenance of
each field, and run ``lunar-reg probe-label`` on a real product to replace the
guesses with fact.

The one exception is :mod:`lunar_reg.ingest.geometry_grid`: every Chandrayaan-2
product bundles a per-observation ground-coordinate grid whose own PDS4 label
declares its columns, so that geometry is read rather than guessed. Prefer it
over the four-corner footprint wherever it is available.
"""

from lunar_reg.ingest.fieldmap import (
    ALL_FIELDS,
    UNVERIFIED_FIELD_NAMES,
    Field,
    Provenance,
)
from lunar_reg.ingest.footprint import Footprint, moon_datum, overlap
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
    "Footprint",
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
    "overlap",
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
