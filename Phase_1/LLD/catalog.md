# LLD — product catalog + scan diagnostics (P1.03)

Produces: C09. Closes: A043 (ingest-9), A044 (ingest-10). Decision: G24 (skip-if-absent).

## 1. `ingest/manifest.py` — classified scans (A043) and product types (A044)
```python
class ScanStatus(str, Enum):
    PARSED = "parsed"
    PARSE_ERROR = "parse_error"
    NOT_A_DATA_PRODUCT = "not_a_data_product"   # browse / geometry / misc label: counted, not an error
    ROOT_MISSING = "root_missing"
    @property
    def is_failure(self) -> bool   # PARSE_ERROR, ROOT_MISSING
@dataclass
class ScanDiagnostics:        # classified-outcomes skill shape; constructible with no arguments
    counts: dict[str, int] = field(default_factory=dict)
    samples: dict[str, str] = field(default_factory=dict)
    def record(self, status: ScanStatus, sample: str) -> None
    def report(self) -> str
def product_type_of(label_path: Path) -> str   # "data" | "browse" | "geometry" | "other"
```
`product_type_of` rules on the lower-cased file name, first match wins: contains `_b_brw_` → `browse`; contains `_g_grd_` → `geometry`; contains `_d_img_` or `_d_cub_` or ends with `_100cm.xml` or is a `.lbl` → `data`; anything else → `other`.
`scan_directory(root, archive="chandrayaan2", sensor=None, strict=False, with_diagnostics=False)`: new keyword `with_diagnostics`; when True it returns `(frame, ScanDiagnostics)`, otherwise the frame only (existing callers unchanged). Labels whose type is not `data` are recorded as `NOT_A_DATA_PRODUCT` and are not parsed into the frame. The manifest gains a column `product_type` appended after `unresolved_fields` in `COLUMNS`. A non-existent `root` → `ROOT_MISSING` and an empty frame.
`lro.scan_lro_directory(root, strict=False, with_diagnostics=False)` gets the same keyword and statuses.

## 2. `ingest/catalog.py` (new, C09)
Search roots (relative to `raw_root`), glob patterns, level rule:
| instrument | globs | level |
|---|---|---|
| OHRC | `ohrc_vikram/*/data/**/*_d_img_*.xml`, `ch2/ohrc/*/data/**/*_d_img_*.xml` | token 3 of the stem (`ch2_ohr_<tok>_...`): `nrp` → raw, `ncp` → calibrated, other → unknown |
| TMC2 | `ch2/tmc2/*/data/**/*_d_img_*.xml`, `ch2/tmc2/*/data/**/*_d_oth_*.xml`, `ch2/tmc2/*/data/**/*_d_dtm_*.xml` | `nrn`/`nrp`… → first letter after `ch2_tmc_`: `n?r?` raw when token[1] == "r", calibrated when token[1] == "c", `oth`/`dtm` → derived. Token meanings are UNVERIFIED (PRADAN FAQ gives examples only): record `level_source = "inferred_from_filename"` |
| IIRS | `ch2/iirs/*/data/**/*_d_*.xml` | same token rule as TMC2 |
| LRO_NAC | `reference/lro_nac_vikram/NAC_DTM_VIKRAMSITE1_M*_100CM.xml` | derived |
| LRO_NAC_DTM | `reference/lro_nac_vikram/NAC_DTM_VIKRAMSITE1.xml` | derived |
| SELENE_TC | `reference/selene_tc_ortho/*.lbl`, `reference/jaxa_selene_tc*/*/*.lbl` | derived for `TCO_MAP*`, raw otherwise |
`CatalogEntry.geometry_grid_path`: for CH-2 entries, the first file matching `<product dir>/geometry/**/*_g_grd_*.csv` whose name contains the product's timestamp token (`YYYYMMDDTHHMMSSffff`), else None.
Status per instrument: no glob hit and no directory → ABSENT; label(s) found but a data file missing next to one of them (`pds4._find_image` returns a non-existent path or None) → PARTIAL; every label present with its data → PRESENT; any label raising during the minimal read (`read_label` for PDS4, existence + first line for PDS3 `.lbl`) → UNREADABLE (sample = label path + error).
`build_catalog` never raises for missing data. `report()` prints one line per instrument (`<INSTRUMENT>: <status>, <n> product(s), e.g. <id>`), then the ScanDiagnostics report.

## 3. CLI (`cli.py`, `catalog` subcommand only)
`lunar-reg catalog [--raw-root data/raw] [--json PATH]` → prints `report()`; `--json` writes `{"status": {...}, "entries": [...]}` (paths as strings); exit 1 only when any instrument is UNREADABLE (G24).

## 4. Tests the prompt adds (`tests/test_catalog.py`)
Empty `tmp_path` → every instrument ABSENT, exit 0; a fake OHRC product tree (label + `.img`) → PRESENT with `level="raw"` for an `nrp` name and `calibrated` for `ncp`; label without image → PARTIAL; a browse label → NOT_A_DATA_PRODUCT counted; malformed XML → UNREADABLE; `product_type_of` table-driven cases.
