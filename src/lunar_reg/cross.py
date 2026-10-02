"""Cross-instrument overlaps at any site (CONTRACTS C28, DECISIONS G41).

Every Chandrayaan-2 product that has a per-pixel geometry grid is tested
against every map reference listed in ``configs/references.json``, at whatever
site they meet. A new strip or a new reference needs a file on disk or a config
row, never a code change.

Overlap is tested in the **reference's own projection**: each grid node is
projected into the reference's pixel space and looked up in a decimated
validity mask of the reference. Footprints are never compared in lon/lat
space: a strip that passes near a pole has corner longitudes spanning most of
0-360 degrees, so a lon/lat box "contains" places hundreds of kilometres away.
That is the most likely cause of the P1.DL "90-100 % box cover" figures that
the per-pixel grids refute (Q-P1.18-1).

Every (product, reference) pair gets an :class:`OverlapStatus`; data gaps
(``NO_GRID``, ``REFERENCE_MISSING``) and expected non-results (``DISJOINT``)
are counted alongside the failures, and :meth:`OverlapReport.report` is printed
by the caller on every run.
"""

from __future__ import annotations

import json
import logging
import math
from collections import Counter
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path

import numpy as np

from lunar_reg.provenance import ValueSource

logger = logging.getLogger(__name__)

#: Longest edge of the decimated reference validity mask, in pixels (G40).
VALIDITY_MAX_EDGE_PX = 2048
VALIDITY_MAX_EDGE_PX_SOURCE = ValueSource.INFERRED

#: Grid nodes / reference pixels sampled for the DISJOINT nearest distance.
DISTANCE_SAMPLE_MAX = 20_000

#: Lunar radius used for arc lengths, km (IAU mean radius, as ``constants.MOON_RADIUS_M``).
_RADIUS_KM = 1737.4

REFERENCE_GEOREFS = ("label", "raster")
_REFERENCE_KEYS = ("name", "path", "georef", "sensor", "independent")


class OverlapStatus(str, Enum):
    OVERLAP = "overlap"
    DISJOINT = "disjoint"  # expected non-result
    NO_GRID = "no_grid"  # source has no geometry grid: data gap
    GRID_UNREADABLE = "grid_unreadable"  # failure
    REFERENCE_MISSING = "reference_missing"  # data gap
    REFERENCE_UNREADABLE = "reference_unreadable"  # failure

    @property
    def is_failure(self) -> bool:
        return self in (OverlapStatus.GRID_UNREADABLE, OverlapStatus.REFERENCE_UNREADABLE)


_STATUS_WORDS = {
    OverlapStatus.OVERLAP: "grid nodes fall on valid reference pixels",
    OverlapStatus.DISJOINT: "no overlap (expected non-result)",
    OverlapStatus.NO_GRID: "source product has no geometry grid (data gap, not a bug)",
    OverlapStatus.GRID_UNREADABLE: "geometry grid exists but could not be read (failure)",
    OverlapStatus.REFERENCE_MISSING: "reference file not on disk (data gap, not a bug)",
    OverlapStatus.REFERENCE_UNREADABLE: (
        "reference exists but could not be georeferenced or read (failure)"
    ),
}


@dataclass(frozen=True)
class ReferenceSpec:
    name: str
    path: str
    georef: str  # "label" | "raster"
    sensor: str
    independent: bool


def load_references(path="configs/references.json") -> list[ReferenceSpec]:
    """Read ``configs/references.json`` (schema 1). ``ValueError`` lists every schema problem."""
    path = Path(path)
    try:
        doc = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise ValueError(f"{path}: cannot read references config: {exc}") from exc
    problems: list[str] = []
    if not isinstance(doc, dict):
        raise ValueError(f"{path}: references config is not a JSON object")
    if doc.get("schema") != 1:
        problems.append(f"schema is {doc.get('schema')!r}, expected 1")
    rows = doc.get("references")
    if not isinstance(rows, list):
        problems.append("'references' is not a list")
        rows = []
    specs: list[ReferenceSpec] = []
    seen: set[str] = set()
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            problems.append(f"references[{i}] is not an object")
            continue
        keys = set(row)
        if keys != set(_REFERENCE_KEYS):
            missing = sorted(set(_REFERENCE_KEYS) - keys)
            extra = sorted(keys - set(_REFERENCE_KEYS))
            problems.append(f"references[{i}] keys: missing {missing}, unexpected {extra}")
            continue
        for key in ("name", "path", "sensor", "georef"):
            if not isinstance(row[key], str) or not row[key]:
                problems.append(f"references[{i}].{key} must be a non-empty string")
        if not isinstance(row["independent"], bool):
            problems.append(f"references[{i}].independent must be true or false")
        if row.get("georef") not in REFERENCE_GEOREFS:
            problems.append(
                f"references[{i}].georef {row.get('georef')!r} not in {list(REFERENCE_GEOREFS)}"
            )
        if row.get("name") in seen:
            problems.append(f"references[{i}].name {row.get('name')!r} is duplicated")
        seen.add(row.get("name"))
        specs.append(ReferenceSpec(**{k: row[k] for k in _REFERENCE_KEYS}))
    if problems:
        raise ValueError(f"{path}: invalid references config: " + "; ".join(problems))
    return specs


@dataclass
class OverlapCandidate:
    source_product_id: str
    instrument: str
    level: str
    reference: str
    status: OverlapStatus
    n_nodes: int
    n_inside: int
    centre_line: int | None
    centre_sample: int | None
    centre_lat: float | None
    centre_lon: float | None
    min_distance_km: float | None  # DISJOINT only: nearest grid node to a valid reference pixel
    overlap_km2: float | None
    overlap_source: str  # ValueSource value
    reference_independent: bool
    reference_georef_source: str | None  # GeoReference.source value
    detail: str = ""

    def as_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        for key, value in d.items():
            if isinstance(value, np.generic):
                d[key] = value.item()
        return d


@dataclass
class ReferenceValidity:
    """Decimated validity mask of one reference (G40): ``mask[r, c]`` covers
    full-resolution rows ``r * factor_y ...`` and columns ``c * factor_x ...``."""

    factor: int
    mask: np.ndarray
    fill_value: float | None
    fill_source: str  # "declared" | "probe_inferred" | "assumed_zero"


def _repo_root() -> Path:
    import lunar_reg

    return Path(lunar_reg.__file__).resolve().parents[2]


def resolve_reference_path(spec: ReferenceSpec) -> Path:
    """``spec.path`` as written when absolute or present from the cwd, else under the repo."""
    path = Path(spec.path)
    if path.is_absolute() or path.exists():
        return path
    return _repo_root() / path


def reference_georeference(spec: ReferenceSpec):
    """The C10 :class:`~lunar_reg.ingest.lro.GeoReference` named by ``spec.georef``."""
    from lunar_reg.ingest.lro import georeference_from_label, georeference_from_raster

    path = resolve_reference_path(spec)
    if spec.georef == "label":
        return georeference_from_label(path)
    if spec.georef == "raster":
        return georeference_from_raster(path)
    raise ValueError(f"reference {spec.name}: unknown georef {spec.georef!r}")


def _probe_fill(path: Path) -> float | None:
    probe = _repo_root() / "docs" / "probes" / f"{path.stem}_raster.json"
    if not probe.exists():
        return None
    try:
        value = json.loads(probe.read_text()).get("fill_candidate")
    except (OSError, ValueError):
        return None
    return None if value is None else float(value)


def reference_validity(spec: ReferenceSpec, geo) -> ReferenceValidity:
    """One decimated nearest-neighbour read of ``spec``'s raster (G40, never a full read).

    Fill value: the declared nodata, else the P1.15 probe's ``fill_candidate``
    (``docs/probes/<stem>_raster.json``), else 0 (``assumed_zero``).
    """
    import rasterio
    from rasterio.enums import Resampling

    path = resolve_reference_path(spec)
    with rasterio.open(path) as ds:
        w, h = ds.width, ds.height
        factor = max(1, math.ceil(max(w, h) / VALIDITY_MAX_EDGE_PX))
        out_shape = (math.ceil(h / factor), math.ceil(w / factor))
        data = ds.read(1, out_shape=out_shape, resampling=Resampling.nearest)
        nodata = ds.nodata
    if nodata is not None:
        fill, fill_source = float(nodata), "declared"
    else:
        probed = _probe_fill(path)
        if probed is not None:
            fill, fill_source = probed, "probe_inferred"
        else:
            fill, fill_source = 0.0, "assumed_zero"
    arr = np.asarray(data)
    mask = arr != fill
    if np.issubdtype(arr.dtype, np.floating):
        mask &= np.isfinite(arr)
    if (w, h) != (geo.width, geo.height):
        logger.warning(
            "reference %s: raster is %dx%d but its georeference says %dx%d",
            spec.name,
            w,
            h,
            geo.width,
            geo.height,
        )
    return ReferenceValidity(factor=factor, mask=mask, fill_value=fill, fill_source=fill_source)


def _unit_vectors(lon_deg: np.ndarray, lat_deg: np.ndarray) -> np.ndarray:
    lon, lat = np.radians(lon_deg), np.radians(lat_deg)
    return np.column_stack([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)])


def _sample(n: int, k: int, seed: int = 0) -> np.ndarray:
    if n <= k:
        return np.arange(n)
    return np.sort(np.random.default_rng(seed).choice(n, size=k, replace=False))


def _median_step(values: np.ndarray) -> float:
    steps = np.diff(np.asarray(values, dtype=np.float64))
    return float(np.median(steps)) if steps.size else 1.0


def _wrap180(lon: float) -> float:
    return float((lon + 180.0) % 360.0 - 180.0)


def overlap_for_grid(
    product_id: str,
    instrument: str,
    level: str,
    grid,
    spec: ReferenceSpec,
    geo,
    valid: ReferenceValidity,
    *,
    min_inside: int = 4,
    nominal_gsd_m: float,
) -> OverlapCandidate:
    """Test one product's geometry grid against one reference, in the reference's projection."""
    from scipy.ndimage import distance_transform_edt
    from scipy.spatial import cKDTree

    lat = np.asarray(grid.lat, dtype=np.float64)
    lon = np.asarray(grid.lon, dtype=np.float64)
    n_nodes = int(lat.size)
    base = dict(
        source_product_id=product_id,
        instrument=instrument,
        level=level,
        reference=spec.name,
        n_nodes=n_nodes,
        overlap_source=ValueSource.COMPUTED.value,
        reference_independent=bool(spec.independent),
        reference_georef_source=geo.source.value,
    )

    finite = np.isfinite(lat) & np.isfinite(lon)
    inside = np.zeros(lat.shape, dtype=bool)
    if finite.any():
        col, row = geo.lonlat_to_pixel(lon=lon[finite], lat=lat[finite])
        col, row = np.asarray(col, np.float64), np.asarray(row, np.float64)
        ok = (
            np.isfinite(col)
            & np.isfinite(row)
            & (col >= 0)
            & (col < geo.width)
            & (row >= 0)
            & (row < geo.height)
        )
        mh, mw = valid.mask.shape
        fy, fx = geo.height / mh, geo.width / mw
        r = np.clip((row[ok] // fy).astype(np.int64), 0, mh - 1)
        c = np.clip((col[ok] // fx).astype(np.int64), 0, mw - 1)
        hit = np.zeros(col.shape, dtype=bool)
        hit[np.flatnonzero(ok)] = valid.mask[r, c]
        inside[finite] = hit
    n_inside = int(inside.sum())

    if n_inside >= min_inside:
        padded = np.pad(inside, 1, constant_values=False)
        depth = distance_transform_edt(padded)[1:-1, 1:-1]
        # argmax over the row-major flattening: ties go to the smallest (scan, pixel) index
        i, j = np.unravel_index(int(np.argmax(np.where(inside, depth, -1.0))), inside.shape)
        area = (
            n_inside
            * _median_step(grid.scan_lines)
            * _median_step(grid.pixels)
            * nominal_gsd_m**2
            / 1e6
        )
        return OverlapCandidate(
            **base,
            status=OverlapStatus.OVERLAP,
            n_inside=n_inside,
            centre_line=int(grid.scan_lines[i]),
            centre_sample=int(grid.pixels[j]),
            centre_lat=float(lat[i, j]),
            centre_lon=_wrap180(float(lon[i, j])),
            min_distance_km=None,
            overlap_km2=float(area),
            detail=f"{n_inside} of {n_nodes} grid nodes on valid reference pixels",
        )

    # DISJOINT: nearest grid node to a valid reference pixel, on the sphere
    min_km: float | None = None
    detail = f"{n_inside} of {n_nodes} grid nodes inside (< {min_inside})"
    rr, cc = np.nonzero(valid.mask)
    if rr.size and finite.any():
        mh, mw = valid.mask.shape
        pick = _sample(rr.size, DISTANCE_SAMPLE_MAX)
        ref_col = (cc[pick] + 0.5) * (geo.width / mw)
        ref_row = (rr[pick] + 0.5) * (geo.height / mh)
        ref_lon, ref_lat = geo.pixel_to_lonlat(col=ref_col, row=ref_row)
        ref_ok = np.isfinite(ref_lon) & np.isfinite(ref_lat)
        src_lat, src_lon = lat[finite], lon[finite]
        spick = _sample(src_lat.size, DISTANCE_SAMPLE_MAX)
        if ref_ok.any():
            tree = cKDTree(_unit_vectors(np.asarray(ref_lon)[ref_ok], np.asarray(ref_lat)[ref_ok]))
            chord, _ = tree.query(_unit_vectors(src_lon[spick], src_lat[spick]))
            arc = 2.0 * _RADIUS_KM * np.arcsin(np.clip(np.min(chord) / 2.0, 0.0, 1.0))
            min_km = float(arc)
            detail += f"; nearest valid reference pixel {min_km:.1f} km"
    elif not rr.size:
        detail += "; reference has no valid pixels"
    return OverlapCandidate(
        **base,
        status=OverlapStatus.DISJOINT,
        n_inside=n_inside,
        centre_line=None,
        centre_sample=None,
        centre_lat=None,
        centre_lon=None,
        min_distance_km=min_km,
        overlap_km2=None,
        detail=detail,
    )


@dataclass
class OverlapReport:
    candidates: list[OverlapCandidate]
    counts: dict[str, int] = field(default_factory=dict)
    samples: dict[str, str] = field(default_factory=dict)

    def report(self) -> str:
        lines = [f"cross overlaps: {len(self.candidates)} (product, reference) pair(s) tested"]
        for status in OverlapStatus:
            n = self.counts.get(status.value, 0)
            if not n:
                continue
            sample = self.samples.get(status.value, "")
            lines.append(f"  {status.value}: {n}  e.g. {sample}  -- {_STATUS_WORDS[status]}")
        if not self.candidates:
            lines.append("  (no source product with a requested instrument/level on disk)")
        return "\n".join(lines)

    def to_json(self) -> str:
        rows = sorted(
            (c.as_dict() for c in self.candidates),
            key=lambda d: (d["reference"], d["source_product_id"]),
        )
        return json.dumps({"schema": 1, "candidates": rows}, indent=2, sort_keys=True)


def _blank(entry, spec: ReferenceSpec, status: OverlapStatus, detail: str, georef_source=None):
    return OverlapCandidate(
        source_product_id=entry.product_id,
        instrument=entry.instrument,
        level=entry.level,
        reference=spec.name,
        status=status,
        n_nodes=0,
        n_inside=0,
        centre_line=None,
        centre_sample=None,
        centre_lat=None,
        centre_lon=None,
        min_distance_km=None,
        overlap_km2=None,
        overlap_source=ValueSource.COMPUTED.value,
        reference_independent=bool(spec.independent),
        reference_georef_source=georef_source,
        detail=detail[:300],
    )


def find_overlaps(
    raw_root,
    references: list[ReferenceSpec],
    *,
    instruments=("OHRC", "TMC2", "IIRS"),
    levels=("raw", "calibrated"),
    min_inside: int = 4,
) -> OverlapReport:
    """Every (catalog product with the requested instrument/level, reference) pair, classified."""
    import csv
    import xml.etree.ElementTree as ET

    from rasterio.errors import RasterioError

    from lunar_reg.constants import SENSORS
    from lunar_reg.ingest.catalog import build_catalog
    from lunar_reg.ingest.geometry_grid import read_geometry_grid
    from lunar_reg.ingest.lro import LabelGeoreferenceError

    catalog = build_catalog(raw_root)
    entries = [e for inst in instruments for e in catalog.products(inst) if e.level in levels]

    grids: dict[str, object] = {}
    grid_errors: dict[str, str] = {}

    def grid_for(entry):
        key = str(entry.geometry_grid_path)
        if key not in grids and key not in grid_errors:
            try:
                grids[key] = read_geometry_grid(entry.geometry_grid_path)
            except (OSError, ValueError, csv.Error, ET.ParseError) as exc:
                grid_errors[key] = f"{type(exc).__name__}: {exc}"
        return grids.get(key), grid_errors.get(key)

    candidates: list[OverlapCandidate] = []
    for spec in references:
        path = resolve_reference_path(spec)
        if not path.exists():
            candidates += [
                _blank(e, spec, OverlapStatus.REFERENCE_MISSING, f"{spec.path} not on disk")
                for e in entries
            ]
            continue
        try:
            geo = reference_georeference(spec)
            valid = reference_validity(spec, geo)
        except (LabelGeoreferenceError, OSError, RasterioError, ValueError) as exc:
            reason = f"{type(exc).__name__}: {exc}"
            candidates += [
                _blank(e, spec, OverlapStatus.REFERENCE_UNREADABLE, reason) for e in entries
            ]
            continue
        for entry in entries:
            if entry.geometry_grid_path is None:
                candidates.append(
                    _blank(
                        entry,
                        spec,
                        OverlapStatus.NO_GRID,
                        "no geometry grid for this product",
                        geo.source.value,
                    )
                )
                continue
            grid, error = grid_for(entry)
            if grid is None:
                candidates.append(
                    _blank(
                        entry,
                        spec,
                        OverlapStatus.GRID_UNREADABLE,
                        f"{Path(entry.geometry_grid_path).name}: {error}",
                        geo.source.value,
                    )
                )
                continue
            candidates.append(
                overlap_for_grid(
                    entry.product_id,
                    entry.instrument,
                    entry.level,
                    grid,
                    spec,
                    geo,
                    valid,
                    min_inside=min_inside,
                    nominal_gsd_m=float(SENSORS[entry.instrument].gsd_m),
                )
            )

    counts = Counter(c.status.value for c in candidates)
    samples: dict[str, str] = {}
    for c in candidates:
        samples.setdefault(
            c.status.value, f"{c.source_product_id} vs {c.reference}: {c.detail}"[:200]
        )
    report = OverlapReport(candidates=candidates, counts=dict(counts), samples=samples)
    logger.info(
        "cross overlaps: %d pair(s): %s",
        len(candidates),
        ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "none",
    )
    return report


__all__ = [
    "OverlapCandidate",
    "OverlapReport",
    "OverlapStatus",
    "ReferenceSpec",
    "ReferenceValidity",
    "find_overlaps",
    "load_references",
    "overlap_for_grid",
    "reference_georeference",
    "reference_validity",
    "resolve_reference_path",
]
