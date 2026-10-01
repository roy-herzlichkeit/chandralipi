"""Reference sun geometry for the Vikram LRO NAC frame: SPICE, checked two ways (G14).

    python scripts/fit_reference_sun.py [--nac 1|2] [--half-size-m 3000]
        [--kernels data/raw/reference/spice] [--out data/processed/vikram/reference_sun]
        [--label-convention]

1. SPICE (primary): the Sun's azimuth (clockwise from north) and elevation at
   the NAC frame's ODE centre and ``UTC_start_time`` (record ``M1442997156LE``,
   or ``M1443025251LE`` for ``--nac 2``) from the NAIF generic kernels.
2. Cross-check A: ODE ``Incidence_angle`` -> elevation, compared with SPICE.
3. Cross-check B: a Lambertian hillshade of ``NAC_DTM_VIKRAMSITE1.TIF``
   correlated with a window of the NAC orthoimage (read as a window only,
   reprojected onto the DTM grid); the best azimuth (grid frame) is compared
   with SPICE converted to the grid frame.
4. ``--label-convention``: SPICE at every OHRC label's mid-time and centre,
   compared with the label's ``sun_azimuth`` under the four candidate azimuth
   conventions; writes ``label_convention.json``.

Writes ``reference_sun.json``, ``ncc_curve.csv``, ``label_convention.json``
(with ``--label-convention``) and ``run_record.json`` (C15) under ``--out``.
Every step's outcome is classified and counted; the report prints on every run.
Exit 2 when the SPICE kernels, spiceypy or the ODE JSON are missing (printing
the command that provides each); exit 1 when a step failed; else 0.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402

from lunar_reg.ingest.sun import (  # noqa: E402
    AZIMUTH_FIT_SOURCE,
    SPICE_KERNELS,
    fit_sun_azimuth,
    north_to_grid_azimuth,
    sun_from_label,
    sun_from_ode_metadata,
    sun_from_spice,
)
from lunar_reg.provenance import ValueSource  # noqa: E402

RAW = Path("data/raw")
NAC_DIR = RAW / "reference/lro_nac_vikram"
ODE_JSON = NAC_DIR / "ode/edrnac4_vikram_box.json"
DTM_TIF = NAC_DIR / "NAC_DTM_VIKRAMSITE1.TIF"
NAC_RECORDS = {1: "M1442997156LE", 2: "M1443025251LE"}
NAC_LABELS = {
    1: NAC_DIR / "NAC_DTM_VIKRAMSITE1_M1442997156_100CM.xml",
    2: NAC_DIR / "NAC_DTM_VIKRAMSITE1_M1443025251_100CM.xml",
}
DEFAULT_KERNELS = RAW / "reference/spice"
DEFAULT_OUT = Path("data/processed/vikram/reference_sun")

#: Vikram site point (lat, lon), the fallback SPICE point and the DTM window centre (LLD §2).
SITE_LAT, SITE_LON = -69.37, 32.32
SITE_SOURCE = ValueSource.DOCUMENTED
#: DTM posting (m), measured 2026-09-29 from the TIF's own transform (LLD §2); checked at run time.
DTM_POSTING_M = 3.0
DTM_POSTING_M_SOURCE = ValueSource.MEASURED

#: ODE field names for the record centre, as they appear in edrnac4_vikram_box.json.
ODE_CENTRE_FIELDS = ("Center_latitude", "Center_longitude")

#: The four candidate readings of ISRO's label azimuth (Phase_1B), as functions of label azimuth a.
CONVENTIONS = {
    "as_is": lambda a: a,
    "plus_180": lambda a: a + 180.0,
    "mirror": lambda a: 360.0 - a,
    "mirror_plus_180": lambda a: 180.0 - a,
}

FETCH_SPICE = "scripts/fetch_public.py --only spice_lsk,spice_pck,spice_de440s,ode_edrnac4_box"
INSTALL_SPICE = 'pip install -e ".[spice]"'


class StepOutcome(str, Enum):
    SPICE_OK = "spice_ok"
    ODE_OK = "ode_ok"
    ODE_NO_RECORD = "ode_no_record"
    DTM_FIT_OK = "dtm_fit_ok"
    DTM_INPUT_MISSING = "dtm_input_missing"
    DTM_FIT_FAILED = "dtm_fit_failed"
    LABEL_OK = "label_ok"
    LABEL_FIELDS_MISSING = "label_fields_missing"
    LABEL_FAILED = "label_failed"

    @property
    def is_failure(self) -> bool:
        return self in (
            StepOutcome.ODE_NO_RECORD,
            StepOutcome.DTM_INPUT_MISSING,
            StepOutcome.DTM_FIT_FAILED,
            StepOutcome.LABEL_FIELDS_MISSING,
            StepOutcome.LABEL_FAILED,
        )


class Diagnostics:
    """Per-outcome counts plus the first sample of each."""

    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.first: dict[str, str] = {}

    def record(self, outcome: StepOutcome, sample: str) -> None:
        self.counts[outcome.value] = self.counts.get(outcome.value, 0) + 1
        self.first.setdefault(outcome.value, sample[:300])

    @property
    def has_failure(self) -> bool:
        return any(StepOutcome(k).is_failure and v for k, v in self.counts.items())

    def report(self) -> str:
        lines = ["fit_reference_sun outcomes:"]
        for outcome in StepOutcome:
            n = self.counts.get(outcome.value, 0)
            if n:
                lines.append(f"  {outcome.value:<22} {n:>3}  first: {self.first[outcome.value]}")
        if len(lines) == 1:
            lines.append("  (no step ran)")
        return "\n".join(lines)


def circular_signed(a: float, b: float) -> float:
    """``a - b`` wrapped to [-180, 180)."""
    return (float(a) - float(b) + 180.0) % 360.0 - 180.0


def _finite_or_none(value) -> float | None:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def missing_inputs(kernels: Path) -> list[str]:
    """Each missing prerequisite with the command that provides it."""
    problems = []
    absent = [name for name in SPICE_KERNELS if not (kernels / name).is_file()]
    if absent:
        problems.append(f"SPICE kernels {', '.join(absent)} under {kernels}: run {FETCH_SPICE}")
    if not ODE_JSON.is_file():
        problems.append(f"ODE JSON {ODE_JSON}: run {FETCH_SPICE}")
    try:
        import spiceypy  # noqa: F401
    except ImportError:
        problems.append(f"spiceypy (optional extra `spice`): run {INSTALL_SPICE}")
    return problems


def ode_record(product: str) -> dict | None:
    doc = json.loads(ODE_JSON.read_text())
    records = ((doc.get("ODEResults") or {}).get("Products") or {}).get("Product") or []
    if isinstance(records, dict):
        records = [records]
    for record in records:
        if str(record.get("Product_name", "")).upper().startswith(product.upper()):
            return record
    return None


def spice_primary(nac: int, kernels: Path) -> tuple:
    """SPICE sun at the NAC record's centre and start time: (sun, lat, lon, utc, point_note)."""
    product = NAC_RECORDS[nac]
    record = ode_record(product)
    if record is None:
        raise LookupError(f"no ODE record for {product} in {ODE_JSON}")
    utc = record.get("UTC_start_time")
    if not utc:
        raise LookupError(f"ODE record {product} has no UTC_start_time")
    lat = _finite_or_none(record.get(ODE_CENTRE_FIELDS[0]))
    lon = _finite_or_none(record.get(ODE_CENTRE_FIELDS[1]))
    if lat is None or lon is None:
        lat, lon = SITE_LAT, SITE_LON
        point_note = (
            f"ODE centre fields {ODE_CENTRE_FIELDS} not found in record {product}; "
            f"used the Vikram site point ({SITE_LAT}, {SITE_LON})"
        )
    else:
        point_note = f"ODE record {product} {ODE_CENTRE_FIELDS[0]}/{ODE_CENTRE_FIELDS[1]}"
    sun = sun_from_spice(str(utc), lat, lon, kernels)
    return sun, lat, lon, str(utc), point_note


#: The LLD §2 step-5 ``dtm_fit`` keys (plus the grid-frame SPICE azimuth the fit is compared with).
DTM_FIT_KEYS = (
    "azimuth_grid_deg",
    "ncc_peak",
    "second_peak_deg",
    "second_peak_ncc",
    "peak_margin",
    "n_valid_px",
    "step_deg",
    "spice_azimuth_grid_deg",
    "fit_minus_spice_deg",
)


def empty_dtm_summary(note: str) -> dict:
    """``dtm_fit`` when the fit did not run or failed: every key None, source UNKNOWN."""
    return {**dict.fromkeys(DTM_FIT_KEYS), "source": ValueSource.UNKNOWN.value, "note": note}


def dtm_cross_check(nac: int, half_size_m: float, sun, lat: float, lon: float) -> dict:
    """Hillshade-fit azimuth on a DTM window vs SPICE in the grid frame (raises on failure)."""
    import rasterio
    from affine import Affine
    from rasterio.warp import Resampling, reproject
    from rasterio.windows import Window

    from lunar_reg.ingest.lro import georeference_from_label

    geo = georeference_from_label(NAC_LABELS[nac])
    crs = geo.crs_proj4
    col, row = geo.lonlat_to_pixel(lon=SITE_LON, lat=SITE_LAT)
    centre_x, centre_y = geo.pixel_to_xy(col=col, row=row)
    half_px = int(round(half_size_m / geo.pixel_size_x_m))
    c0, r0 = int(round(float(col))) - half_px, int(round(float(row))) - half_px
    with rasterio.open(NAC_LABELS[nac]) as ds:
        win = Window(c0, r0, 2 * half_px, 2 * half_px)
        nac_win = ds.read(1, window=win, boundless=True, fill_value=0).astype(np.float32)
    nac_transform = geo.affine() @ Affine.translation(c0, r0)

    with rasterio.open(DTM_TIF) as ds:
        dtm_t = ds.transform
        posting = float(dtm_t.a)
        if abs(posting - DTM_POSTING_M) > 1e-6 or abs(-dtm_t.e - DTM_POSTING_M) > 1e-6:
            raise ValueError(f"DTM posting {dtm_t.a}, {dtm_t.e} != {DTM_POSTING_M} m")
        dcol, drow = ~dtm_t @ (float(centre_x), float(centre_y))
        half_dtm = int(round(half_size_m / DTM_POSTING_M))
        dc0, dr0 = int(round(dcol)) - half_dtm, int(round(drow)) - half_dtm
        dwin = Window(dc0, dr0, 2 * half_dtm, 2 * half_dtm)
        dtm = ds.read(1, window=dwin, boundless=True, fill_value=np.nan).astype(np.float64)
        nodata = ds.nodata
        dtm_win_t = ds.window_transform(dwin)
    if nodata is not None:
        dtm[dtm == nodata] = np.nan
    dtm[~np.isfinite(dtm) | (np.abs(dtm) > 1e30)] = np.nan

    nac_on_dtm = np.zeros(dtm.shape, dtype=np.float32)
    reproject(
        nac_win,
        nac_on_dtm,
        src_transform=nac_transform,
        src_crs=crs,
        src_nodata=0,
        dst_transform=dtm_win_t,
        dst_crs=crs,
        dst_nodata=0,
        resampling=Resampling.bilinear,
    )
    fit = fit_sun_azimuth(dtm, DTM_POSTING_M, nac_on_dtm, sun.elevation_deg, valid=nac_on_dtm > 0)
    spice_grid = north_to_grid_azimuth(sun.azimuth_deg, lat, lon, crs)
    return {
        "fit": fit,
        "summary": {
            "azimuth_grid_deg": fit.azimuth_deg,
            "ncc_peak": fit.ncc_peak,
            "second_peak_deg": _finite_or_none(fit.second_peak_deg),
            "second_peak_ncc": _finite_or_none(fit.second_peak_ncc),
            "peak_margin": _finite_or_none(fit.peak_margin),
            "n_valid_px": fit.n_valid_px,
            "step_deg": float(fit.azimuths[1] - fit.azimuths[0]),
            "spice_azimuth_grid_deg": spice_grid,
            "fit_minus_spice_deg": circular_signed(fit.azimuth_deg, spice_grid),
            "source": AZIMUTH_FIT_SOURCE.value,
            "note": (
                f"DTM window {2 * half_dtm} px at {DTM_POSTING_M} m centred on "
                f"({SITE_LAT}, {SITE_LON}); NAC window {2 * half_px} px from "
                f"{NAC_LABELS[nac].name} (georeference {geo.source.value}: {geo.note}), "
                f"bilinear onto the DTM grid; SPICE azimuth converted to the grid frame "
                f"at ({lat}, {lon}) in {crs}"
            ),
        },
    }


def _label_point(product) -> tuple[float, float] | None:
    lats = [product[f"corner{i}_lat"] for i in range(1, 5)]
    lons = [product[f"corner{i}_lon"] for i in range(1, 5)]
    if any(_finite_or_none(v) is None for v in lats + lons):
        return None
    ref = float(lons[0])
    lon = ref + float(np.mean([circular_signed(v, ref) for v in lons]))
    return float(np.mean(lats)), (lon + 180.0) % 360.0 - 180.0


def _utc_text(value) -> str | None:
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value.isoformat()
    return None


def label_convention(kernels: Path, diag: Diagnostics) -> dict:
    """SPICE vs ISRO label sun azimuth for every OHRC label, under the four conventions."""
    from lunar_reg.ingest.catalog import build_catalog
    from lunar_reg.ingest.pds4 import read_label

    catalog = build_catalog(RAW, ("OHRC",))
    per_strip = []
    for entry in catalog.products("OHRC"):
        try:
            product = read_label(entry.label_path)
            label = sun_from_label(product)
            start, stop = product["start_time"], product["stop_time"]
            point = _label_point(product)
            if (
                label.as_tuple() is None
                or point is None
                or not (isinstance(start, datetime) and isinstance(stop, datetime))
            ):
                diag.record(
                    StepOutcome.LABEL_FIELDS_MISSING,
                    f"{entry.product_id}: sun {label.as_tuple()}, point {point}, "
                    f"start {start!r}, stop {stop!r}",
                )
                continue
            mid = start + (stop - start) / 2
            spice = sun_from_spice(_utc_text(mid), point[0], point[1], kernels)
        except Exception as exc:  # noqa: BLE001 - classified and counted, never a crash
            diag.record(
                StepOutcome.LABEL_FAILED, f"{entry.product_id}: {type(exc).__name__}: {exc}"
            )
            continue
        diffs = {
            name: abs(circular_signed(fn(label.azimuth_deg), spice.azimuth_deg))
            for name, fn in CONVENTIONS.items()
        }
        tag = next((t for t in entry.product_id.split("_") if "T" in t and t[:8].isdigit()), "")
        per_strip.append(
            {
                "tag": tag,
                "product_id": entry.product_id,
                "label_azimuth": label.azimuth_deg,
                "label_elevation": label.elevation_deg,
                "spice_azimuth": spice.azimuth_deg,
                "spice_elevation": spice.elevation_deg,
                "diffs": diffs,
            }
        )
        diag.record(StepOutcome.LABEL_OK, entry.product_id)
    if not per_strip:
        return {
            "per_strip": [],
            "convention": None,
            "max_diff_deg": None,
            "elevation_max_diff_deg": None,
            "source": ValueSource.UNKNOWN.value,
            "note": "no OHRC label gave a usable SPICE comparison (see the run's outcome counts)",
        }
    worst = {name: max(s["diffs"][name] for s in per_strip) for name in CONVENTIONS}
    best = min(worst, key=worst.get)
    return {
        "per_strip": per_strip,
        "convention": best,
        "max_diff_deg": worst[best],
        "elevation_max_diff_deg": max(
            abs(s["label_elevation"] - s["spice_elevation"]) for s in per_strip
        ),
        "source": ValueSource.COMPUTED.value,
    }


def _write_json(path: Path, obj) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--nac", type=int, choices=(1, 2), default=1, help="NAC epoch (default 1)")
    ap.add_argument("--half-size-m", type=float, default=3000.0, help="DTM-fit window half size")
    ap.add_argument("--kernels", type=Path, default=DEFAULT_KERNELS, help="NAIF kernel directory")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory")
    ap.add_argument(
        "--label-convention",
        action="store_true",
        help="also compare SPICE with every OHRC label's sun azimuth (label_convention.json)",
    )
    args = ap.parse_args(argv)

    problems = missing_inputs(args.kernels)
    if problems:
        print("fit_reference_sun: missing inputs:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 2

    from lunar_reg.runrecord import finish_run, start_run, write_run_record

    record = start_run(
        [sys.executable, *sys.argv] if argv is None else ["fit_reference_sun.py", *argv],
        {
            "nac": args.nac,
            "half_size_m": args.half_size_m,
            "kernels": str(args.kernels),
            "label_convention": args.label_convention,
        },
    )
    diag = Diagnostics()
    try:
        sun, lat, lon, utc, point_note = spice_primary(args.nac, args.kernels)
    except LookupError as exc:
        print(f"fit_reference_sun: {exc}; re-fetch with {FETCH_SPICE}", file=sys.stderr)
        return 2
    diag.record(StepOutcome.SPICE_OK, f"{NAC_RECORDS[args.nac]} {utc}: {sun.as_tuple()}")

    ode = sun_from_ode_metadata(ODE_JSON, NAC_RECORDS[args.nac])
    if ode.elevation_deg is None:
        diag.record(StepOutcome.ODE_NO_RECORD, ode.note)
        elevation_diff = None
    else:
        diag.record(StepOutcome.ODE_OK, ode.note)
        elevation_diff = ode.elevation_deg - sun.elevation_deg

    artefacts: list[Path] = []
    curve = args.out / "ncc_curve.csv"
    if not (DTM_TIF.is_file() and NAC_LABELS[args.nac].is_file()):
        missing = f"need {DTM_TIF} and {NAC_LABELS[args.nac]} (with its .IMG)"
        diag.record(StepOutcome.DTM_INPUT_MISSING, missing)
        dtm_summary = empty_dtm_summary(f"{StepOutcome.DTM_INPUT_MISSING.value}: {missing}")
    else:
        try:
            result = dtm_cross_check(args.nac, args.half_size_m, sun, lat, lon)
        except Exception as exc:  # noqa: BLE001 - classified and counted, never a crash
            failure = f"{type(exc).__name__}: {exc}"
            diag.record(StepOutcome.DTM_FIT_FAILED, failure)
            dtm_summary = empty_dtm_summary(f"{StepOutcome.DTM_FIT_FAILED.value}: {failure}")
        else:
            dtm_summary = result["summary"]
            diag.record(
                StepOutcome.DTM_FIT_OK,
                f"azimuth {dtm_summary['azimuth_grid_deg']} (grid), "
                f"fit - spice {dtm_summary['fit_minus_spice_deg']:.2f} deg",
            )
            fit = result["fit"]
            curve.parent.mkdir(parents=True, exist_ok=True)
            with open(curve, "w", newline="") as fh:
                writer = csv.writer(fh)
                writer.writerow(["azimuth_deg", "ncc"])
                for az, ncc in zip(fit.azimuths, fit.ncc, strict=True):
                    writer.writerow([f"{az:g}", "" if not np.isfinite(ncc) else f"{ncc:.6f}"])
            artefacts.append(curve)

    doc = {
        "sun": sun.as_dict(),
        "cross_checks": {
            "ode_elevation_deg": ode.elevation_deg,
            "ode_elevation_source": ode.elevation_source.value,
            "ode_note": ode.note,
            "elevation_diff_deg": elevation_diff,
            "elevation_diff_source": (
                ValueSource.COMPUTED.value
                if elevation_diff is not None
                else ValueSource.UNKNOWN.value
            ),
            "dtm_fit": dtm_summary,
        },
        "inputs": {
            "ode_json": str(ODE_JSON),
            "ode_record": NAC_RECORDS[args.nac],
            "utc": utc,
            "lat_deg": lat,
            "lon_deg": lon,
            "point_note": point_note,
            "kernels": [str(args.kernels / k) for k in SPICE_KERNELS],
            "dtm": str(DTM_TIF),
            "nac_label": str(NAC_LABELS[args.nac]),
            "half_size_m": args.half_size_m,
        },
    }
    artefacts.insert(0, _write_json(args.out / "reference_sun.json", doc))

    convention = None
    if args.label_convention:
        convention = label_convention(args.kernels, diag)
        artefacts.append(_write_json(args.out / "label_convention.json", convention))

    record = finish_run(record, diag.counts, artefacts)
    write_run_record(record, args.out)

    print(diag.report())
    print(f"SPICE sun ({NAC_RECORDS[args.nac]}, {utc}): {sun.as_tuple()} [{sun.azimuth_frame}]")
    print(f"ODE elevation {ode.elevation_deg}; ODE - SPICE {elevation_diff}")
    if dtm_summary["fit_minus_spice_deg"] is not None:
        print(
            f"DTM fit azimuth {dtm_summary['azimuth_grid_deg']} (grid), SPICE "
            f"{dtm_summary['spice_azimuth_grid_deg']:.2f} (grid), "
            f"fit - SPICE {dtm_summary['fit_minus_spice_deg']:.2f}, "
            f"margin {dtm_summary['peak_margin']}"
        )
    if convention is not None:
        print(
            f"label convention: {convention['convention']} "
            f"(max diff {convention['max_diff_deg']}, elevation max diff "
            f"{convention['elevation_max_diff_deg']}) over {len(convention['per_strip'])} labels"
        )
    print(f"wrote {', '.join(str(a) for a in artefacts)} and {args.out / 'run_record.json'}")
    return 1 if diag.has_failure else 0


if __name__ == "__main__":
    sys.exit(main())
