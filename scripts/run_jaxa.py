"""Rebuild the two JAXA Kaguya (SELENE) Terrain Camera pairs through ``register_pair``.

``Phase_1/LLD/jaxa_cli_ablation.md`` §1 (closes A066). The v1 JAXA/WAC rows in
the results store had no producing script; the only record of how they were made
is ``data/processed/demo_real/README.md``. This script makes every preparation
choice explicit and writes it into each result's ``extra`` (G19):

``JAXA_SELENE_TC-JAXA_SELENE_TC``
    Two TC passes over the same ground. Both share a CRS, so both are cropped to
    the intersection of their bounds in that CRS and resampled (GDAL ``average``)
    to a common GSD ``g = max(native GSDs, extent / 1152)``, so the longest side
    is at most 1152 px; then ``to_uint8(valid = data > 0)``.
``JAXA_SELENE_TC-LRO_WAC``
    A TC scene reprojected onto the LRO WAC 100 m/px grid with
    :func:`lunar_reg.preprocess.georeference.georeference` (reference grid, NaN
    fill), both cropped to the valid bounding box of the reprojected TC, then
    ``to_uint8(valid=...)``.

Nothing is real ISRO data and nothing is synthetic: sensor names in the store
are ``JAXA_SELENE_TC`` and ``LRO_WAC``. A missing input file is reported as
``input_missing`` (never an exception); the script prints the preparation report
and :meth:`~lunar_reg.pipeline.BatchReport.report` on every run and exits 1 when
no registration succeeded. Input paths are relative to the current directory.

Usage::

    .venv/bin/python scripts/run_jaxa.py --root data/processed/results [--overwrite]
"""

# No ``from __future__ import annotations``: this module defines dataclasses and is
# also loaded by file path (tests), outside ``sys.modules``, where string
# annotations make ``dataclasses`` fail.
import argparse
import dataclasses
import glob
import logging
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

SAME_PAIR = "JAXA_SELENE_TC-JAXA_SELENE_TC"
CROSS_PAIR = "JAXA_SELENE_TC-LRO_WAC"
TC_SENSOR = "JAXA_SELENE_TC"
WAC_SENSOR = "LRO_WAC"

SAME_SOURCE_GLOB = "data/raw/reference/jaxa_selene_tc_pair2/TC1S2B0_01_05504N194E0230/*.tif"
SAME_REFERENCE_GLOB = "data/raw/reference/jaxa_selene_tc_pair2/TC1S2B0_01_05505N193E0219/*.tif"
CROSS_SOURCE_GLOB = "data/raw/reference/jaxa_selene_tc/TC1S2B0_01_05600N005E1008/*.tif"
CROSS_REFERENCE_GLOB = "data/raw/reference/lro_wac/lro_wac_100m_lon99.3-101.4E_lat-0.5-1.3N.tif"

#: Longest side of the prepared same-sensor pair (LoFTR's measured CPU tile budget, README).
MAX_SIDE_PX = 1152
DEFAULT_MATCHERS = ("sift", "akaze", "asift", "lightglue", "loftr")
RUN_DIR = "data/processed/demo_real/v2"

SAME_PREP = (
    "crop both to the intersection of their bounds in the shared CRS; resample (average) both "
    f"to g = max(native GSDs, extent / {MAX_SIDE_PX}); to_uint8(valid = data > 0)"
)
CROSS_PREP = (
    "georeference(tc, tc_ds, wac_ds) onto the WAC grid (cubic, NaN fill); crop both to the "
    "valid bounding box of the reprojected TC; to_uint8(valid = data > 0)"
)


class PairPrepStatus(str, Enum):
    """Why a JAXA pair could or could not be prepared."""

    OK = "ok"
    #: An input file is absent (data gap: the download has not been made here).
    INPUT_MISSING = "input_missing"
    #: Both inputs exist but share no valid ground (the operation found nothing).
    NO_OVERLAP = "no_overlap"

    @property
    def is_failure(self) -> bool:
        return self is not PairPrepStatus.OK


@dataclass
class PairPrepDiagnostics:
    """Counts per :class:`PairPrepStatus` and the first sample of each."""

    counts: dict[str, int] = field(default_factory=dict)
    samples: dict[str, str] = field(default_factory=dict)

    def record(self, status: PairPrepStatus, sample: str) -> None:
        self.counts[status.value] = self.counts.get(status.value, 0) + 1
        self.samples.setdefault(status.value, sample[:200])

    def report(self) -> str:
        total = sum(self.counts.values())
        lines = [f"pair preparation: {self.counts.get('ok', 0)} of {total} pair(s) prepared"]
        words = {
            "input_missing": "input file absent (data gap, not a matching failure)",
            "no_overlap": "inputs present but no shared valid ground",
            "ok": "prepared",
        }
        for status in sorted(self.counts):
            lines.append(
                f"  {status}: {self.counts[status]}  ({words.get(status, status)})  "
                f"e.g. {self.samples[status]}"
            )
        return "\n".join(lines)


@dataclass
class PreparedPair:
    """One prepared pair, or the classified reason it could not be prepared."""

    name: str
    status: PairPrepStatus
    detail: str = ""
    source: np.ndarray | None = None
    reference: np.ndarray | None = None
    source_valid: np.ndarray | None = None
    reference_valid: np.ndarray | None = None
    source_id: str = ""
    reference_id: str = ""
    source_sensor: str = TC_SENSOR
    reference_sensor: str = ""
    gsd_m: float | None = None
    extra: dict = field(default_factory=dict)


def _find(pattern: str) -> Path | None:
    """The first file matching ``pattern`` (sorted), or None."""
    hits = sorted(glob.glob(pattern))
    return Path(hits[0]) if hits else None


def _missing(name: str, patterns: dict[str, str]) -> PreparedPair | None:
    absent = [f"{role} {pat}" for role, pat in patterns.items() if _find(pat) is None]
    if not absent:
        return None
    return PreparedPair(
        name, PairPrepStatus.INPUT_MISSING, detail="no file for " + "; ".join(absent)
    )


def _valid_u8(data: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    from lunar_reg.preprocess.radiometric import to_uint8

    data = np.asarray(data, dtype=np.float32)
    valid = np.isfinite(data) & (data > 0)
    return to_uint8(data, valid=valid), valid


def prepare_same() -> PreparedPair:
    """Two TC passes: shared-CRS intersection crop, common GSD, uint8 stretch."""
    missing = _missing(SAME_PAIR, {"source": SAME_SOURCE_GLOB, "reference": SAME_REFERENCE_GLOB})
    if missing is not None:
        return missing
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.windows import from_bounds

    from lunar_reg.provenance import ValueSource

    src_path, ref_path = _find(SAME_SOURCE_GLOB), _find(SAME_REFERENCE_GLOB)
    with rasterio.open(src_path) as s, rasterio.open(ref_path) as r:
        if s.crs != r.crs:
            # The README records a shared CRS; a different one is a setup error, not a pair outcome.
            raise ValueError(
                f"{SAME_PAIR}: CRS differ ({s.crs} vs {r.crs}); this pair needs one CRS"
            )
        left, bottom = max(s.bounds.left, r.bounds.left), max(s.bounds.bottom, r.bounds.bottom)
        right, top = min(s.bounds.right, r.bounds.right), min(s.bounds.top, r.bounds.top)
        if right <= left or top <= bottom:
            return PreparedPair(
                SAME_PAIR,
                PairPrepStatus.NO_OVERLAP,
                detail=f"bounds of {src_path.name} and {ref_path.name} do not intersect",
            )
        extent = max(right - left, top - bottom)
        native = max(abs(s.res[0]), abs(s.res[1]), abs(r.res[0]), abs(r.res[1]))
        g = max(native, extent / MAX_SIDE_PX)
        shape = (max(1, round((top - bottom) / g)), max(1, round((right - left) / g)))
        arrays = []
        for ds in (s, r):
            window = from_bounds(left, bottom, right, top, transform=ds.transform)
            band = ds.read(
                1,
                window=window,
                out_shape=shape,
                resampling=Resampling.average,
                masked=True,
                boundless=True,
            )
            arrays.append(np.ma.filled(band.astype(np.float32), np.nan))
        crs = s.crs.to_proj4()
    source, source_valid = _valid_u8(arrays[0])
    reference, reference_valid = _valid_u8(arrays[1])
    if not (source_valid & reference_valid).any():
        return PreparedPair(
            SAME_PAIR,
            PairPrepStatus.NO_OVERLAP,
            detail="the intersection holds no pixel valid in both scenes",
        )
    bounds = [float(left), float(bottom), float(right), float(top)]
    return PreparedPair(
        SAME_PAIR,
        PairPrepStatus.OK,
        detail=f"{shape[1]}x{shape[0]} px at {g:.3f} m/px",
        source=source,
        reference=reference,
        source_valid=source_valid,
        reference_valid=reference_valid,
        source_id=src_path.stem,
        reference_id=ref_path.stem,
        reference_sensor=TC_SENSOR,
        gsd_m=float(g),
        extra={
            "pair_prep": SAME_PREP,
            "common_gsd_m": float(g),
            # max(native GSDs, extent / MAX_SIDE_PX): derived from both files' grids.
            "common_gsd_m_source": ValueSource.COMPUTED.value,
            "crop_bounds": bounds,
            "crop_bounds_source": ValueSource.COMPUTED.value,
            "crs": crs,
            "source_file": str(src_path),
            "reference_file": str(ref_path),
        },
    )


def _reproject_onto(image: np.ndarray, src_ds, ref_ds) -> np.ndarray:
    """Same-CRS fallback: resample ``image`` onto the reference grid (cubic, NaN fill)."""
    from rasterio.warp import Resampling, reproject

    out = np.full((ref_ds.height, ref_ds.width), np.nan, dtype=np.float32)
    reproject(
        source=image,
        destination=out,
        src_transform=src_ds.transform,
        src_crs=src_ds.crs,
        src_nodata=0 if src_ds.nodata is None else src_ds.nodata,
        dst_transform=ref_ds.transform,
        dst_crs=ref_ds.crs,
        dst_nodata=np.nan,
        resampling=Resampling.cubic,
    )
    return out


def prepare_cross() -> PreparedPair:
    """TC reprojected onto the WAC grid, both cropped to the TC's valid bounding box."""
    missing = _missing(CROSS_PAIR, {"source": CROSS_SOURCE_GLOB, "reference": CROSS_REFERENCE_GLOB})
    if missing is not None:
        return missing
    import rasterio
    from rasterio.windows import Window
    from rasterio.windows import bounds as window_bounds

    from lunar_reg.preprocess.georeference import georeference
    from lunar_reg.preprocess.pipeline import StepStatus
    from lunar_reg.provenance import ValueSource

    src_path, ref_path = _find(CROSS_SOURCE_GLOB), _find(CROSS_REFERENCE_GLOB)
    with rasterio.open(src_path) as t, rasterio.open(ref_path) as w:
        tc = t.read(1)
        geo = georeference(tc, t, w)
        if geo.status is StepStatus.NOOP:
            reprojected = _reproject_onto(tc, t, w)
        elif not geo.applied:
            return PreparedPair(
                CROSS_PAIR,
                PairPrepStatus.INPUT_MISSING,
                detail=f"georeference not applied: {geo.reason}",
            )
        else:
            reprojected = np.asarray(geo.image, dtype=np.float32)
        del tc
        wac = w.read(1).astype(np.float32)
        tc_valid = np.isfinite(reprojected) & (reprojected > 0)
        if not tc_valid.any():
            return PreparedPair(
                CROSS_PAIR,
                PairPrepStatus.NO_OVERLAP,
                detail=f"{src_path.name} reprojects to no valid WAC pixel",
            )
        rows, cols = np.flatnonzero(tc_valid.any(axis=1)), np.flatnonzero(tc_valid.any(axis=0))
        r0, r1, c0, c1 = int(rows[0]), int(rows[-1]) + 1, int(cols[0]), int(cols[-1]) + 1
        left, bottom, right, top = window_bounds(Window(c0, r0, c1 - c0, r1 - r0), w.transform)
        g = float(max(abs(w.res[0]), abs(w.res[1])))
        crs = w.crs.to_proj4()
    source, source_valid = _valid_u8(reprojected[r0:r1, c0:c1])
    reference, reference_valid = _valid_u8(wac[r0:r1, c0:c1])
    if not (source_valid & reference_valid).any():
        return PreparedPair(
            CROSS_PAIR,
            PairPrepStatus.NO_OVERLAP,
            detail="the TC footprint holds no valid WAC pixel",
        )
    return PreparedPair(
        CROSS_PAIR,
        PairPrepStatus.OK,
        detail=f"{c1 - c0}x{r1 - r0} px at {g:.3f} m/px",
        source=source,
        reference=reference,
        source_valid=source_valid,
        reference_valid=reference_valid,
        source_id=src_path.stem,
        reference_id=ref_path.stem,
        reference_sensor=WAC_SENSOR,
        gsd_m=g,
        extra={
            "pair_prep": CROSS_PREP,
            "common_gsd_m": g,
            # The WAC grid's own pixel size, read from its GeoTIFF geotransform.
            "common_gsd_m_source": ValueSource.DOCUMENTED.value,
            "crop_bounds": [float(left), float(bottom), float(right), float(top)],
            "crop_bounds_source": ValueSource.COMPUTED.value,
            "crs": crs,
            "source_file": str(src_path),
            "reference_file": str(ref_path),
            "georeference_status": "noop_reprojected"
            if geo.status is StepStatus.NOOP
            else geo.status.value,
            "georeference_fit_rms_px": geo.pixel_transform_fit_rms_px,
            "georeference_fit_rms_px_source": geo.pixel_transform_fit_rms_px_source,
        },
    )


PREPARERS = {"same": prepare_same, "cross": prepare_cross}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--root", type=Path, default=Path("data/processed/results"), help="results store"
    )
    parser.add_argument(
        "--matchers", default=",".join(DEFAULT_MATCHERS), help="comma-separated matcher names"
    )
    parser.add_argument("--overwrite", action="store_true", help="replace stored pairs")
    parser.add_argument("--only-pair", choices=sorted(PREPARERS), help="run one pair only")
    return parser


def main(argv: list[str] | None = None) -> int:
    from lunar_reg.pipeline import BatchReport, PipelineConfig, RunStatus, register_pair
    from lunar_reg.results import save_failures, save_results
    from lunar_reg.runrecord import finish_run, start_run, write_run_record

    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    matchers = tuple(m.strip() for m in args.matchers.split(",") if m.strip())
    record = start_run(
        ["scripts/run_jaxa.py", *(sys.argv[1:] if argv is None else argv)],
        {
            "root": str(args.root),
            "matchers": list(matchers),
            "overwrite": args.overwrite,
            "only_pair": args.only_pair,
            "max_side_px": MAX_SIDE_PX,
        },
    )

    diag = PairPrepDiagnostics()
    batch = BatchReport()
    keys = [args.only_pair] if args.only_pair else list(PREPARERS)
    for key in keys:
        pair = PREPARERS[key]()
        diag.record(pair.status, f"{pair.name}: {pair.detail}")
        if pair.status.is_failure:
            continue
        for matcher in matchers:
            config = PipelineConfig(matcher=matcher, gsd_m=pair.gsd_m, extra=dict(pair.extra))
            outcome = register_pair(
                pair.source,
                pair.reference,
                f"{pair.name}_{matcher}",
                config,
                source_id=pair.source_id,
                reference_id=pair.reference_id,
                source_sensor=pair.source_sensor,
                reference_sensor=pair.reference_sensor,
                source_valid=pair.source_valid,
                reference_valid=pair.reference_valid,
            )
            batch.outcomes.append(outcome)

    save_note = ""
    if batch.results:
        try:
            batch.store = save_results(batch.results, args.root, overwrite=args.overwrite)
        except FileExistsError as exc:
            save_note = f"results NOT saved: {exc}"
    save_failures(batch.failures, args.root)

    counts = {f"prep_{s.value}": int(diag.counts.get(s.value, 0)) for s in PairPrepStatus}
    for s in RunStatus:
        counts[s.value] = sum(o.status is s for o in batch.outcomes)
    counts["saved"] = 0 if batch.store is None else int(batch.store.n_saved)
    record = dataclasses.replace(record, notes="; ".join(x for x in (record.notes, save_note) if x))
    artefacts = [
        p
        for p in (Path(args.root) / "index.parquet", Path(args.root) / "failures.parquet")
        if p.exists()
    ]
    rr_path = write_run_record(finish_run(record, counts, artefacts), RUN_DIR)

    print(diag.report())
    print(batch.report())
    if save_note:
        print(save_note)
    print(f"run record: {rr_path}")
    return 0 if batch.results else 1


if __name__ == "__main__":
    raise SystemExit(main())
