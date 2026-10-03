"""Chandrayaan-2 <-> LRO NAC registration at the Vikram landing site (thin CLI).

Source (moving): Chandrayaan-2 OHRC, TMC-2 and IIRS products (raw and
calibrated, whichever the catalog finds PRESENT under ``data/raw``; absent
instruments are reported and skipped). Reference (fixed): the LROC
``NAC_DTM_VIKRAMSITE1`` map-projected orthoimage, 1 m/px. The work is done by
:func:`lunar_reg.sites.runner.run_site` (``Phase_1/LLD/site_runner.md``): pair
preparation at a common ground sample distance (``--gsd``), an optional coarse
pass, the search prior, :func:`lunar_reg.pipeline.register_pair` for every
matcher, and the results store, so the dashboard shows each pair like any other
result. This script builds the :class:`~lunar_reg.sites.runner.SiteConfig`,
prints the run's report and exits 0 only when at least one pair registered.
``--export-only`` re-exports registered GeoTIFFs of stored OHRC raw results
without matching (:func:`export_stored`).

What the numbers mean -- read before quoting any of them
---------------------------------------------------------
There is **no ground truth** here. ``rmse_px`` and friends are the fit's
residual on its own inliers (the "self-residual" this repo warns about), not a
truth-based error. What *is* independently informative:

``label_offset_m``
    How far the transform found by matching moves the OHRC window's centre
    relative to where the OHRC label corners plus the NAC georeference put it.
    It measures the combined error of (a) OHRC raw label corners, interpolated
    bilinearly, and (b) the corrected NAC transform, which is itself only
    established to about 1 km. Large values are expected; they are the reason
    image registration is needed at all.

NAC georeference
----------------
GDAL's transform for these orthoimages is wrong (see the unit warning in
``data/raw/reference/lro_nac_vikram/PROVENANCE.json``). The runner takes the
NAC georeference from its label (:func:`lunar_reg.ingest.lro.georeference_from_label`,
CONTRACTS C10); :func:`export_stored` uses the corrected transform recorded in
PROVENANCE.json. Both use an upper-left x whose sign was inferred from a fit
against the label's bounding coordinates.
"""

from __future__ import annotations

import argparse
import glob
import logging
from enum import Enum
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

#: The two NAC orthoimages in the Vikram DTM bundle. Both sit on the same grid
#: (identical upperleft_corner and pixel_scale in their labels), so one corrected
#: georeference serves both. Epoch 2 was imaged ~8 h after epoch 1.
NAC_IDS = {1: "NAC_DTM_VIKRAMSITE1_M1442997156_100CM", 2: "NAC_DTM_VIKRAMSITE1_M1443025251_100CM"}
NAC_DIR = "data/raw/reference/lro_nac_vikram"
NAC_LABEL = f"{NAC_DIR}/{NAC_IDS[1]}.xml"
NAC_ID = NAC_IDS[1]
REGISTERED_DIR = "data/processed/vikram/registered"
#: Demo default. The pipeline library keeps its own default of 8.
DEFAULT_MIN_INLIERS = 5
#: MEASURED 2026-09-28: the label-corner error on OHRC 20240425T1406019344,
#: from its coarse (8 m/px) and fine (4 m/px) registrations, which agree within
#: 2 m. Used only as a fallback search centre when a strip's own coarse pass
#: fails -- it assumes the label error is similar across strips, which is
#: plausible for one site but unverified.
DEFAULT_PRIOR_SHIFT = "556,-2888"
# Corrected georeference; provenance in PROVENANCE.json. Metres, 1 m/px.
NAC_X0, NAC_Y0, NAC_PX_M = -11043.5, 638258.5, 1.0
NAC_PROJ = "+proj=stere +lat_0=-90 +lat_ts=-69.3 +lon_0=32.3 +R=1737400 +units=m"
MOON_GEO = "+proj=longlat +R=1737400 +no_defs"
OHRC_GSD_M = 0.25

RESULTS_ROOT = "data/processed/results"
SOURCE_SENSOR = "CH2_OHRC_RAW"
REFERENCE_SENSOR = "LRO_NAC_ORTHO"


def stretch_u8(image: np.ndarray) -> np.ndarray:
    """1-99 percentile stretch over non-zero pixels; zero (no data) stays zero."""
    valid = image[image > 0]
    if valid.size == 0:
        return np.zeros(image.shape, np.uint8)
    lo, hi = np.percentile(valid, [1, 99])
    out = np.clip((image.astype(np.float32) - lo) / max(hi - lo, 1e-6) * 254 + 1, 1, 255)
    out[image == 0] = 0
    return out.astype(np.uint8)


def label_corners(product) -> dict[str, tuple[float, float]]:
    """UL/UR/LL/LR (lat, lon) from the project's parsed label.

    corner1..4 are the label's upper_left / upper_right / lower_left /
    lower_right fields, confirmed against a raw OHRC label on 2026-09-28.
    """
    names = ("ul", "ur", "ll", "lr")
    return {
        n: (product[f"corner{i}_lat"], product[f"corner{i}_lon"])
        for i, n in enumerate(names, 1)
    }


def interp_latlon(c, u: float, v: float) -> tuple[float, float]:
    """Bilinear lat/lon at fractional (sample u, line v) of the whole strip."""
    top = [(1 - u) * a + u * b for a, b in zip(c["ul"], c["ur"], strict=True)]
    bot = [(1 - u) * a + u * b for a, b in zip(c["ll"], c["lr"], strict=True)]
    return tuple((1 - v) * t + v * b for t, b in zip(top, bot, strict=True))


def latlon_to_nac_px(lats, lons):
    from rasterio.warp import transform

    xs, ys = transform(MOON_GEO, NAC_PROJ, list(lons), list(lats))
    cols = [(x - NAC_X0) / NAC_PX_M for x in xs]
    rows = [(NAC_Y0 - y) / NAC_PX_M for y in ys]
    return np.array(cols), np.array(rows)


def prepare_pair(label_path: str, nac, gsd: float, window_m: float, margin_m: float,
                 shift_px: tuple[float, float] = (0.0, 0.0)):
    """Source window, reference crop, and the label-based prior transform.

    ``shift_px`` moves the *reference crop* (NAC 1 m pixels) away from where the
    label corners put it -- used by the coarse-to-fine pass. The returned prior is
    always the unshifted label prior, so ``label_offset_m`` keeps its meaning.
    """
    import rasterio
    from rasterio.windows import Window

    from lunar_reg.ingest.pds4 import read_label

    product = read_label(label_path)
    lines, samples = product.lines, product.samples
    win = int(window_m / OHRC_GSD_M)
    win_s = min(win, samples)
    l0, s0 = lines // 2 - win // 2, samples // 2 - win_s // 2
    with rasterio.open(label_path) as ds:
        raw = ds.read(1, window=Window(s0, l0, win_s, win))
    factor = gsd / OHRC_GSD_M
    size = (round(win_s / factor), round(win / factor))
    source = cv2.resize(raw, size, interpolation=cv2.INTER_AREA)
    del raw

    corners = label_corners(product)
    frac = [((s0 + ds_) / samples, (l0 + dl) / lines) for ds_, dl in
            ((0, 0), (win_s, 0), (0, win), (win_s, win))]
    latlon = [interp_latlon(corners, u, v) for u, v in frac]
    cols, rows = latlon_to_nac_px([p[0] for p in latlon], [p[1] for p in latlon])

    margin = margin_m / NAC_PX_M
    dc, dr = shift_px
    c0, r0 = int(cols.min() + dc - margin), int(rows.min() + dr - margin)
    c1, r1 = int(cols.max() + dc + margin), int(rows.max() + dr + margin)
    ref_raw = nac.read(1, window=Window(c0, r0, c1 - c0, r1 - r0), boundless=True, fill_value=0)
    ref_factor = gsd / NAC_PX_M
    reference = cv2.resize(ref_raw, (round((c1 - c0) / ref_factor), round((r1 - r0) / ref_factor)),
                           interpolation=cv2.INTER_AREA)
    ref_valid = float((ref_raw > 0).mean())
    del ref_raw

    # Prior: source px -> reference-crop px, from label corners + NAC georeference.
    src_quad = np.float32([[0, 0], [size[0], 0], [0, size[1]], [size[0], size[1]]])
    dst_quad = np.float32(np.c_[(cols - c0) / ref_factor, (rows - r0) / ref_factor])
    prior = cv2.getPerspectiveTransform(src_quad, dst_quad)

    geo = {"c0": c0, "r0": r0, "ref_factor": ref_factor,
           "shift_e_m": float(dc), "shift_s_m": float(dr),
           "src_win_l0": int(l0), "src_win_s0": int(s0),
           "src_win_lines": int(win), "src_win_samples": int(win_s),
           "label_centre": (float(cols.mean()), float(rows.mean()))}
    return product, stretch_u8(source), stretch_u8(reference), prior, ref_valid, geo


def geometry_extra(geo: dict, gsd_m: float) -> dict:
    """The crop geometry a result was produced with, as reserved C04 ``extra`` keys.

    Recorded numerically at run time so a registered GeoTIFF can later be rebuilt
    from exactly these numbers -- never from defaults or a parsed note.
    """
    return {
        "ref_crop_c0": int(geo["c0"]),
        "ref_crop_r0": int(geo["r0"]),
        "ref_factor": float(geo["ref_factor"]),
        "shift_e_m": float(geo["shift_e_m"]),
        "shift_s_m": float(geo["shift_s_m"]),
        "src_win_l0": int(geo["src_win_l0"]),
        "src_win_s0": int(geo["src_win_s0"]),
        "src_win_lines": int(geo["src_win_lines"]),
        "src_win_samples": int(geo["src_win_samples"]),
        "gsd_m": float(gsd_m),
        "crop_geometry_source": "recorded",
    }


def _stored_shift(extra: dict) -> tuple[float, float] | None:
    """Reference-crop shift parsed from a legacy result's provenance note.

    For results stored before the crop geometry was recorded numerically.
    ``None`` when neither note carries a shift -- never a silent ``(0, 0)``.
    """
    import re

    for key, pattern in (("coarse_pass", r"shift ([+-]?[\d.]+),([+-]?[\d.]+)"),
                         ("search_prior", r"prior shift ([+-]?[\d.]+),([+-]?[\d.]+)")):
        match = re.search(pattern, str(extra.get(key, "")))
        if match:
            return float(match.group(1)), float(match.group(2))
    return None


class ExportStatus(str, Enum):
    EXPORTED = "exported"
    #: no ref_crop_c0/r0 and no parsable legacy note
    RECORDED_GEOMETRY_MISSING = "recorded_geometry_missing"
    #: window_m or margin_m or gsd_m absent
    SETTINGS_UNRECORDED = "settings_unrecorded"
    #: OHRC label or NAC label not on disk
    INPUT_MISSING = "input_missing"
    WRITE_FAILED = "write_failed"


def _export_report(n_results: int, counts: dict, samples: dict) -> str:
    lines = [f"{n_results} stored OHRC result(s):"]
    for status in ExportStatus:
        if counts.get(status):
            lines.append(f"  {status.value}: {counts[status]}  e.g. {samples[status]}")
    if not counts:
        lines.append("  (none)")
    return "\n".join(lines)


def export_stored(only: str = "") -> int:
    """Write registered GeoTIFFs for stored OHRC results without re-matching.

    Each result's crop origin comes from the geometry recorded in its ``extra``
    (``ref_crop_c0``/``ref_crop_r0``, tagged ``crop_geometry_source=recorded``),
    or, for results stored before that, from the shift in its legacy provenance
    note (tagged ``regex_legacy``). Window, margin and working resolution must
    be recorded; nothing falls back to a default. Every result gets an
    :class:`ExportStatus`, reported per status on every run. Returns 0 only when
    every result was exported.
    """
    import rasterio

    from lunar_reg.align.warp import save_registered_geotiff
    from lunar_reg.results import load_index, load_pair

    index = load_index(RESULTS_ROOT)
    ids = [i for i in index["pair_id"] if i.startswith(SOURCE_SENSOR) and only in i]
    counts: dict[ExportStatus, int] = {}
    samples: dict[ExportStatus, str] = {}

    def record(status: ExportStatus, pair_id: str, why: str = "") -> None:
        counts[status] = counts.get(status, 0) + 1
        samples.setdefault(status, f"{pair_id}: {why}" if why else pair_id)
        if status is not ExportStatus.EXPORTED:
            print(f"  NOT exported {pair_id}: {status.value}{f' ({why})' if why else ''}")

    for pair_id in ids:
        r = load_pair(pair_id, RESULTS_ROOT)
        extra = r.extra

        missing = [k for k in ("window_m", "margin_m", "gsd_m") if extra.get(k) is None]
        if missing:
            record(ExportStatus.SETTINGS_UNRECORDED, pair_id, f"no {', '.join(missing)}")
            continue
        gsd = float(extra["gsd_m"])

        recorded = ("ref_crop_c0", "ref_crop_r0", "shift_e_m", "shift_s_m")
        if all(extra.get(k) is not None for k in recorded):
            source_kind = "recorded"
            # The shift sets the reference crop's integer extent, hence the output shape.
            shift = (float(extra["shift_e_m"]), float(extra["shift_s_m"]))
        else:
            shift = _stored_shift(extra)
            if shift is None:
                record(ExportStatus.RECORDED_GEOMETRY_MISSING, pair_id,
                       "no ref_crop_c0/r0 and no shift in coarse_pass/search_prior")
                continue
            source_kind = "regex_legacy"

        tag = pair_id[len(SOURCE_SENSOR) + 1:].split("-")[0]
        labels = glob.glob(f"data/raw/ohrc_vikram/*{tag}*/data/raw/*/*_d_img_*.xml")
        nac_label = f"{NAC_DIR}/{r.reference_id}.xml"
        if not labels or not Path(nac_label).exists():
            record(ExportStatus.INPUT_MISSING, pair_id,
                   f"ohrc label found={bool(labels)}, nac label exists={Path(nac_label).exists()}")
            continue

        try:
            with rasterio.open(nac_label) as nac:
                _, src, ref, _, _, geo = prepare_pair(
                    labels[0], nac, gsd, float(extra["window_m"]), float(extra["margin_m"]),
                    shift)
            if source_kind == "recorded":
                c0, r0 = int(extra["ref_crop_c0"]), int(extra["ref_crop_r0"])
            else:
                c0, r0 = int(geo["c0"]), int(geo["r0"])
            out = save_registered_geotiff(
                src, np.asarray(r.transform), ref.shape[:2], f"{REGISTERED_DIR}/{pair_id}.tif",
                crs=NAC_PROJ,
                origin_xy=(NAC_X0 + c0 * NAC_PX_M, NAC_Y0 - r0 * NAC_PX_M),
                pixel_size=gsd,
                tags={"pair_id": pair_id, "source": r.source_id, "reference": r.reference_id,
                      "matcher": r.matcher,
                      "model": extra.get("model", "unrecorded"),
                      "min_inliers": extra.get("min_inliers", "unrecorded"),
                      "crop_geometry_source": source_kind,
                      "georeference": "corrected NAC transform, see PROVENANCE.json "
                                      "(~1 km absolute)"})
        except Exception as exc:  # noqa: BLE001 - GDAL/rasterio raise many types on a bad write
            record(ExportStatus.WRITE_FAILED, pair_id, f"{type(exc).__name__}: {exc}"[:200])
            continue
        record(ExportStatus.EXPORTED, pair_id)
        print(f"  wrote {out['path']}  ({out['valid_fraction']:.0%} of grid covered, "
              f"{source_kind} crop geometry)")

    print(_export_report(len(ids), counts, samples))
    return 0 if counts.get(ExportStatus.EXPORTED, 0) == len(ids) else 1


def _csv(text: str) -> tuple[str, ...]:
    return tuple(x.strip() for x in text.split(",") if x.strip())


def _prior_shift(text: str) -> tuple[float, float] | None:
    """``"E,S"`` metres, or None for ``''`` (disabled)."""
    if not text.strip():
        return None
    e, s = (float(v) for v in text.split(","))
    return e, s


def main(argv=None) -> int:
    from lunar_reg.align.refine import ECC_PREFILTERS
    from lunar_reg.pairs import BAND_REDUCTIONS
    from lunar_reg.pipeline import PRECISIONS
    from lunar_reg.preprocess.presets import PRESET_NAMES
    from lunar_reg.sites.runner import SiteConfig

    defaults = SiteConfig()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gsd", type=float, default=4.0, help="common ground sample distance, m/px")
    ap.add_argument("--window-m", type=float, default=3000.0, help="source window along-track, m")
    ap.add_argument("--margin-m", type=float, default=1000.0, help="reference crop margin, m")
    ap.add_argument("--matchers", default="sift,akaze,asift,lightglue",
                    help="comma list; also accepts rift2, loftr")
    ap.add_argument("--coarse", action=argparse.BooleanOptionalAction, default=True,
                    help="coarse LightGlue pass (8 m/px, 4 km margin) to re-centre the "
                         "reference crop; never run with --dry-run")
    ap.add_argument("--model", default="homography",
                    choices=("homography", "affine", "partial_affine"))
    ap.add_argument("--min-inliers", type=int, default=DEFAULT_MIN_INLIERS,
                    help="fewest RANSAC inliers accepted as a result")
    ap.add_argument("--ransac-px", type=float, default=3.0, help="RANSAC threshold, px")
    ap.add_argument("--prior-shift", default=DEFAULT_PRIOR_SHIFT, metavar="E,S",
                    help="fallback shift (m, east,south) of the reference crop from the "
                         "label prior, used only when the coarse pass fails and only for "
                         "the instruments it was measured on (OHRC, G38); pass '' to disable")
    ap.add_argument("--nac", type=int, choices=(1, 2), default=1, help="NAC orthoimage epoch")
    ap.add_argument("--only", default="", help="only products whose id contains this")
    ap.add_argument("--instruments", default=",".join(defaults.instruments),
                    help="comma list of Chandrayaan-2 instruments (OHRC, TMC2, IIRS); "
                         "absent ones are reported and skipped")
    ap.add_argument("--levels", default=",".join(defaults.levels),
                    help="comma list of product levels (raw, calibrated)")
    ap.add_argument("--preprocess", default=defaults.preprocess, choices=PRESET_NAMES,
                    help="preprocessing preset run before matching")
    ap.add_argument("--ecc-prefilter", default=defaults.ecc_prefilter,
                    choices=ECC_PREFILTERS, help="ECC prefilter")
    ap.add_argument("--band-reduction", default=defaults.band_reduction, choices=BAND_REDUCTIONS,
                    help="multi-band (IIRS) reduction to one plane")
    ap.add_argument("--results-root", default=RESULTS_ROOT, help="results store")
    ap.add_argument("--out-dir", default=str(defaults.out_dir),
                    help="run_record.json, products.json, previews and registered GeoTIFFs")
    ap.add_argument("--reference-sun-json", default=str(defaults.reference_sun_json),
                    help="reference sun JSON from scripts/fit_reference_sun.py; '' for none")
    ap.add_argument("--save-registered", action=argparse.BooleanOptionalAction, default=True,
                    help="write each registered window as a GeoTIFF under <out-dir>/registered")
    ap.add_argument("--export-only", action="store_true",
                    help="no matching: write registered GeoTIFFs for results already in the "
                         f"store, using their stored transforms (into {REGISTERED_DIR})")
    ap.add_argument("--dry-run", action="store_true",
                    help="prepare and report, do not match (no coarse pass); previews go to "
                         "<out-dir>/preview")
    ap.add_argument("--overwrite", action="store_true",
                    help="replace results already stored under the same pair id")
    # P2.10 (Phase_2/LLD/runner_gpu_runs.md): GPU and native mode; defaults keep Phase 1
    ap.add_argument("--device", default=defaults.device,
                    help="cpu, cuda or cuda:<n> for the learned matchers (default: the "
                         "pipeline's choice, cuda when available)")
    ap.add_argument("--precision", default=defaults.precision, choices=PRECISIONS,
                    help="learned-matcher precision (auto = fp16 for LoFTR on CUDA, else fp32)")
    ap.add_argument("--native", action="store_true",
                    help="refine the --native-matcher result of each strip at the reference's "
                         "native GSD; with --save-registered also write <pair_id>_native.tif "
                         "under <out-dir>/registered")
    ap.add_argument("--native-matcher", default=defaults.native_matcher,
                    help="matcher whose OK result is refined (must be among --matchers)")
    ap.add_argument("--native-tile-px", type=int, default=defaults.native_tile_px,
                    help="native refinement tile side, px (default: align.native's 512)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.WARNING)
    if args.export_only:
        return export_stored(args.only)

    from lunar_reg.sites.runner import run_site

    cfg = SiteConfig(
        reference_label=Path(f"{NAC_DIR}/{NAC_IDS[args.nac]}.xml"),
        reference_sensor=REFERENCE_SENSOR if args.nac == 1 else f"{REFERENCE_SENSOR}_E2",
        instruments=_csv(args.instruments),
        only=args.only,
        levels=_csv(args.levels),
        gsd_m=args.gsd,
        window_m=args.window_m,
        margin_m=args.margin_m,
        matchers=_csv(args.matchers),
        model=args.model,
        min_inliers=args.min_inliers,
        ransac_threshold_px=args.ransac_px,
        preprocess=args.preprocess,
        ecc_prefilter=args.ecc_prefilter,
        coarse=args.coarse and not args.dry_run,
        prior_shift_m=_prior_shift(args.prior_shift),
        band_reduction=args.band_reduction,
        results_root=Path(args.results_root),
        out_dir=Path(args.out_dir),
        save_registered=args.save_registered,
        overwrite=args.overwrite,
        dry_run=args.dry_run,
        reference_sun_json=Path(args.reference_sun_json) if args.reference_sun_json else None,
        device=args.device or None,
        precision=args.precision,
        native=args.native,
        native_matcher=args.native_matcher,
        native_tile_px=args.native_tile_px,
    )
    report = run_site(cfg)
    print(report.report())
    return 0 if report.any_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
