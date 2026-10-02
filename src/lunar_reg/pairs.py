"""Window-pair preparation: a source window and a reference crop at one working GSD.

CONTRACTS C11, ``Phase_1/LLD/pairs.md``. This is the library form of
``scripts/run_vikram.prepare_pair``: it cuts a window out of a Chandrayaan-2
product (OHRC, TMC-2 or IIRS), finds where that window's corners land in a
map-projected reference (LRO NAC) through the label corners or the product's
geometry grid plus the reference's :class:`~lunar_reg.ingest.lro.GeoReference`,
reads both windows (windowed reads only, decimated at read time when shrinking
by 4x or more), resamples them to ``gsd_m`` and returns a label-based ``prior``
transform between the two working images.

Everything the crop was produced with is recorded numerically on the returned
:class:`WindowPair` (``source_window``, ``reference_window``, the two
``*_to_native`` matrices, ``shift_m``) and :meth:`WindowPair.geometry_extra`
gives the C04 crop-geometry ``extra`` keys, so a registered product can later be
rebuilt from exactly these numbers.

A pair that cannot be prepared is never an exception: it is a classified
:class:`PrepOutcome` (``PrepStatus``). Exceptions are raised only for programmer
error (a non-positive ``gsd_m``, an unknown ``band_reduction``, a ``centre_line``
outside the product). :class:`PrepDiagnostics` counts outcomes over a batch; the
caller prints its ``report()`` on every run.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from enum import Enum
from math import ceil, floor
from pathlib import Path

import cv2
import numpy as np

from lunar_reg.ingest.lro import GeoReference
from lunar_reg.ingest.overlap import PriorSource
from lunar_reg.provenance import ValueSource

logger = logging.getLogger(__name__)

__all__ = [
    "BAND_REDUCTIONS",
    "DECIMATE_AT_FACTOR",
    "MIN_REFERENCE_VALID_FRACTION",
    "PrepDiagnostics",
    "PrepOutcome",
    "PrepStatus",
    "PriorSource",
    "WindowPair",
    "prepare_window_pair",
]

#: Multi-band reduction methods accepted by :func:`prepare_window_pair` (C11).
BAND_REDUCTIONS = ("first", "mean", "pca")

#: Shrink factor at and above which a window is read decimated (``out_shape`` +
#: ``Resampling.average``) instead of at full resolution (LLD pairs §1 step 6).
DECIMATE_AT_FACTOR = 4.0
DECIMATE_AT_FACTOR_SOURCE = ValueSource.INFERRED

#: Below this fraction of valid working-reference pixels the pair is
#: ``EMPTY_REFERENCE`` (LLD pairs §1 step 9).
MIN_REFERENCE_VALID_FRACTION = 0.05
MIN_REFERENCE_VALID_FRACTION_SOURCE = ValueSource.INFERRED


class PrepStatus(str, Enum):
    """Why a window pair could or could not be prepared (C11)."""

    OK = "ok"
    #: The source label cannot be parsed, lacks lines/samples, or names a sensor
    #: with no nominal GSD.
    LABEL_UNREADABLE = "label_unreadable"
    #: Neither label corners nor a usable geometry grid give the window's ground
    #: position -- a data gap, not a geometry failure.
    NO_FOOTPRINT = "no_footprint"
    #: The window's ground position maps entirely outside the reference raster.
    OUTSIDE_REFERENCE = "outside_reference"
    #: The reference crop lies on the raster but is (almost) all nodata.
    EMPTY_REFERENCE = "empty_reference"
    #: A raster (source, reference or geometry grid) could not be read.
    READ_FAILED = "read_failed"

    @property
    def is_failure(self) -> bool:
        return self is not PrepStatus.OK


@dataclass
class WindowPair:
    """A prepared source/reference pair at ``gsd_m`` (C11)."""

    source: np.ndarray  # 2-D uint8 at gsd_m, 0 = nodata
    reference: np.ndarray
    source_valid: np.ndarray  # bool
    reference_valid: np.ndarray
    prior: np.ndarray  # 3x3 float64: working-source px -> working-reference px
    prior_source: PriorSource
    gsd_m: float
    source_window: tuple[int, int, int, int]  # (row_off, col_off, height, width), source native px
    reference_window: tuple[int, int, int, int]  # reference native px
    source_native_gsd_m: float
    reference_native_gsd_m: float
    source_to_native: np.ndarray  # 3x3: working-source px -> source native px (pixel centres)
    reference_to_native: np.ndarray  # 3x3: working-reference px -> reference native px
    shift_m: tuple[float, float]  # (east, south) applied to the reference window
    source_id: str
    reference_id: str
    provenance: dict[str, str]  # quantity -> ValueSource value

    def geometry_extra(self) -> dict:
        """The C04 crop-geometry ``extra`` keys plus ``prior_source``."""
        r0, c0, _, _ = self.reference_window
        l0, s0, lines, samples = self.source_window
        return {
            "ref_crop_c0": int(c0),
            "ref_crop_r0": int(r0),
            "ref_factor": float(self.gsd_m / self.reference_native_gsd_m),
            "shift_e_m": float(self.shift_m[0]),
            "shift_s_m": float(self.shift_m[1]),
            "src_win_l0": int(l0),
            "src_win_s0": int(s0),
            "src_win_lines": int(lines),
            "src_win_samples": int(samples),
            "gsd_m": float(self.gsd_m),
            "crop_geometry_source": "recorded",
            "prior_source": self.prior_source.value,
        }


@dataclass
class PrepOutcome:
    status: PrepStatus
    pair: WindowPair | None = None
    detail: str = ""


@dataclass
class PrepDiagnostics:
    """Per-status counts and the first sample of each, over a batch of preparations."""

    counts: dict[str, int] = field(default_factory=dict)
    samples: dict[str, str] = field(default_factory=dict)

    def record(self, outcome: PrepOutcome, item_id: str) -> None:
        status = outcome.status
        self.counts[status.value] = self.counts.get(status.value, 0) + 1
        self.samples.setdefault(status.value, f"{item_id}: {outcome.detail}"[:200])

    @property
    def n_failed(self) -> int:
        return sum(n for k, n in self.counts.items() if PrepStatus(k).is_failure)

    def report(self) -> str:
        total = sum(self.counts.values())
        lines = [
            f"window-pair preparation: {total} attempted, {self.counts.get('ok', 0)} ok, "
            f"{self.n_failed} failed (no_footprint = the label/grid has no ground position, "
            f"a data gap; outside_reference = it has one but the reference does not cover it)"
        ]
        for key in sorted(self.counts):
            lines.append(f"  {key}: {self.counts[key]}  e.g. {self.samples.get(key, '')}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _to_native(x0: int, y0: int, native_wh: tuple[int, int], working_wh: tuple[int, int]):
    """Working px -> native px, pixel-centre convention (CONTRACTS C11)."""
    fx = native_wh[0] / working_wh[0]
    fy = native_wh[1] / working_wh[1]
    return np.array(
        [[fx, 0.0, x0 + (fx - 1) / 2], [0.0, fy, y0 + (fy - 1) / 2], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )


def _working_size(width: int, height: int, factor: float) -> tuple[int, int]:
    return max(1, round(width / factor)), max(1, round(height / factor))


def _label_corner_lonlat(product, s, ln):
    """Bilinear interpolation of the four label corners (run_vikram.interp_latlon).

    Returns ``(lon, lat)`` arrays, or ``None`` when any corner value is missing.
    corner1..4 are UL, UR, LL, LR (confirmed on a real OHRC label, 2026-09-28).
    """
    vals = [(product[f"corner{i}_lat"], product[f"corner{i}_lon"]) for i in range(1, 5)]
    if any(v is None for pair in vals for v in pair):
        return None
    ul, ur, ll, lr = (np.asarray(v, dtype=np.float64) for v in vals)
    u = np.asarray(s, dtype=np.float64)[:, None] / product.samples
    v = np.asarray(ln, dtype=np.float64)[:, None] / product.lines
    top = (1 - u) * ul + u * ur
    bot = (1 - u) * ll + u * lr
    p = (1 - v) * top + v * bot  # (n, 2) as (lat, lon)
    return p[:, 1], p[:, 0]


#: The acquisition timestamp token of a CH-2 product (``YYYYMMDDTHHMMSSffff``).
#: Real labels write it with a lower-case ``t`` in the logical_identifier
#: (``..._20240425t1406019344_d_img_d18``) and an upper-case ``T`` in the file
#: names, so it is matched case-insensitively here and normalised to ``T``.
_TIMESTAMP_TOKEN = re.compile(r"\d{8}T\d{10}", re.IGNORECASE)


def _grid_key(label_path: Path, product_id: str | None) -> str | None:
    """This product's timestamp token (``YYYYMMDDTHHMMSSffff``), or ``None``.

    Taken from ``product_id`` and otherwise from the label file stem. ``None``
    means no token: grid discovery is then skipped, never run unfiltered (an
    unfiltered search would return another product's grid).
    """
    for text in (product_id, label_path.stem):
        found = _TIMESTAMP_TOKEN.search(text) if text else None
        if found is not None:
            token = found.group(0)
            return f"{token[:8]}T{token[9:]}"
    return None


def _find_grid(label_path: Path, product_id: str | None) -> Path | None:
    """The product's geometry-grid CSV, if one sits next to its label.

    Looks under ``<product dir>/geometry`` (the CH-2 bundle layout: the parent of
    the ``data`` directory holding the label) and otherwise under the label
    directory's parent, as LLD pairs §1 step 3 names it. Only grids whose name
    carries this product's timestamp token (:func:`_grid_key`) are considered;
    with no token there is no discovery.
    """
    from lunar_reg.ingest.geometry_grid import find_geometry_files

    key = _grid_key(label_path, product_id)
    if key is None:
        return None
    roots = []
    for parent in label_path.parents:
        if parent.name == "data":
            roots.append(parent.parent / "geometry")
            break
    roots.append(label_path.parent.parent)
    for root in roots:
        if not root.is_dir():
            continue
        found = find_geometry_files(root, key)
        if found:
            if len(found) > 1:
                logger.warning(
                    "%s: %d geometry grids match; using %s",
                    label_path.name,
                    len(found),
                    found[0][0].name,
                )
            return Path(found[0][0])
    return None


def _decimated_read(ds, window, factor: float, indexes, boundless: bool):
    """Read ``window``; decimated with ``Resampling.average`` when ``factor >= 4``.

    Returns ``(data, nearest)``: ``nearest`` is ``None`` for a full-resolution
    read; for a decimated read it is a second, nearest-neighbour decimated read
    (the ``INTER_NEAREST`` equivalent at read time) that the valid mask comes
    from, so averaging with nodata cannot mark a cell valid.
    """
    from rasterio.enums import Resampling

    kwargs = {"window": window}
    if boundless:
        kwargs.update(boundless=True, fill_value=0)
    if factor < DECIMATE_AT_FACTOR:
        return ds.read(indexes, **kwargs), None
    w, h = _working_size(int(window.width), int(window.height), factor)
    shape = (h, w) if isinstance(indexes, int) else (len(indexes), h, w)
    data = ds.read(indexes, out_shape=shape, resampling=Resampling.average, **kwargs)
    nearest = ds.read(indexes, out_shape=shape, resampling=Resampling.nearest, **kwargs)
    return data, nearest


def _valid(arr: np.ndarray) -> np.ndarray:
    """Native validity: finite and > 0 (P1.08: 0 = nodata); a cube: all bands finite, any > 0."""
    a = np.asarray(arr)
    finite = np.isfinite(a)
    with np.errstate(invalid="ignore"):
        positive = finite & (a > 0)
    if a.ndim == 3:
        return finite.all(axis=0) & positive.any(axis=0)
    return positive


def _reduce(cube: np.ndarray, valid: np.ndarray, method: str) -> np.ndarray:
    """A ``(bands, h, w)`` cube to one float32 plane per ``band_reduction``."""
    if method == "first":
        return cube[0].astype(np.float32)
    data = cube.astype(np.float32)
    data[:, ~valid] = np.nan
    if method == "mean":
        # nan-mean over bands; all-NaN (invalid) pixels become 0 below
        counts = np.isfinite(data).sum(axis=0)
        sums = np.nansum(data, axis=0)
        plane = np.where(counts > 0, sums / np.maximum(counts, 1), np.nan)
    elif not valid.any():
        # reduce_bands raises on a cube with no valid pixel; an all-nodata window
        # is a bad item, not a programmer error, so it comes back all-invalid
        # exactly as "first" and "mean" do (Q-P1.13-1)
        plane = np.zeros(data.shape[1:], dtype=np.float32)
    else:
        from lunar_reg.preprocess.hyperspectral import reduce_bands

        plane, _ = reduce_bands(data, method="pca", n_components=1)
    plane = np.asarray(plane, dtype=np.float32)
    plane[~np.isfinite(plane)] = 0.0
    return plane


def _resample(plane, valid, size_wh):
    """INTER_AREA image + INTER_NEAREST valid mask at ``size_wh`` (LLD §1 steps 7-8)."""
    img = np.asarray(plane, dtype=np.float32)
    if img.shape[::-1] != tuple(size_wh):
        img = cv2.resize(img, size_wh, interpolation=cv2.INTER_AREA)
        valid = cv2.resize(valid.astype(np.uint8), size_wh, interpolation=cv2.INTER_NEAREST).astype(
            bool
        )
    return img, valid


def _done(outcome: PrepOutcome, item: str) -> PrepOutcome:
    """Log the one summary line for this call and return ``outcome``."""
    if outcome.status.is_failure:
        logger.warning(
            "prepare_window_pair %s: %s (%s)", item, outcome.status.value, outcome.detail
        )
    else:
        p = outcome.pair
        logger.info(
            "prepare_window_pair %s: ok, source %s, reference %s at %.3g m/px, prior from %s",
            item,
            p.source.shape,
            p.reference.shape,
            p.gsd_m,
            p.prior_source.value,
        )
    return outcome


# ---------------------------------------------------------------------------
# main entry point
# ---------------------------------------------------------------------------


def prepare_window_pair(
    source_label,
    reference_path,
    reference_geo: GeoReference,
    *,
    gsd_m: float,
    window_m: float,
    margin_m: float,
    shift_m: tuple[float, float] = (0.0, 0.0),
    centre_line: int | None = None,
    centre_sample: int | None = None,
    geometry_grid_path=None,
    band_reduction: str = "first",
) -> PrepOutcome:
    """Prepare one source window and its reference crop at ``gsd_m`` (C11, LLD pairs §1).

    ``source_label`` is the CH-2 PDS4 label; ``reference_path`` the reference
    raster (NAC label or GeoTIFF; only its pixels are read, the georeference is
    ``reference_geo``). ``shift_m = (east, south)`` moves the reference crop;
    the returned ``prior`` is always the unshifted label/grid prior.
    ``centre_line`` / ``centre_sample`` centre the source window (default: the
    product's middle line / sample); the window is clamped inside the product.
    """
    import rasterio
    from rasterio.errors import RasterioError
    from rasterio.windows import Window

    from lunar_reg.constants import SENSORS
    from lunar_reg.ingest.pds4 import open_product, read_label
    from lunar_reg.preprocess.radiometric import to_uint8

    if not gsd_m > 0 or not window_m > 0 or not margin_m >= 0:
        raise ValueError(
            f"need gsd_m > 0, window_m > 0, margin_m >= 0; got {gsd_m}, {window_m}, {margin_m}"
        )
    if band_reduction not in BAND_REDUCTIONS:
        raise ValueError(f"band_reduction must be one of {BAND_REDUCTIONS}, got {band_reduction!r}")

    source_label = Path(source_label)
    reference_path = Path(reference_path)
    item = f"{source_label.name} -> {reference_path.name}"
    shift_e, shift_s = float(shift_m[0]), float(shift_m[1])

    # 1. label
    try:
        product = read_label(source_label)
    except (OSError, ET.ParseError, ValueError) as exc:
        return _done(
            PrepOutcome(PrepStatus.LABEL_UNREADABLE, detail=f"{type(exc).__name__}: {exc}"[:200]),
            item,
        )
    lines, samples = product.lines, product.samples
    if not lines or not samples:
        return _done(
            PrepOutcome(PrepStatus.LABEL_UNREADABLE, detail="label has no Line/Sample axis sizes"),
            item,
        )

    # 2. source window, native px
    spec = SENSORS.get(product.sensor or "")
    if spec is None:
        return _done(
            PrepOutcome(
                PrepStatus.LABEL_UNREADABLE, detail=f"no nominal GSD for sensor {product.sensor}"
            ),
            item,
        )
    src_gsd = float(spec.gsd_m)
    if centre_line is None:
        centre_line = lines // 2
    if not 0 <= centre_line < lines:
        raise ValueError(f"centre_line {centre_line} outside the product's 0..{lines - 1}")
    if centre_sample is None:
        centre_sample = samples // 2
    if not 0 <= centre_sample < samples:
        raise ValueError(f"centre_sample {centre_sample} outside the product's 0..{samples - 1}")
    win = min(max(1, round(window_m / src_gsd)), lines)
    win_s = min(win, samples)
    l0 = min(max(int(centre_line) - win // 2, 0), lines - win)
    s0 = min(max(int(centre_sample) - win_s // 2, 0), samples - win_s)

    # 3. ground position of the window corners (corner convention, run_vikram order)
    cs = np.array([s0, s0 + win_s, s0, s0 + win_s], dtype=np.float64)
    cl = np.array([l0, l0, l0 + win, l0 + win], dtype=np.float64)
    grid_path = Path(geometry_grid_path) if geometry_grid_path is not None else None
    if grid_path is None:
        grid_path = _find_grid(source_label, product.product_id)
    if grid_path is not None:
        import csv

        from lunar_reg.ingest.geometry_grid import pixel_to_lonlat, read_geometry_grid

        try:
            grid = read_geometry_grid(grid_path, lines=lines, samples=samples)
        except (OSError, ValueError, csv.Error, ET.ParseError) as exc:
            # No fallback to the label corners (as ingest.overlap): a grid that
            # exists and cannot be read is a fault to look at.
            return _done(
                PrepOutcome(
                    PrepStatus.READ_FAILED,
                    detail=f"geometry grid {grid_path.name}: {type(exc).__name__}: {exc}"[:200],
                ),
                item,
            )
        # grid indices are pixel centres: corner x sits at index x - 0.5, clamped
        # to the grid's index range (a half-pixel shift, irrelevant to a prior)
        lon, lat = pixel_to_lonlat(
            grid, np.clip(cl - 0.5, 0, lines - 1), np.clip(cs - 0.5, 0, samples - 1)
        )
        if not (np.isfinite(lon).all() and np.isfinite(lat).all()):
            return _done(
                PrepOutcome(
                    PrepStatus.NO_FOOTPRINT,
                    detail=f"geometry grid {grid_path.name} does not cover the window corners",
                ),
                item,
            )
        prior_source = PriorSource.GEOMETRY_GRID
    else:
        found = _label_corner_lonlat(product, cs, cl)
        if found is None:
            return _done(
                PrepOutcome(
                    PrepStatus.NO_FOOTPRINT, detail="label has no corner coordinates and no grid"
                ),
                item,
            )
        lon, lat = found
        prior_source = PriorSource.LABEL_CORNERS

    # 4. reference pixels of the corners (unshifted), then the shift
    cols, rows = reference_geo.lonlat_to_pixel(lon=lon, lat=lat)
    cols = np.asarray(cols, dtype=np.float64)
    rows = np.asarray(rows, dtype=np.float64)
    if not (np.isfinite(cols).all() and np.isfinite(rows).all()):
        return _done(
            PrepOutcome(
                PrepStatus.OUTSIDE_REFERENCE,
                detail="a window corner does not project to the reference",
            ),
            item,
        )
    psx = float(reference_geo.pixel_size_x_m)
    psy = float(reference_geo.pixel_size_y_m)
    dcol, drow = shift_e / psx, shift_s / psy

    # 5. reference window, native px
    c0 = floor(cols.min() + dcol - margin_m / psx)
    c1 = ceil(cols.max() + dcol + margin_m / psx)
    r0 = floor(rows.min() + drow - margin_m / psy)
    r1 = ceil(rows.max() + drow + margin_m / psy)
    if c1 <= 0 or r1 <= 0 or c0 >= reference_geo.width or r0 >= reference_geo.height:
        return _done(
            PrepOutcome(
                PrepStatus.OUTSIDE_REFERENCE,
                detail=f"crop cols {c0}..{c1} rows {r0}..{r1} vs reference "
                f"{reference_geo.width}x{reference_geo.height}",
            ),
            item,
        )
    ref_w, ref_h = c1 - c0, r1 - r0

    # 6. windowed reads (decimated when shrinking >= 4x)
    src_factor = gsd_m / src_gsd
    ref_factor = gsd_m / psx
    provenance = {
        "src_gsd": ValueSource.DOCUMENTED.value,
        "reference_georef": reference_geo.source.value,
        "corners": ValueSource.DOCUMENTED.value,
        "shift_m": (
            ValueSource.INFERRED if (shift_e, shift_s) != (0.0, 0.0) else ValueSource.COMPUTED
        ).value,
    }
    try:
        with open_product(source_label) as ds:
            multi = ds.count > 1
            indexes = list(range(1, ds.count + 1)) if multi else 1
            src_win = Window(s0, l0, win_s, win)
            raw, nearest = _decimated_read(ds, src_win, src_factor, indexes, False)
        with rasterio.open(reference_path) as ds:
            ref_raw, ref_nearest = _decimated_read(
                ds, Window(c0, r0, ref_w, ref_h), ref_factor, 1, True
            )
    except (OSError, RasterioError, ValueError) as exc:
        return _done(
            PrepOutcome(PrepStatus.READ_FAILED, detail=f"{type(exc).__name__}: {exc}"[:200]), item
        )
    src_valid = _valid(raw if nearest is None else nearest)
    if multi:
        src_plane = _reduce(raw, src_valid, band_reduction)
        provenance["band_reduction"] = band_reduction
    else:
        src_plane = raw
    del raw, nearest
    ref_valid = _valid(ref_raw if ref_nearest is None else ref_nearest)

    # 7-8. resample to gsd_m, stretch to uint8 with 0 = nodata
    src_wh = _working_size(win_s, win, src_factor)
    ref_wh = _working_size(ref_w, ref_h, ref_factor)
    src_img, src_valid = _resample(src_plane, src_valid, src_wh)
    ref_img, ref_valid = _resample(ref_raw, ref_valid, ref_wh)
    del src_plane, ref_raw, ref_nearest
    source = to_uint8(src_img, valid=src_valid)
    reference = to_uint8(ref_img, valid=ref_valid)

    # 9. empty reference
    frac = float(ref_valid.mean())
    if frac < MIN_REFERENCE_VALID_FRACTION:
        return _done(
            PrepOutcome(
                PrepStatus.EMPTY_REFERENCE,
                detail=f"reference valid fraction {frac:.3f} < {MIN_REFERENCE_VALID_FRACTION}",
            ),
            item,
        )

    # 10. prior: working source corners -> unshifted corner reference px, in working-reference px
    w, h = src_wh
    src_quad = np.float32([[0, 0], [w, 0], [0, h], [w, h]])
    dst_quad = np.float32(np.c_[(cols - c0) / ref_factor, (rows - r0) / ref_factor])
    prior = cv2.getPerspectiveTransform(src_quad, dst_quad).astype(np.float64)

    # 11. working -> native, pixel-centre convention, actual sizes
    pair = WindowPair(
        source=source,
        reference=reference,
        source_valid=src_valid,
        reference_valid=ref_valid,
        prior=prior,
        prior_source=prior_source,
        gsd_m=float(gsd_m),
        source_window=(int(l0), int(s0), int(win), int(win_s)),
        reference_window=(int(r0), int(c0), int(ref_h), int(ref_w)),
        source_native_gsd_m=src_gsd,
        reference_native_gsd_m=psx,
        source_to_native=_to_native(s0, l0, (win_s, win), src_wh),
        reference_to_native=_to_native(c0, r0, (ref_w, ref_h), ref_wh),
        shift_m=(shift_e, shift_s),
        source_id=(product.product_id or source_label.stem).rsplit(":", 1)[-1],
        reference_id=reference_path.stem,
        provenance=provenance,
    )
    return _done(PrepOutcome(PrepStatus.OK, pair=pair), item)
