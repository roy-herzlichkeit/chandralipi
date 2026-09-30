# CONTRACTS — frozen cross-phase interfaces

Rules: a contract is frozen from the commit of its producer prompt. Names, signatures, field names, enum members and values, defaults, file formats and JSON keys below are matched character for character. A later prompt may only **add** an optional keyword argument with a default, or a new enum member where the contract says "open"; everything else is an escalation (`QUESTIONS.md` → architect). Each contract's proof is `Phase_<p>/harness/tests/test_contracts_P<p>.py::test_C<nn>_*` (G16); consumer preflights re-run it with `-k C<nn>`.

Index

| ID | name | module / file | producer | consumers |
|---|---|---|---|---|
| C01 | `ValueSource`, `Sourced` | `src/lunar_reg/provenance.py` | P0.07 | all |
| C02 | `RunStatus`, `RunOutcome` | `src/lunar_reg/pipeline.py` | P0.09 | 1, 2, 1B, 3 |
| C03 | `PipelineConfig`, `register_pair` | `src/lunar_reg/pipeline.py` | P0.09 (fields added P1.10, P2.05) | 1, 2, 1B, 3 |
| C04 | `PairResult` v2 + index columns + extra keys | `src/lunar_reg/results.py` | P0.10 | 1, 2, 1B, 3 |
| C05 | `failures.parquet`, `StoreReport` | `src/lunar_reg/results.py` | P0.10 | 1, 2, 1B, 3 |
| C06 | `Transform`, `estimate_transform` | `src/lunar_reg/align/estimate.py` | P0.07 | 1, 2, 1B, 3 |
| C07 | `EccStatus`, `ecc_refine`, `refine_full` detail | `src/lunar_reg/align/refine.py` | P0.08 | 1, 2, 1B, 3 |
| C08 | `data/raw/DOWNLOADS.json`, `DownloadStatus` | `src/lunar_reg/ingest/downloads.py` | P1.01 | 1, 4 |
| C09 | `InstrumentStatus`, `ProductCatalog` | `src/lunar_reg/ingest/catalog.py` | P1.03 | 1, 2, 1B |
| C10 | `GeoReference`, `georeference_from_label` | `src/lunar_reg/ingest/lro.py` | P1.04 | 1, 2, 1B, 3 |
| C11 | `PriorSource`, `PrepStatus`, `WindowPair`, `prepare_window_pair` | `src/lunar_reg/pairs.py` (+ `PriorSource` in `ingest/overlap.py`) | P1.06 / P1.13 | 1, 2, 1B, 3 |
| C12 | preprocessing presets | `src/lunar_reg/preprocess/presets.py` | P1.10 | 1, 2, 1B, 3 |
| C13 | `SunGeometry`, `AzimuthFit` | `src/lunar_reg/ingest/sun.py` | P1.11 | 1, 1B |
| C14 | `AgreementResult`, `cross_matcher_agreement` | `src/lunar_reg/eval/agreement.py` | P1.12 | 1, 1B |
| C15 | `run_record.json`, `RunRecord` | `src/lunar_reg/runrecord.py` | P0.07 | all RUN prompts |
| C16 | device profile JSON, `DeviceProfile` | `src/lunar_reg/device.py`, `configs/device_profiles/*.json` | P2.02 | 2, 3, 4 |
| C17 | `MemoryReading`, `free_memory_bytes` | `src/lunar_reg/device.py` | P2.01 | 2, 3, 4 |
| C18 | `TileStatus`, `TileDiagnostics`, `TiledMatcher.match_arrays(prior=)` | `src/lunar_reg/match/tiled.py` | P2.06 | 2, 1B, 3 |
| C19 | `NativeStatus`, `refine_native_arrays` | `src/lunar_reg/align/native.py` | P2.08 | 2, 3 |
| C20 | `data/processed/vikram/exp1_gate.json` | file | P1.20 | 1B, 3 |
| C21 | `render_shaded_relief`, `pooled_consensus` | `src/lunar_reg/eval/render.py`, `src/lunar_reg/consensus.py` | P1B.01 / P1B.03 | 1B only (no later phase consumes it; 1B may be skipped, G02) |
| C22 | `JobDescriptor` | `src/lunar_reg/distributed/job.py` | P3.01 | 3, 4 |
| C23 | `JobStatus`, `JobResult`, result files | `src/lunar_reg/distributed/outcome.py` | P3.02 | 3, 4 |
| C24 | `JobQueue` protocol, `Lease`, `QueueStats` | `src/lunar_reg/distributed/queue.py` | P3.04 | 3, 4 |
| C25 | `process_job`, `run_worker` | `src/lunar_reg/distributed/worker.py` | P3.05 | 3, 4 |
| C26 | `reduce_run`, `ReduceOutcome` | `src/lunar_reg/distributed/reducer.py` | P3.06 | 3, 4 |
| C27 | `RedisJobQueue`, `configs/hosts.json` schema | `src/lunar_reg/distributed/redis_queue.py` | P4.01 / P4.04 | 4 |

---

## C01 — provenance enum (P0.07)
```python
class ValueSource(str, Enum):
    MEASURED = "measured"      # a run on this project's data or hardware produced it
    COMPUTED = "computed"      # derived deterministically from measured/documented inputs
    DOCUMENTED = "documented"  # read from a cited external document or archive metadata
    INFERRED = "inferred"      # a fit or reasoning step, not documented
    UNKNOWN = "unknown"

@dataclass(frozen=True)
class Sourced:
    value: float | int | str | None
    source: ValueSource
    note: str = ""
    def as_dict(self) -> dict   # {"value": value, "source": source.value, "note": note}
```
Test: `test_C01_members` (exact members and values), `test_C01_sourced_as_dict`.

## C02 — pair outcome (P0.09)
```python
class RunStatus(str, Enum):
    OK = "ok"
    TOO_FEW_MATCHES = "too_few_matches"
    ESTIMATION_FAILED = "estimation_failed"
    TOO_FEW_INLIERS = "too_few_inliers"
    MATCHER_ERROR = "matcher_error"
    REFINEMENT_FAILED = "refinement_failed"
    EVAL_FAILED = "eval_failed"
    PREPROCESS_FAILED = "preprocess_failed"   # member exists from P0.09; first produced by P1.10
    OOM = "oom"                               # member exists from P0.09; first produced by P2.05
    @property
    def is_failure(self) -> bool   # every member except OK

@dataclass
class RunOutcome:
    pair_id: str
    status: RunStatus
    result: PairResult | None = None
    detail: str = ""
    extra: dict = field(default_factory=dict)
    @property
    def ok(self) -> bool
```
All nine members are introduced together in P0.09 (the P0 contract test checks all nine).
`RunOutcome.extra` on every outcome (OK or not) contains the keys `source_id, reference_id, source_sensor, reference_sensor, matcher, model, stage` plus every key of `PipelineConfig.extra`. `stage` ∈ {`"match"`, `"estimate"`, `"refine"`, `"eval"`, `"preprocess"`, `"done"`}. Failures after matching also carry `n_raw_matches` (int); failures after RANSAC also carry `n_ransac_inliers` (int). `register_pair` never raises for a bad pair.
Test: `test_C02_members`, `test_C02_failure_extra_keys`.

## C03 — pipeline config and entry point (P0.09; fields added by P1.10 and P2.05)
```python
@dataclass
class PipelineConfig:
    matcher: str = "akaze"
    model: str = "homography"
    ransac_threshold_px: float = 3.0
    use_ecc: bool = True
    ecc_prefilter: str = "none"
    min_matches: int = 8
    min_inliers: int = 8
    n_bootstrap: int = 40
    gsd_m: float | None = None
    extra: dict = field(default_factory=dict)
    refit_threshold_px: float = 1.0        # P0.09
    seed: int = 0                          # P0.09
    ecc_max_shift_px: float = 3.0          # P0.09
    nodata: float | None = None            # P0.09; value marking invalid pixels in both images
    preprocess: str = "none"               # P1.10; one of C12 PRESET_NAMES (default changed only by P1.19, G09)
    device: str | None = None              # P2.05; None = lunar_reg.device.get_device()
    precision: str = "auto"                # P2.05; "auto" | "fp16" | "fp32"

def register_pair(
    source: np.ndarray, reference: np.ndarray, pair_id: str,
    config: PipelineConfig | None = None,
    source_id: str = "", reference_id: str = "",
    source_sensor: str = "", reference_sensor: str = "",
    source_sun: tuple[float, float] | None = None,
    reference_sun: tuple[float, float] | None = None,
    synthetic: bool = False, notes: str = "",
    source_valid: np.ndarray | None = None,       # P0.09; bool mask, True = valid pixel
    reference_valid: np.ndarray | None = None,    # P0.09
) -> RunOutcome
```
Stage order: preprocess (P1.10) → match → min_matches → estimate (`seed=config.seed`) → min_inliers → refine_full (`threshold_px=config.refit_threshold_px`) → min_inliers re-check ("after refit") → metrics/uniformity/conditioning → `PairResult`.
Test: `test_C03_fields_and_defaults` (Phase 0 fields; P1 and P2 contract tests extend it for their fields), `test_C03_signature`.

## C04 — stored result, schema v2 (P0.10)
```python
SCHEMA_VERSION = 2
PAIR_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]*$"

@dataclass
class PairResult:
    pair_id: str
    source_id: str
    reference_id: str
    source_sensor: str
    reference_sensor: str
    matcher: str
    src_pts: np.ndarray                 # (N,2) float64, ALL raw matcher correspondences (G34)
    dst_pts: np.ndarray
    inlier_mask: np.ndarray | None      # (N,) bool, final (refit) inliers over the raw set
    transform: np.ndarray               # final transform, 2x3 or 3x3 float64, source px -> reference px
    metrics: dict = field(default_factory=dict)
    uniformity: dict = field(default_factory=dict)
    conditioning: dict = field(default_factory=dict)
    source_image: np.ndarray | None = None
    reference_image: np.ndarray | None = None
    synthetic: bool = False
    notes: str = ""
    extra: dict = field(default_factory=dict)
    created_utc: str = ""
    ransac_mask: np.ndarray | None = None        # v2: (N,) bool, first-pass RANSAC inliers
    pre_ecc_transform: np.ndarray | None = None  # v2: transform after refit, before ECC
    schema_version: int = SCHEMA_VERSION         # v2: version the record was written with
    # properties
    n_matches -> int          # len(src_pts)
    n_inliers -> int          # inlier_mask.sum(), or n_matches when None
    n_ransac_inliers -> int | None
    def index_row(self) -> dict
```
`__post_init__` raises `ValueError` when `pair_id` does not match `PAIR_ID_PATTERN`, or when any mask length differs from N.
`index_row()` top-level keys, exactly: `pair_id, source_id, reference_id, source_sensor, reference_sensor, matcher, n_matches, n_ransac_inliers, n_inliers, inlier_ratio, synthetic, notes, created_utc, schema_version`, then `m_<k>` (metrics), `u_<k>` (uniformity), `c_<k>` (conditioning), `x_<k>` (extra). Values: numpy scalars → Python scalars; lists/tuples/ndarrays/dicts → JSON string (`json.dumps(..., sort_keys=True)`); any other object → `TypeError` naming the key.
`.npz` keys: `src_pts, dst_pts, transform, meta` always; `inlier_mask, ransac_mask, pre_ecc_transform, source_image, reference_image` when not None. `meta` JSON carries every scalar field plus `source_scale`, `reference_scale`, `schema_version`.
`save_pair(result, root, overwrite: bool = False) -> Path`: writes `<root>/pairs/<pair_id>.npz` via a temp file + `os.replace`; raises `FileExistsError` when the file exists and `overwrite` is False.
`load_pair(pair_id, root) -> PairResult`: loads v1 and v2; for v1 records `ransac_mask = None`, `pre_ecc_transform = None`, `schema_version = 1`.

Reserved `extra` keys (writers must use these names when they record the quantity):

| key | type | written by |
|---|---|---|
| `refit_threshold_px`, `ransac_threshold_px`, `min_inliers`, `model`, `seed` | float/int/str | P0.09 (`register_pair`) |
| `refine_stages`, `ecc_status`, `ecc_motion`, `ecc_cc`, `ecc_shift_px` | str/str/str/float/float | P0.09 |
| `matcher_<meta key>` | scalar | P0.09 (copied from `MatchResult.meta`, scalars only) |
| `cv2_version`, `numpy_version` | str | P0.09 |
| `ref_crop_c0`, `ref_crop_r0`, `ref_factor`, `shift_e_m`, `shift_s_m`, `src_win_l0`, `src_win_s0`, `src_win_lines`, `src_win_samples`, `gsd_m`, `crop_geometry_source` | int/int/float/float/float/int/int/int/int/float/str | P0.11, P1.13 |
| `prior_source` | str (C11 `PriorSource` value) | P1.13 |
| `preprocess`, `preprocess_placeholders` | str/str | P1.10 |
| `licence` | str | P1.14 (SuperGlue only, G11) |
| `device`, `precision`, `seconds_match`, `seconds_total`, `peak_vram_bytes` | str/str/float/float/int | P2.05 |
| `source_sun_azimuth`, `source_sun_elevation`, `reference_sun_azimuth`, `reference_sun_elevation`, `reference_sun_source` | float/float/float/float/str | P0.09 / P1.16 |

Test: `test_C04_fields`, `test_C04_index_columns`, `test_C04_pair_id_rejected`, `test_C04_overwrite_refused`, `test_C04_v1_loads`.

## C05 — failures and store report (P0.10)
`<root>/failures.parquet`, one row per failed `RunOutcome`, columns exactly: `pair_id, status, detail, stage, matcher, model, source_id, reference_id, source_sensor, reference_sensor, n_raw_matches, n_ransac_inliers, created_utc, schema_version`, then `x_<k>` for every other scalar key in `RunOutcome.extra`. Rows are appended; a row is never rewritten.
```python
def save_failures(outcomes: list[RunOutcome], root) -> Path     # ignores OK outcomes; atomic write
def load_failures(root) -> pandas.DataFrame                     # empty frame when absent

@dataclass
class StoreReport:
    frame: pandas.DataFrame           # the index as written (or as kept)
    n_saved: int
    load_failures: list[tuple[str, str]]   # (pair_id, reason)
    index_written: bool
    index_rows_before: int
    def report(self) -> str

def reindex(root, force: bool = False) -> StoreReport
def save_results(results, root, reindex_all: bool = True, overwrite: bool = False) -> StoreReport
```
`reindex` does not overwrite `index.parquet` when at least one `.npz` failed to load and the new index would have fewer rows than the old one, unless `force=True`; then `index_written=False`. `pipeline.run_batch(pairs, config=None, root=None) -> BatchReport` persists OK results with `save_results` and failures with `save_failures` when `root` is given.
Test: `test_C05_failures_columns`, `test_C05_reindex_keeps_index`, `test_C05_run_batch_persists_failures`.

## C06 — robust fit (P0.07)
```python
TRANSFORM_MODELS = ("homography", "affine", "partial_affine")

@dataclass
class Transform:
    matrix: np.ndarray       # 3x3 (homography) or 2x3 (affine, partial_affine), float64
    model: str
    n_inliers: int
    n_total: int
    estimator: str = "unknown"   # "USAC_MAGSAC" | "RANSAC" | "LSQ"
    seed: int | None = None
    inlier_ratio -> float
    def apply(self, pts) -> np.ndarray

def estimate_transform(result: MatchResult, model: str = "homography",
                       threshold_px: float = 2.0, max_iters: int = 10_000,
                       confidence: float = 0.9999, seed: int = 0) -> tuple[Transform, MatchResult]
```
Behaviour: `cv2.setRNGSeed(seed)` immediately before the OpenCV call; points are shifted by their float64 centroids before the float32 cast and the shift is composed back in float64; two calls with identical input return bit-identical matrices and masks. Raises `ValueError` as today.
Test: `test_C06_signature`, `test_C06_deterministic`, `test_C06_large_coordinates`.

## C07 — ECC and refinement (P0.08)
```python
class EccStatus(str, Enum):
    APPLIED = "applied"
    SKIPPED_NO_SIMILARITY_MOTION = "skipped_no_similarity_motion"   # partial_affine (G35)
    SKIPPED_SINGULAR = "skipped_singular"
    SKIPPED_DISABLED = "skipped_disabled"        # use_ecc False or images missing
    NOT_CONVERGED = "not_converged"
    REJECTED_DISPLACEMENT = "rejected_displacement"

@dataclass
class EccOutcome:
    transform: Transform       # refined when APPLIED, else the input transform unchanged
    status: EccStatus
    cc: float                  # nan unless APPLIED
    motion: str | None         # "homography" | "affine" | None
    shift_px: float | None     # max probe displacement between input and ECC result
    detail: str = ""

ECC_MAX_SHIFT_PX = Sourced(3.0, ValueSource.INFERRED, "equals the default RANSAC threshold")

def ecc_refine(transform: Transform, source: np.ndarray, reference: np.ndarray, *,
               max_iterations: int = 200, epsilon: float = 1e-7, gaussian_blur: int = 5,
               prefilter: str = "none", nodata: float | None = None,
               max_shift_px: float = 3.0,
               source_valid: np.ndarray | None = None,        # bool, True = valid (input mask)
               reference_valid: np.ndarray | None = None      # bool, True = valid (template mask)
               ) -> EccOutcome
# masks: explicit *_valid wins; else (image != nodata) when nodata is set; else none. With any mask,
# cv2.findTransformECCWithMask(template=reference, input=source, templateMask, inputMask, ...) is used
# (present in cv2 4.14, measured 2026-09-30); without masks, cv2.findTransformECC as today.

def refine_transform_ecc(...same positional args as today..., nodata=None, max_shift_px=3.0) -> tuple[Transform, float]
    # thin wrapper: (outcome.transform, outcome.cc)

def refine_full(result, source=None, reference=None, model="homography", threshold_px=1.0,
                use_ecc=True, ecc_kwargs=None, seed: int = 0) -> tuple[Transform, MatchResult, dict]
```
`refine_full` detail keys, always present: `stages` (list of `"reestimate_on_inliers"`, `"ecc"`), `inliers_after_refit` (int), `pre_ecc_matrix` (ndarray), `ecc_status` (`EccStatus` value str), `ecc_motion`, `ecc_cc` (float or None), `ecc_shift_px` (float or None). Inputs are never mutated. The returned `Transform.matrix` shape equals the input model's shape.
Test: `test_C07_status_members`, `test_C07_affine_stays_affine`, `test_C07_detail_keys`.

## C08 — download manifest (P1.01)
`data/raw/DOWNLOADS.json`:
```json
{"schema": 1,
 "files": [{"path": "data/raw/<...>", "bytes": 0, "sha256": "<64 hex>",
            "source": "PRADAN|ODE|PDS_LROC|PDS_IMG|DARTS|LOCAL",
            "url": "<https url or null>", "product_id": "<id>",
            "instrument": "OHRC|TMC2|IIRS|LRO_NAC|LRO_NAC_DTM|LRO_NAC_EDR|SELENE_TC|SELENE_DTM|ODE_METADATA|DOC",
            "role": "data|label|geometry|browse|metadata|misc|doc",
            "downloaded_utc": "<ISO-8601 Z>", "recorded_by": "P1.DL|fetch_public|manual"}],
 "failures": [{"url": "<url>", "http_status": 0, "error": "<text>", "utc": "<ISO-8601 Z>"}]}
```
`path` is repo-relative POSIX. One entry per path (re-recording replaces it).
```python
class DownloadStatus(str, Enum):
    OK = "ok"; MISSING = "missing"; SIZE_MISMATCH = "size_mismatch"
    HASH_MISMATCH = "hash_mismatch"; UNRECORDED = "unrecorded"; HTTP_ERROR = "http_error"
    is_failure -> bool    # MISSING, SIZE_MISMATCH, HASH_MISMATCH, HTTP_ERROR
    is_suspicious -> bool # UNRECORDED
def record_file(path, *, source, product_id, instrument, role, url=None,
                recorded_by="manual", manifest=DEFAULT_MANIFEST) -> DownloadEntry
def record_failure(url, http_status, error, manifest=DEFAULT_MANIFEST) -> None
def verify_downloads(manifest=DEFAULT_MANIFEST, raw_root="data/raw", check_hash=True,
                     scan_unrecorded=True) -> DownloadDiagnostics   # .counts, .samples, .report()
```
Test: `test_C08_roundtrip`, `test_C08_statuses`.

## C09 — product catalog (P1.03)
```python
INSTRUMENTS = ("OHRC", "TMC2", "IIRS", "LRO_NAC", "LRO_NAC_DTM", "SELENE_TC")
class InstrumentStatus(str, Enum):
    PRESENT = "present"; ABSENT = "absent"; PARTIAL = "partial"; UNREADABLE = "unreadable"
@dataclass
class CatalogEntry:
    instrument: str; product_id: str; label_path: Path; image_path: Path | None
    level: str          # "raw" | "calibrated" | "derived" | "unknown"
    product_type: str   # "data" | "browse" | "geometry" | "other"
    geometry_grid_path: Path | None
@dataclass
class ProductCatalog:
    entries: list[CatalogEntry]
    status: dict[str, InstrumentStatus]     # one key per INSTRUMENTS member
    diagnostics: ScanDiagnostics            # ingest/manifest.py (P1.03): counts per ScanStatus + first sample
    def products(self, instrument: str, product_type: str = "data") -> list[CatalogEntry]
    def report(self) -> str
def build_catalog(raw_root="data/raw", instruments=INSTRUMENTS) -> ProductCatalog
```
Search roots per instrument are fixed in `Phase_1/LLD/catalog.md`. PARTIAL = labels without their data file (or the reverse). The CLI `lunar-reg catalog` prints `report()` and exits 0 unless an instrument is UNREADABLE.
Test: `test_C09_empty_root_all_absent`, `test_C09_present_ohrc`.

## C10 — map georeference (P1.04)
```python
@dataclass(frozen=True)
class GeoReference:
    crs_proj4: str
    x0_m: float            # projected x of the outer upper-left corner of pixel (0, 0)
    y0_m: float            # projected y of that corner; rows increase southward: y = y0 - row * psy
    pixel_size_x_m: float  # > 0
    pixel_size_y_m: float  # > 0
    width: int
    height: int
    source: ValueSource
    note: str = ""
    # keyword-only coordinates: geometry_grid.lonlat_to_pixel(grid, lat, lon) takes lat first,
    # so positional calls here are forbidden to make an axis swap impossible
    def pixel_to_xy(self, *, col, row) -> tuple[np.ndarray, np.ndarray]           # returns (x, y)
    def xy_to_pixel(self, *, x, y) -> tuple[np.ndarray, np.ndarray]               # returns (col, row)
    def lonlat_to_pixel(self, *, lon, lat) -> tuple[np.ndarray, np.ndarray]       # returns (col, row)
    def pixel_to_lonlat(self, *, col, row) -> tuple[np.ndarray, np.ndarray]       # returns (lon, lat)
    def affine(self) -> affine.Affine
    def as_dict(self) -> dict      # JSON-safe, round-trips via GeoReference.from_dict
    @classmethod
    def from_dict(cls, d: dict) -> GeoReference
class LabelGeoreferenceError(ValueError): ...
def georeference_from_label(label_path) -> GeoReference
```
Pixel coordinates use the corner convention: `(col, row) = (0, 0)` is the outer corner of the first pixel. The upper-left x sign is chosen by the rule in `Phase_1/LLD/lro_georeference.md` (fit to `cart:Bounding_Coordinates`); `source` is `DOCUMENTED` when the label value is used as written and `INFERRED` when its sign is flipped.
Test: `test_C10_synthetic_label`, `test_C10_roundtrip` (+ data-marked `test_C10_real_nac_sign`).

## C11 — window-pair preparation (P1.06 `PriorSource`; P1.13 the rest)
```python
# src/lunar_reg/ingest/overlap.py (P1.06), re-exported by lunar_reg.pairs
class PriorSource(str, Enum):
    GEOMETRY_GRID = "geometry_grid"; LABEL_CORNERS = "label_corners"; BBOX = "bbox"

# src/lunar_reg/pairs.py (P1.13)
class PrepStatus(str, Enum):
    OK = "ok"; LABEL_UNREADABLE = "label_unreadable"; NO_FOOTPRINT = "no_footprint"
    OUTSIDE_REFERENCE = "outside_reference"; EMPTY_REFERENCE = "empty_reference"; READ_FAILED = "read_failed"
@dataclass
class WindowPair:
    source: np.ndarray; reference: np.ndarray                 # 2-D uint8 at gsd_m, 0 = nodata
    source_valid: np.ndarray; reference_valid: np.ndarray     # bool
    prior: np.ndarray               # 3x3 float64: working-source px -> working-reference px
    prior_source: PriorSource
    gsd_m: float
    source_window: tuple[int, int, int, int]      # (row_off, col_off, height, width), source native px
    reference_window: tuple[int, int, int, int]   # reference native px
    source_native_gsd_m: float; reference_native_gsd_m: float
    source_to_native: np.ndarray    # 3x3: working-source px -> source native px (pixel-centre convention, see below)
    reference_to_native: np.ndarray # 3x3: working-reference px -> reference native px (pixel-centre convention)
    shift_m: tuple[float, float]    # (east, south) applied to the reference window
    source_id: str; reference_id: str
    provenance: dict[str, str]      # quantity -> ValueSource value
    def geometry_extra(self) -> dict   # the C04 crop-geometry extra keys, crop_geometry_source="recorded"
@dataclass
class PrepOutcome:
    status: PrepStatus
    pair: WindowPair | None = None
    detail: str = ""
def prepare_window_pair(source_label, reference_path, reference_geo: GeoReference, *,
                        gsd_m: float, window_m: float, margin_m: float,
                        shift_m: tuple[float, float] = (0.0, 0.0),
                        centre_line: int | None = None,
                        geometry_grid_path=None,
                        band_reduction: str = "first") -> PrepOutcome   # "first" | "mean" | "pca" for multi-band sources
```
Pixel-centre convention for every resampling matrix in this plan (C11, C19): with native window size `(W, H)`, working size `(w, h)` = the `cv2.resize` output, `fx = W / w`, `fy = H / h` and window offset `(x0, y0)`: `to_native = [[fx, 0, x0 + (fx − 1)/2], [0, fy, y0 + (fy − 1)/2], [0, 0, 1]]` (this is exactly `cv2.resize`'s sampling geometry).
Test: `test_C11_members`, `test_C11_synthetic_prepare`.

## C12 — preprocessing presets (P1.10)
```python
PRESET_NAMES = ("none", "ohrc_nac", "clahe_shadow")
@dataclass
class PresetOutcome:
    ok: bool
    source: np.ndarray | None        # uint8, same shape as input
    reference: np.ndarray | None
    detail: str
    history: list[dict]              # per side: {"side", "step", "status", "reason"}
    uses_placeholders: list[str]     # names of PLACEHOLDER params actually used
def apply_preset(name: str, source, reference, *, source_valid=None, reference_valid=None,
                 nodata: float | None = 0) -> PresetOutcome
```
Presets run no geometric step (pair preparation already fixed the GSD), so pixel coordinates are unchanged. Unknown name → `ValueError`.
Test: `test_C12_names`, `test_C12_none_is_identity`, `test_C12_nodata_preserved`.

## C13 — sun geometry (P1.11)
```python
@dataclass(frozen=True)
class SunGeometry:
    azimuth_deg: float | None
    elevation_deg: float | None
    azimuth_source: ValueSource
    elevation_source: ValueSource
    azimuth_frame: str       # "north_clockwise" (SPICE) | "grid_up_clockwise" (DTM fit) | "label_unverified" (ISRO label)
    note: str = ""
    def as_tuple(self) -> tuple[float, float] | None
    def as_dict(self) -> dict
@dataclass
class AzimuthFit:
    azimuth_deg: float; ncc_peak: float
    azimuths: np.ndarray; ncc: np.ndarray
    second_peak_deg: float; second_peak_ncc: float; peak_margin: float
    n_valid_px: int
def lambert_shade(dtm, posting_m, azimuth_deg, elevation_deg) -> np.ndarray   # float32 in [0, 1]
def fit_sun_azimuth(dtm, posting_m, image, elevation_deg, *, valid=None, step_deg=1.0) -> AzimuthFit
def sun_from_ode_metadata(json_path, product_name) -> SunGeometry   # elevation = 90 - Incidence_angle
def sun_from_label(product: PDS4Product) -> SunGeometry            # OHRC label fields, DOCUMENTED, frame "label_unverified"
def azimuth_elevation_from_vector(sun_body_xyz, lat_deg: float, lon_deg: float) -> tuple[float, float]
    # pure geometry: body-fixed sun vector (any length) seen from surface point (lat, lon east-positive,
    # sphere) -> (azimuth clockwise from north in [0, 360), elevation above the local horizon), degrees
def sun_from_spice(utc: str, lat_deg: float, lon_deg: float, kernels_dir) -> SunGeometry
    # spiceypy (optional extra `spice`): Sun position in IAU_MOON from the generic kernels (LSK, PCK, DE SPK)
    # at `utc`; both sources ValueSource.COMPUTED; azimuth_frame "north_clockwise"
```
Test: `test_C13_synthetic_azimuth_recovered`, `test_C13_ode_elevation`, `test_C13_vector_geometry` (+ data-marked `test_C13_spice_kernels`).

## C14 — cross-matcher agreement (P1.12)
```python
@dataclass
class AgreementResult:
    matchers: tuple[str, ...]
    pairwise_px: dict[str, float]     # "a|b" (sorted names) -> max probe distance, reference px
    max_disagreement_px: float        # nan when fewer than 2 transforms
    threshold_px: float
    passes: bool                      # n_matchers >= 2 and max_disagreement_px <= threshold_px
    n_matchers: int
    gsd_m: float | None
    max_disagreement_m: float | None
def cross_matcher_agreement(transforms: dict[str, np.ndarray], shape: tuple[int, int], *,
                            threshold_px: float = 1.0, gsd_m: float | None = None) -> AgreementResult
```
Probes are the four source-image corners plus the centre. Input transforms are the **pre-ECC** matrices (C04 `pre_ecc_transform`).
Test: `test_C14_identical`, `test_C14_known_offset`.

## C15 — run record (P0.07)
`<out_dir>/run_record.json`:
```json
{"schema": 1, "command": ["..."], "params": {}, "started_utc": "...", "finished_utc": "...",
 "git_sha": "<40 hex>", "git_dirty": false, "host": "...", "device": "...",
 "versions": {"python": "...", "numpy": "...", "cv2": "...", "torch": "...", "kornia": "..."},
 "outcome_counts": {"<status>": 0}, "artefacts": ["<repo-relative path>"], "notes": ""}
```
```python
@dataclass
class RunRecord: (fields = the JSON keys above)
def start_run(command: list[str], params: dict | None = None) -> RunRecord
def finish_run(record: RunRecord, outcome_counts: dict[str, int], artefacts: list) -> RunRecord
def write_run_record(record: RunRecord, out_dir) -> Path
def read_run_record(path) -> RunRecord
def validate_run_record(path) -> list[str]   # problems; [] = valid
```
`validate_run_record` checks: every key present; `finished_utc` set; `git_sha` 40 hex; every artefact path exists (relative to cwd); counts are ints ≥ 0.
Test: `test_C15_roundtrip`, `test_C15_validate_flags_missing_artefact`.

## C16 — device profile (P2.02)
`configs/device_profiles/<slug>.json`:
```json
{"schema": 1, "slug": "rtx4060-laptop", "device_name": "...", "total_bytes": 0,
 "free_bytes_at_measure": 0, "torch": "...", "cuda": "...", "driver": "...",
 "measured_utc": "...", "run_record": "<path>", "source": "measured",
 "matchers": {"<name>": {"<precision>": {"fixed_bytes": 0, "bytes_per_px": 0.0,
      "max_tile_px": 0, "points": [[256, 0]]}}}}
```
```python
@dataclass
class DeviceProfile:
    slug: str; device_name: str; total_bytes: int; matchers: dict
    measured_utc: str; source: ValueSource; path: Path | None = None
    @classmethod
    def load(cls, path) -> DeviceProfile
    def save(self, path) -> Path
    def plan_tile(self, matcher: str, precision: str, free_bytes: int,
                  safety: float = 0.75) -> TileBudget
def load_profile_for(device_name: str, root="configs/device_profiles") -> DeviceProfile | None
# TileBudget gains: fits: bool, source: ValueSource
```
Test: `test_C16_roundtrip`, `test_C16_plan_tile_fits_flag`.

## C17 — free memory (P2.01)
```python
@dataclass(frozen=True)
class MemoryReading:
    device: str; free_bytes: int; total_bytes: int; source: ValueSource
def free_memory_bytes(device: str) -> MemoryReading
```
`device` values: `"cpu"`, `"cuda"`, `"cuda:<n>"`. CUDA readings come from `torch.cuda.mem_get_info(<n>)` (`MEASURED`); `"cpu"` reads `MemAvailable`/`MemTotal` from `/proc/meminfo` (`MEASURED`); any failure returns `free_bytes=0, total_bytes=0, source=UNKNOWN`, never a nameplate value. `free_vram_bytes(device)` remains and returns `free_memory_bytes(device).free_bytes`.
Test: `test_C17_cpu_reading`, `test_C17_cuda_index` (gpu).

## C18 — prior-driven tiling (P2.06)
```python
class TileStatus(str, Enum):
    OK = "ok"; EMPTY = "empty"; OUT_OF_REFERENCE = "out_of_reference"
    SKIPPED_NODATA = "skipped_nodata"; MATCHER_ERROR = "matcher_error"; OOM = "oom"
@dataclass
class TileOutcome:
    index: int; status: TileStatus; n_matches: int; detail: str
    source_window: tuple[int, int, int, int]; reference_window: tuple[int, int, int, int] | None
@dataclass
class TileDiagnostics:
    outcomes: list[TileOutcome]
    counts -> dict[str, int]; samples -> dict[str, TileOutcome]; n_failed -> int
    def record(self, outcome: TileOutcome) -> None
    def report(self) -> str
class TiledMatcher:
    def __init__(self, matcher, tile_px=None, overlap=0.25, max_matches_per_tile=256,
                 progress=True, deduplicate_overlaps=True, tolerance_px=1.5,
                 min_valid_fraction: float = 0.5, ref_margin_px: int = 32)
    def match_arrays(self, source, reference, prior: np.ndarray | None = None,
                     source_valid=None, reference_valid=None,
                     offset_prior: tuple[int, int] | None = None) -> MatchResult
    last_diagnostics: TileDiagnostics | None
```
`prior` maps source px → reference px (3×3). Each reference window is the bounding box of the prior-mapped source tile corners plus `ref_margin_px`, clipped to the reference; the tile's matches are lifted back into full-image coordinates. `offset_prior` is converted to a translation prior. Per-tile exceptions become `MATCHER_ERROR` or `OOM` outcomes (`torch.OutOfMemoryError` is caught before `RuntimeError`).
Test: `test_C18_members`, `test_C18_scaled_prior`, `test_C18_error_tile_counted`.

## C19 — native-GSD refinement (P2.08)
```python
class NativeStatus(str, Enum):
    OK = "ok"; TOO_FEW_MATCHES = "too_few_matches"; ESTIMATION_FAILED = "estimation_failed"
    DRIFT_EXCEEDED = "drift_exceeded"; TILE_FAILURES = "tile_failures"
@dataclass
class NativeRefinement:
    status: NativeStatus
    transform: np.ndarray | None     # 3x3: source-native px -> reference-native px
    n_matches: int; n_inliers: int
    drift_coarse_px: float | None    # max probe distance vs the coarse transform, in coarse (working) px
    tiles: TileDiagnostics | None
    detail: str
def lift_to_native(coarse: np.ndarray, source_to_native: np.ndarray,
                   reference_to_native: np.ndarray) -> np.ndarray
def refine_native_arrays(source_native: np.ndarray, reference_native: np.ndarray,
                         prior_native: np.ndarray, *, source_native_gsd_m: float,
                         reference_native_gsd_m: float, matcher: str = "sift",
                         tile_px: int | None = None, model: str = "homography",
                         coarse_gsd_m: float = 4.0, max_drift_coarse_px: float = 1.0,
                         seed: int = 0) -> NativeRefinement
```
Matching happens at the reference native GSD (G10): the source window is resampled to `reference_native_gsd_m`, matched tile by tile with `prior`, fitted, and the result re-expressed in source-native px.
Test: `test_C19_lift_roundtrip`, `test_C19_synthetic_refine`.

## C20 — exp-1 gate (P1.20)
`data/processed/vikram/exp1_gate.json`:
```json
{"schema": 1, "decision": "BUILD_1B|SKIP_1B",
 "rule": "SKIP_1B iff every 2023 strip has >=1 matcher with n_inliers>=20 and u_score>=0.7 and agreement passes (<1 px pre-ECC, >=2 matchers)",
 "strips": [{"tag": "...", "best_matcher": "...", "status": "...", "n_inliers": 0,
             "u_score": 0.0, "agreement_px": 0.0, "passes_targets": false}],
 "n_strips_passing": 0, "reference_sun": {}, "run_record": "data/processed/vikram/exp1/run_record.json",
 "created_utc": "..."}
```
`reference_sun` is a C13 `SunGeometry.as_dict()`. `strips` has exactly the three 2023 tags of G27.
Test: Phase_1 `test_contracts_P1.py::test_C20_schema` (validates the file when present; P1.20's check requires it present).

## C21 — illumination bridge (P1B.01 / P1B.03)
```python
# eval/render.py
def render_shaded_relief(dtm: np.ndarray, posting_m: float, azimuth_deg: float,
                         elevation_deg: float, *, cast_shadows: bool = True,
                         ambient: float = 0.04, nodata: float | None = None) -> np.ndarray   # uint8, 0 = nodata
# consensus.py
class ConsensusStatus(str, Enum):
    OK = "ok"; TOO_FEW_MATCHERS = "too_few_matchers"; DISAGREEMENT = "disagreement"
    ESTIMATION_FAILED = "estimation_failed"
@dataclass
class ConsensusResult:
    status: ConsensusStatus
    transform: Transform | None
    per_matcher: dict[str, Transform | None]
    pooled: MatchResult
    agreement: AgreementResult | None
    contributing: list[str]
    detail: str
def pooled_consensus(results: dict[str, MatchResult], shape: tuple[int, int], *,
                     model: str = "homography", threshold_px: float = 3.0,
                     agreement_threshold_px: float = 1.0, min_matchers: int = 2,
                     seed: int = 0, refit_threshold_px: float = 1.0) -> ConsensusResult
```
Test: `test_C21_render_uint8`, `test_C21_consensus_agree`, `test_C21_consensus_disagree`.

## C22 — job descriptor (P3.01)
```python
JOB_SCHEMA = 1
@dataclass(frozen=True)
class JobDescriptor:
    run_id: str; pair_id: str; tile_index: int
    source_path: str; reference_path: str                 # repo-relative POSIX
    source_window: tuple[int, int, int, int]             # (row_off, col_off, height, width), native px
    reference_window: tuple[int, int, int, int]
    prior: tuple[float, ...]                             # 9 floats, row-major, source-window px -> reference-window px at working_gsd_m
    working_gsd_m: float; source_native_gsd_m: float; reference_native_gsd_m: float
    preprocess: str; matcher: str; precision: str        # "fp16" | "fp32"
    tile_px: int; est_vram_bytes: int; base_seed: int
    reference_georef: dict | None = None                 # C10 as_dict
    schema: int = JOB_SCHEMA
    def to_json(self) -> str      # json.dumps(asdict, sort_keys=True, separators=(",", ":"))
    @classmethod
    def from_json(cls, text: str) -> JobDescriptor
    job_id -> str                 # sha256(to_json().encode()).hexdigest()
    seed -> int                   # (base_seed + int(job_id[:8], 16)) % 2**31
```
Test: `test_C22_roundtrip`, `test_C22_job_id_stable`, `test_C22_key_order_irrelevant`.

## C23 — job outcomes and result files (P3.02)
```python
class JobStatus(str, Enum):
    OK = "ok"; NO_MATCHES = "no_matches"; DEGENERATE_OVERLAP = "degenerate_overlap"
    READ_FAILED = "read_failed"; OOM = "oom"; WORKER_LOST = "worker_lost"
    TIMEOUT = "timeout"; MATCHER_ERROR = "matcher_error"
    is_failure -> bool
@dataclass
class JobResult:
    job_id: str; status: JobStatus; n_matches: int
    src_pts: np.ndarray; dst_pts: np.ndarray    # (N,2) float64 in source-native / reference-native px
    scores: np.ndarray | None
    worker_id: str; host: str; device: str
    seconds: float; peak_vram_bytes: int | None; attempt: int; detail: str
    bytes_read: int = 0                         # source + reference window bytes read (P4.02 fills it)
def write_job_result(result: JobResult, results_dir) -> tuple[Path, bool]   # (json path, newly_written)
def read_job_result(job_id: str, results_dir) -> JobResult
class JobDiagnostics:
    def record(self, result: JobResult, duplicate: bool = False) -> None
    counts -> dict[str, int]; samples -> dict[str, str]; n_duplicates -> int
    def report(self) -> str
```
Files `<results_dir>/<job_id>.npz` (`src_pts`, `dst_pts`, optional `scores`) and `<job_id>.json` (all other fields); both written via temp + `os.replace`, JSON last. If `<job_id>.json` exists, nothing is written and `newly_written` is False (at-least-once → exactly-one-result).
Test: `test_C23_roundtrip`, `test_C23_idempotent_write`.

## C24 — queue protocol (P3.04)
```python
@dataclass
class Lease:
    job: JobDescriptor; worker_id: str; lease_id: str; deadline_utc: float; attempt: int
@dataclass
class QueueStats:
    pending: int; leased: int; done: int; failed: int; lost_events: int
class JobQueue(Protocol):
    def put(self, job: JobDescriptor) -> bool                 # False when job_id already known
    def claim(self, worker_id: str, lease_s: float, max_bytes: int | None = None) -> Lease | None
        # max_bytes: only jobs with est_vram_bytes <= max_bytes (None = any); used by P4.03 routing
    def ack(self, lease: Lease, status: JobStatus) -> bool    # False when the lease was already reclaimed
    def reclaim_expired(self) -> list[str]                    # job_ids requeued (each = 1 lost event)
    def renew(self, lease: Lease, lease_s: float) -> bool     # extend a live lease (worker heartbeat); False when already reclaimed
    def stats(self) -> QueueStats
MAX_ATTEMPTS = 3   # a job reclaimed 3 times is closed with WORKER_LOST
class LocalJobQueue:  # SQLite file at <run_dir>/queue.sqlite; process-safe
    def __init__(self, path)
    def close_unfinished(self, status: JobStatus) -> int  # every pending/leased job -> failed(status); used by run_local when all workers died (G36)
```
`run_worker` renews its current lease every `lease_s / 3` seconds from a daemon thread while `process_job` runs, so a long tile is never reclaimed while alive.
Test: `test_C24_put_dedupe`, `test_C24_lease_expiry_counts_lost`, `test_C24_max_attempts`, `test_C24_renew`.

## C25 — worker (P3.05)
```python
def process_job(job: JobDescriptor, device: str, *, matcher_factory=None,
                repo_root=".") -> JobResult          # never raises for a bad job
@dataclass
class WorkerSummary:
    worker_id: str; processed: int; counts: dict[str, int]; seconds: float
def run_worker(queue: JobQueue, results_dir, worker_id: str, device: str, *,
               lease_s: float = 120.0, max_jobs: int | None = None,
               idle_exit_s: float = 5.0, matcher_factory=None,
               max_bytes: int | None = None) -> WorkerSummary   # paths in jobs resolve against the cwd
```
`matcher_factory(name: str, device: str) -> Matcher`; default = `lunar_reg.match.build_matcher`.
Test: `test_C25_process_job_synthetic`, `test_C25_read_failed_classified`.

## C26 — reducer (P3.06)
```python
@dataclass
class ReduceOutcome:
    status: RunStatus
    transform: np.ndarray | None          # 3x3 source-native px -> reference-native px
    n_matches: int; n_inliers: int
    diagnostics: JobDiagnostics
    missing_jobs: list[str]
    result: PairResult | None
    detail: str
def reduce_run(results_dir, jobs: list[JobDescriptor], *, model: str = "homography",
               threshold_px: float = 3.0, refit_threshold_px: float = 1.0,
               seed: int = 0) -> ReduceOutcome
```
Points are concatenated in `(job_id, point index)` order before fitting, so the transform is independent of completion order.
Test: `test_C26_order_independent`, `test_C26_missing_jobs_reported`.

## C27 — multi-host (P4.01 / P4.04)
```python
class RedisJobQueue:     # implements C24 (incl. renew)
    def __init__(self, url: str, run_id: str, *, stream_prefix: str = "lunar",
                 group: str = "workers", client=None)   # url: redis:// or rediss://; client: injected (protocol=2)
    def reclaim_expired(self, lease_s: float | None = None) -> list[str]
    def register_tiers(self, tiers) -> None   # P4.03 Tier(name, max_bytes) list
    def purge(self) -> int      # delete every key of this run; returns keys deleted
```
Routing is by **tier streams**, never by skipping entries (G36). `put(job, tier: str | None = None)` appends to stream `<p>:jobs:<tier>`; every tier is registered in hash `<p>:tiers` (name → `max_bytes`). A named tier comes from P4.03 (`scheduler.capacity_tiers`, `max_bytes` = a real worker's `0.75 × free`) and must be registered first with `register_tiers(tiers)`; `tier=None` uses an automatic bucket `b<k>` with `max_bytes = 2**k`, `k = max(0, ceil(log2(est_vram_bytes)))` (`b0` when `est_vram_bytes <= 1`). `claim(worker_id, lease_s, max_bytes)` reads only registered tiers with `max_bytes_tier <= max_bytes` (all tiers when None), largest first. An entry is never re-added to skip it, so claim cannot spin; a job no worker can take is reported `unschedulable` by the planner and never put. Other keys: hash `<p>:state`, `<p>:attempts`, `<p>:payload`, counter `<p>:lost` (`<p>` = `<stream_prefix>:<run_id>`). Lease reclaim uses `XAUTOCLAIM` with `min_idle_time = lease_s*1000`; replies of length 2 or 3 are accepted (G31). `renew` = `XPENDING <stream> <group> <entry id> <entry id> 1` must show `lease.worker_id` as the owner (else False), then `XCLAIM <stream> <group> <owner> 0 <entry id> JUSTID` (resets idle time without counting a delivery). The ownership check is required: `XCLAIM` with min-idle 0 would otherwise take the entry back from `__reclaimer__` (measured on fakeredis 2.x, 2026-09-30). `reclaim_expired` `XACK`s + `XDEL`s each reclaimed entry immediately after `XAUTOCLAIM`.
`configs/hosts.json` (human copy of `configs/hosts.example.json`):
```json
{"schema": 1, "broker": {"host": "<ip>", "port": 6379, "password_env": "REDIS_PASSWORD"},
 "hosts": [{"name": "laptop", "address": "<ip>", "ssh_user": "<user>", "repo_path": "<abs path>",
            "python": ".venv/bin/python", "cache_dir": "<abs path>", "results_dir": "<abs path>",
            "source_root": "<abs path>", "max_workers": 1,
            "gpus": [{"index": 0, "name": "...", "profile": "configs/device_profiles/<slug>.json"}]}]}
```
Test: `test_C27_fakeredis_protocol_conformance` (runs the C24 behaviour suite against `RedisJobQueue` on fakeredis), `test_C27_hosts_example_schema`.
