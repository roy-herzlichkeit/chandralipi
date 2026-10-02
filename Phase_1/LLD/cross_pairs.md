# LLD — cross-instrument pairs at any site (P1.24)

Produces: C10 addition (`georeference_from_raster`), C11 addition (`centre_sample`), C28 (`lunar_reg.cross`, `configs/references.json`, `data/processed/cross/overlaps.json`). Decision: G41. Closes the P1.18 blocker Q-P1.18-1.

Evidence tags: **M** = measured by the architect on the files on disk, 2026-10-02 · **D** = read in a file · **I** = inference, untested.

## 0. Why this prompt exists
- The TMC-2 and IIRS products on disk do not reach the Vikram site. Their closest per-pixel grid nodes are 529–652 km away (Q-P1.18-1, M). The site runner only knows the Vikram NAC reference, so P1.18 step 4 produced 0 registrations.
- The same products do overlap other data near the south pole (M, per-pixel grids, polygon test in south polar stereographic):
  - IIRS `nci_20230125T1944138897` and TMC-2 `ncf_20231026T0943001971` overlap over latitudes −74.9° to −89.9°. 25 % of the IIRS grid nodes fall inside the TMC-2 footprint.
  - Both overlap valid pixels of the TMC-2 derived ortho `ndn_20231027T1315134884`: 4.2 % (TMC-2) and 2.4 % (IIRS) of its decimated valid pixels.
- The problem statement asks for a generic tool: any Chandrayaan-2 image (OHRC, TMC-2, IIRS) against any lunar reference (`README_TITLE.md` §1, D). This prompt removes the Vikram-only assumption, so a newly downloaded strip or reference is used by adding a file or a config row, with no code change.

## 1. `configs/references.json` (new, committed)
Schema 1. Each row names a map-projected reference raster:
```json
{"schema": 1, "references": [
 {"name": "lro_nac_m1442997156", "path": "data/raw/reference/lro_nac_vikram/NAC_DTM_VIKRAMSITE1_M1442997156_100CM.xml", "georef": "label", "sensor": "LRO_NAC_ORTHO", "independent": true},
 {"name": "lro_nac_m1443025251", "path": "data/raw/reference/lro_nac_vikram/NAC_DTM_VIKRAMSITE1_M1443025251_100CM.xml", "georef": "label", "sensor": "LRO_NAC_ORTHO", "independent": true},
 {"name": "selene_tc_ortho_s66e030", "path": "data/raw/reference/selene_tc_ortho/TCO_MAP_02_S66E030S69E033SC.lbl", "georef": "raster", "sensor": "SELENE_TC_ORTHO", "independent": true},
 {"name": "selene_tc_ortho_s69e030", "path": "data/raw/reference/selene_tc_ortho/TCO_MAP_02_S69E030S72E033SC.lbl", "georef": "raster", "sensor": "SELENE_TC_ORTHO", "independent": true},
 {"name": "tmc2_ortho_20231027", "path": "data/raw/ch2/tmc2/ch2_tmc_ndn_20231027T1315134884_d_oth_d18/data/derived/20231027/ch2_tmc_ndn_20231027T1315134884_d_oth_d18.tif", "georef": "raster", "sensor": "TMC2_ORTHO", "independent": false}
]}
```
- `georef`: `"label"` uses C10 `georeference_from_label` (PDS4 cartography). `"raster"` uses §2.
- `independent`: false when the reference comes from the same mission as the source, so its absolute position is not an independent check. It is carried into every result (§5).
- A row whose `path` does not exist yields `REFERENCE_MISSING` candidates, which are counted and never raise.
- Adding a reference later means adding one row here.

## 2. `ingest/lro.py`: `georeference_from_raster(path) -> GeoReference` (C10 addition)
1. `rasterio.open(path)`. An open failure, or `ds.crs is None`, → `LabelGeoreferenceError` naming the reason.
2. `proj4 = ds.crs.to_proj4()`. It must contain `+proj=stere` or `+proj=eqc`, and `+R=`. Otherwise `LabelGeoreferenceError("unsupported CRS …")`.
3. `T = ds.transform` must be north-up: `T.b == 0`, `T.d == 0`, `T.a > 0`, `T.e < 0`. Otherwise `LabelGeoreferenceError`.
4. `GeoReference(crs_proj4=proj4, x0_m=T.c, y0_m=T.f, pixel_size_x_m=T.a, pixel_size_y_m=-T.e, width=ds.width, height=ds.height, source=…, note=…)`.
5. **Cross-check (sets `source`).** Applies when a PDS3 label (`path` itself when it ends in `.lbl`, else `<stem>.lbl`) has all four keywords `MAXIMUM_LATITUDE`, `MINIMUM_LATITUDE`, `WESTERNMOST_LONGITUDE`, `EASTERNMOST_LONGITUDE`. These are seen in the real SELENE TC label, lines 57–60 (D).
   - Compute the lon/lat of the raster's four outer corners with `pixel_to_lonlat`.
   - Take the largest difference against those bounds, converted to metres (`Δlat·R·π/180`, `Δlon·R·cos(lat)·π/180`).
   - Residual ≤ 1.5 pixels → `source = DOCUMENTED`, `note = "raster tags agree with PDS3 label bounds within <r> m"`.
   - Larger residual → `source = INFERRED`, with the residual in `note`.
   - No such label → `source = INFERRED`, `note = "raster tags not cross-checked (no PDS3 bounding keywords)"`.
   - Known outcomes:
     - SELENE TC S69E030: GDAL `x0 = 909 696.81 m = R·30°`, `y0 = −2 092 307.48 m = R·(−69°)`, pixel 7.40316 m = `MAP_SCALE` → DOCUMENTED (M).
     - TMC-2 ortho: its PDS4 label has no cartography block. Its `isda:System_Level_Coordinates` corners map about 8 000–9 000 px (about 40 km) outside the raster (M), so they cannot serve as a cross-check → INFERRED.
6. Never used for the NAC PDS4 orthos: GDAL's transform is wrong there (A007, S12). Those keep `"georef": "label"`.

## 3. `pairs.prepare_window_pair(..., centre_sample: int | None = None)` (C11 addition)
Keyword-only, default None (= `samples // 2`, today's behaviour). The source window's samples are centred on `centre_sample`, clamped exactly as lines are (`s0 = min(max(centre_sample − win_s // 2, 0), samples − win_s)`). Out of range → `ValueError` (programmer error, like `centre_line`).

## 4. `src/lunar_reg/cross.py` (new, C28)
```python
class OverlapStatus(str, Enum):
    OVERLAP = "overlap"
    DISJOINT = "disjoint"                         # expected non-result
    NO_GRID = "no_grid"                           # source has no geometry grid: data gap
    GRID_UNREADABLE = "grid_unreadable"           # failure
    REFERENCE_MISSING = "reference_missing"       # data gap
    REFERENCE_UNREADABLE = "reference_unreadable" # failure
    @property
    def is_failure(self) -> bool   # GRID_UNREADABLE, REFERENCE_UNREADABLE
@dataclass(frozen=True)
class ReferenceSpec:
    name: str; path: str; georef: str; sensor: str; independent: bool
def load_references(path="configs/references.json") -> list[ReferenceSpec]   # ValueError listing every schema problem
@dataclass
class OverlapCandidate:
    source_product_id: str; instrument: str; level: str; reference: str
    status: OverlapStatus
    n_nodes: int; n_inside: int
    centre_line: int | None; centre_sample: int | None
    centre_lat: float | None; centre_lon: float | None
    min_distance_km: float | None      # DISJOINT only: nearest grid node to a valid reference pixel
    overlap_km2: float | None
    overlap_source: str                # ValueSource value; "computed"
    reference_independent: bool
    reference_georef_source: str | None  # GeoReference.source value
    detail: str = ""
    def as_dict(self) -> dict
def overlap_for_grid(product_id: str, instrument: str, level: str, grid: GeometryGrid,
                     spec: ReferenceSpec, geo: GeoReference, valid: ReferenceValidity, *,
                     min_inside: int = 4, nominal_gsd_m: float) -> OverlapCandidate
@dataclass
class ReferenceValidity:      # decimated validity mask of one reference (G40)
    factor: int; mask: np.ndarray; fill_value: float | None; fill_source: str
def reference_validity(spec: ReferenceSpec, geo: GeoReference) -> ReferenceValidity
@dataclass
class OverlapReport:
    candidates: list[OverlapCandidate]; counts: dict[str, int]; samples: dict[str, str]
    def report(self) -> str        # counts per status + first sample per status, printed on every run
    def to_json(self) -> str       # C28 file format
def find_overlaps(raw_root, references: list[ReferenceSpec], *,
                  instruments=("OHRC", "TMC2", "IIRS"), levels=("raw", "calibrated"),
                  min_inside: int = 4) -> OverlapReport
```
Method, per (catalog product with `geometry_grid_path`, reference):
1. **Reference.**
   - `geo` comes from `georef` (§1, §2). An error → one `REFERENCE_UNREADABLE` candidate per product, with the error text.
   - `reference_validity`: one decimated read, `f = ceil(max(w, h) / 2048)`, `out_shape = (ceil(h/f), ceil(w/f))`, `Resampling.nearest`. This is G40; never a full read.
   - Fill value: the declared nodata, else the P1.15 probe's `fill_candidate` from `docs/probes/<stem>_raster.json` when it exists (`fill_source = "probe_inferred"`), else 0 (`fill_source = "assumed_zero"`).
   - The validity mask is computed once per reference, not once per product.
2. **Grid.** A product without a grid → `NO_GRID`. A read error → `GRID_UNREADABLE`.
3. **Overlap test, done in the reference's own projection.**
   - Every grid node: `col, row = geo.lonlat_to_pixel(lon=…, lat=…)`. A node is inside when `0 ≤ col < width`, `0 ≤ row < height`, and `mask[int(row // f), int(col // f)]` is valid.
   - Never compare in lon/lat space. A strip that crosses the pole has corner longitudes spanning most of 0–360°, so a lon/lat bounding box "contains" sites hundreds of km away. That is the most likely cause (I) of the P1.DL "90–100 % box cover" figures, which the per-pixel grids refute (Q-P1.18-1).
4. **`n_inside ≥ min_inside` → `OVERLAP`.**
   - The centre is the inside node farthest from any non-inside node, in grid index space: `scipy.ndimage.distance_transform_edt` on the node mask padded by one False row/column. Ties go to the smallest `(scan index, pixel index)`.
   - `centre_line = grid.scan_lines[i]`, `centre_sample = grid.pixels[j]`, and `centre_lat`/`centre_lon` from the grid.
   - `overlap_km2 = n_inside · median(Δscan_lines) · median(Δpixels) · nominal_gsd_m² / 1e6`, with `overlap_source = "computed"`. The nominal GSD is DOCUMENTED (`constants.SENSORS`).
5. **Otherwise `DISJOINT`.**
   - Sample up to 20 000 grid nodes and up to 20 000 valid decimated reference pixel centres (fixed seed 0). Convert both to unit vectors on the sphere.
   - `min_distance_km` = smallest chord from `scipy.spatial.cKDTree`, converted to arc length with R = 1737.4 km.
6. `reference_independent` and `reference_georef_source` are copied from the spec and `geo`.

The library logs one summary line; `report()` is printed by the caller.

## 5. Site runner (`sites/runner.py`)
`SiteConfig` gains, appended:
- `reference_georef: str = "label"`
- `reference_name: str = ""`
- `reference_independent: bool = True`
- `centres: dict[str, tuple[int, int]] | None = None` (product_id → `(centre_line, centre_sample)`)

`run_site` changes:
- Reference georeference: `georeference_from_raster` when `reference_georef == "raster"`, else `georeference_from_label`.
- When `centres` is given, products without an entry are skipped and counted as `not_in_centres`. Products with an entry pass both centres to `prepare_window_pair`.
- Every saved `PairResult.extra` gains `reference_name`, `reference_independent`, `reference_georef_source` and `reference_georef_note`.
- Unchanged for Vikram: `run_vikram.py` passes none of the new fields, so its behaviour and its tests are unchanged.

## 6. `scripts/run_cross.py` (new)
**`find`:** `run_cross.py find --references configs/references.json --instruments TMC2,IIRS --out data/processed/cross/overlaps.json`
- Calls `find_overlaps`, writes the C28 JSON, and prints `report()`.
- Exit 1 only when an `is_failure` status occurred.

**`run`:** `run_cross.py run --overlaps data/processed/cross/overlaps.json --references configs/references.json --matchers sift,akaze,lightglue --results-root data/processed/results --out-dir data/processed/cross/runs [--instruments …] [--overwrite]`. For each `OVERLAP` candidate, it builds a `SiteConfig`:
- `site = f"cross_{reference}"`
- `reference_label = spec.path`, `reference_georef = spec.georef`, `reference_sensor = spec.sensor`, `reference_name = spec.name`, `reference_independent = spec.independent`
- `instruments = (instrument,)`, `levels = (level,)`, `only = <product tag>`
- `gsd_m = max(nominal source GSD, reference pixel size)` rounded up to 0.5 m
- `window_m = 400 · gsd_m`, `margin_m = 0.5 · window_m`
- `coarse = False`, `prior_shift_m = None`
- `centres = {product_id: (centre_line, centre_sample)}`
- `reference_sun_json = None`, `label_convention_json = None`
- `band_reduction = "pca"`
- `out_dir = <out-dir>/<reference>/<tag>`

It then calls `run_site`, printing each `SiteReport.report()`.

After all candidates it writes the aggregate `data/processed/cross/run_record.json` (C15):
- One `instrument_<inst>_<catalog status>` key per requested instrument.
- `overlap_<status>` counts.
- `pairs_run`, `registrations_ok` and `registrations_failed`.
- Notes:
  - one line per DISJOINT pair, `"<product> vs <reference>: disjoint, nearest <d> km"`;
  - `"<inst>: absent, not run"` for every ABSENT instrument;
  - `"relative only: reference <name> is not independent"` for every pair run against a non-independent reference.
- Artefacts: `overlaps.json` and each sub-run's run record.

This record replaces the inline snippet of Q-P1.18-2 for step 4. Exit 0 when every candidate ran, with failures classified; exit 1 on a setup error.

## 7. Tests the prompt adds (`tests/test_cross_pairs.py`, all offline and synthetic)
| test | asserts |
|---|---|
| raster georef, eqc sphere GeoTIFF + matching `.lbl` bounds | fields equal the transform; `source == DOCUMENTED` |
| same with bounds off by 10 px | `source == INFERRED`, residual in `note` |
| no CRS / rotated transform / `+proj=merc` | `LabelGeoreferenceError` naming the reason |
| `centre_sample` | the window's `col_off` follows it and is clamped at both edges |
| pole-crossing strip vs a reference near (−69.37°, 32.32°) | `DISJOINT`, `min_distance_km > 400`, even though the strip's corner longitudes span > 180° |
| strip over the reference | `OVERLAP`, the centre node is inside the reference and its `centre_line`/`centre_sample` are grid indices |
| all-fill reference | `DISJOINT` (valid mask empty), never `OVERLAP` |
| missing reference path | `REFERENCE_MISSING`, not a failure, counted in `report()` |
| `run_cross.py run` on a synthetic overlap with a SIFT-friendly scene | one OK result whose `extra["reference_independent"]` equals the spec |
