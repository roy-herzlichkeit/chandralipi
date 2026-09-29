# LLD — overlap: geometry-grid wiring + correctness fixes (P1.06)

Produces: C11 `PriorSource`. Closes: TBD 1.1 (wiring), A046 (S6), A047 (ingest-4), A048 (ingest-5), A049 (ingest-6), A050 (S5), A051 (ingest-8), A052 (ingest-12), A053 (ingest-18), A105 (ingest-7), A106 (ingest-15). Files: `ingest/overlap.py`, `ingest/pseudo_gt.py` only.

## 1. New types in `overlap.py`
```python
class PriorSource(str, Enum):          # C11
    GEOMETRY_GRID = "geometry_grid"
    LABEL_CORNERS = "label_corners"
    BBOX = "bbox"

class WindowStatus(str, Enum):
    OK = "ok"
    NO_PIXEL_SIZE = "no_pixel_size"                    # lines/samples unknown
    OUTSIDE_PRODUCT = "outside_product"
    BBOX_HAS_NO_PIXEL_ORIENTATION = "bbox_has_no_pixel_orientation"   # A049
    GRID_UNREADABLE = "grid_unreadable"
    @property
    def is_failure(self) -> bool   # every member except OK

@dataclass
class WindowOutcome:
    status: WindowStatus
    window: tuple[int, int, int, int] | None      # (row_off, col_off, height, width)
    source: PriorSource | None
    detail: str = ""
```
`FootprintPolygon` gains `geometry_grid_path: str | None = None` (appended; frozen dataclass). `footprint_from_row` copies the row's `geometry_grid_path` column when present (P1.03's catalog provides it; manifests without the column → None).

## 2. Grid-first pixel mapping (TBD 1.1)
```python
def pixel_window(footprint: FootprintPolygon, polygon) -> WindowOutcome
def footprint_prior_source(footprint: FootprintPolygon) -> PriorSource
```
- `footprint_prior_source`: `GEOMETRY_GRID` when `geometry_grid_path` is set and the file exists; else `BBOX` when `bbox_derived`; else `LABEL_CORNERS`.
- `pixel_window`: GEOMETRY_GRID → `geometry_grid.read_geometry_grid(path, lines=…, samples=…)` (cached per path with `functools.lru_cache(maxsize=8)` on the path string) then `geometry_grid.polygon_to_pixel_window`; a read failure → `GRID_UNREADABLE` (detail = exception text) and **no** silent fallback to corners. LABEL_CORNERS → the existing homography path. BBOX → `BBOX_HAS_NO_PIXEL_ORIENTATION`.
- `polygon_to_pixel_window(footprint, polygon)` keeps its signature and return type and becomes `pixel_window(...).window`.
- `crop_to_overlap` uses `pixel_window` and writes `entry["window_status"]` and `entry["prior_source"]` for each side.

## 3. Correctness fixes
| audit | change |
|---|---|
| A047 | Non-polar `intersect`: before clipping, rewrap both rings' longitudes into `(ref − 180, ref + 180]` with `ref` = the source ring's first longitude. |
| A048 | `_touching(a_ring, b_ring, eps)` (signature unchanged) returns `(abs(gap_a) <= eps and gap_b <= eps) or (abs(gap_b) <= eps and gap_a <= eps)`. |
| A049 | covered by §2 (BBOX status). |
| A050 | `find_overlapping_pairs`: when `source_sensor == reference_sensor`, iterate `j > i` over one polygon list and skip pairs with equal `product_id`. |
| A105 | `record_missing` is called once per product without a footprint, inside the two footprint loops, with sample `f"{role} {product_id}"` (`role` = "source"/"reference"). |
| A106 | `polygon_to_pixel_window` (corner path) snaps min/max with `geometry_grid.snap_to_integer` before `floor`. |
| A046 | `crop_to_overlap`: `profile["transform"] = dataset.window_transform(window)`; keep `crs`; keep `nodata` from the parent when it is set. |
| A052 | `crop_to_overlap` reads all bands (`dataset.read(window=window)`), `count = dataset.count`, writes all bands. |
| A051 | `pseudo_gt.project_to_pixels`: map `(lat, lon)` through `overlap.footprint_frame(fp).plane_ring(...)` when the frame is not None, before applying the matrix — via a new shared helper `overlap.to_fit_plane(footprint, ring) -> tuple[tuple[float, float], ...]` (the ring unchanged for non-polar footprints, the `PolarFrame` plane ring otherwise) also used by `polygon_to_pixel_window`. |

## 4. Tests the prompt adds (`tests/test_overlap_fixes.py`, A053)
One regression test per row of §3 plus: a footprint with a synthetic geometry grid CSV (written in `tmp_path` in the real CSV format read by `read_geometry_grid`) → `pixel_window(...).source is PriorSource.GEOMETRY_GRID`; a grid path pointing at garbage → `GRID_UNREADABLE`; bbox footprint → `BBOX_HAS_NO_PIXEL_ORIENTATION`; crop of an in-memory georeferenced 3-band GeoTIFF → `crop.transform * (0, 0) == parent.transform * (col_off, row_off)` and `count == 3`; same-sensor scan of 3 products → 3 pairs considered, 0 self-pairs.
For the CSV format, reuse the header/field layout from `tests/test_geometry_grid.py` fixtures (read that file; do not invent field names).
