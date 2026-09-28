"""First real Chandrayaan-2 OHRC <-> LRO NAC registration: the Vikram landing site.

Source (moving): Chandrayaan-2 OHRC **raw** (``nrp``) products, 0.25 m/px,
camera geometry. Reference (fixed): the LROC ``NAC_DTM_VIKRAMSITE1`` map-projected
orthoimage, 1 m/px. Both are resampled to a common ground sample distance
(``--gsd``) before matching, and every pair goes through the project's own
:func:`lunar_reg.pipeline.register_pair` and is saved into the normal results
store, so the dashboard shows it like any other result.

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
``data/raw/reference/lro_nac_vikram/PROVENANCE.json``). This script uses the
corrected transform recorded there, including an upper-left x whose sign was
inferred from a fit against the label's bounding coordinates.
"""

from __future__ import annotations

import argparse
import glob
import logging
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
#: MEASURED (ODE): source frames M1442997156L/RC, 2023-07-03, incidence ~74 deg.
#: INFERRED, not measured: azimuth north-west, from the full-moon date putting
#: 32 deg E in early lunar afternoon. The label publishes no sun geometry.
REFERENCE_SUN_NOTE = (
    "NAC source frames 2023-07-03, incidence ~74 deg (ODE); azimuth not published, "
    "inferred north-west from the full-moon date"
)


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
           "label_centre": (float(cols.mean()), float(rows.mean()))}
    return product, stretch_u8(source), stretch_u8(reference), prior, ref_valid, geo


def centre_offset_m(found: np.ndarray, prior: np.ndarray, shape, gsd: float) -> float:
    h, w = shape[:2]
    pt = np.float32([[[w / 2, h / 2]]])
    a = cv2.perspectiveTransform(pt, found)[0, 0]
    b = cv2.perspectiveTransform(pt, prior)[0, 0]
    return float(np.hypot(*(a - b)) * gsd)


def coarse_shift(label: str, nac, args) -> tuple[tuple[float, float], str]:
    """Find where the OHRC window really sits in the NAC, at 8 m/px with a 4 km margin.

    Returns the NAC-pixel shift of the window centre relative to the label prior,
    and a short note for the result's provenance. On failure the shift is zero and
    the note says why -- the fine pass then falls back to the label prior.
    """
    from lunar_reg.pipeline import PipelineConfig, RunStatus, register_pair

    gsd, margin = 8.0, 4000.0
    _, src, ref, _, _, geo = prepare_pair(label, nac, gsd, args.window_m, margin)
    outcome = register_pair(src, ref, "coarse", PipelineConfig(matcher="lightglue",
                            n_bootstrap=0, use_ecc=False))
    if outcome.status is not RunStatus.OK:
        note = f"coarse pass failed ({outcome.status.value}); label prior used"
        print(f"   coarse     {note}")
        return (0.0, 0.0), note
    h, w = src.shape[:2]
    x, y = cv2.perspectiveTransform(np.float32([[[w / 2, h / 2]]]), outcome.result.transform)[0, 0]
    found = (geo["c0"] + x * geo["ref_factor"], geo["r0"] + y * geo["ref_factor"])
    shift = (found[0] - geo["label_centre"][0], found[1] - geo["label_centre"][1])
    n = outcome.result.metrics["n_inliers"]
    note = f"8 m/px LightGlue, {n} inliers, shift {shift[0]:+.0f},{shift[1]:+.0f} m (E,S)"
    print(f"   coarse     {note}")
    return shift, note


def _stored_shift(extra: dict) -> tuple[float, float]:
    """Reference-crop shift a stored result was produced with, from its provenance."""
    import re

    for key, pattern in (("coarse_pass", r"shift ([+-]?\d+),([+-]?\d+)"),
                         ("search_prior", r"prior shift ([+-]?[\d.]+),([+-]?[\d.]+)")):
        match = re.search(pattern, str(extra.get(key, "")))
        if match:
            return float(match.group(1)), float(match.group(2))
    return 0.0, 0.0


def export_stored(only: str = "") -> int:
    """Write registered GeoTIFFs for stored OHRC results without re-matching.

    Each result's crop is rebuilt from the settings recorded in its ``extra``
    (window, margin, search shift, working resolution), then warped with its
    stored transform. Results whose settings cannot be recovered are reported,
    not skipped silently.
    """
    import rasterio

    from lunar_reg.align.warp import save_registered_geotiff
    from lunar_reg.results import load_index, load_pair

    index = load_index(RESULTS_ROOT)
    ids = [i for i in index["pair_id"] if i.startswith(SOURCE_SENSOR) and only in i]
    written, problems = [], []
    for pair_id in ids:
        r = load_pair(pair_id, RESULTS_ROOT)
        extra, metrics = r.extra, r.metrics
        gsd = extra.get("gsd_m")
        if gsd is None and metrics.get("rmse_px"):
            gsd = round(metrics["rmse_m"] / metrics["rmse_px"], 3)
        tag = pair_id[len(SOURCE_SENSOR) + 1:].split("-")[0]
        labels = glob.glob(f"data/raw/ohrc_vikram/*{tag}*/data/raw/*/*_d_img_*.xml")
        nac_label = f"{NAC_DIR}/{r.reference_id}.xml"
        if not gsd or not labels or not Path(nac_label).exists():
            problems.append((pair_id, f"gsd={gsd}, ohrc label found={bool(labels)}, "
                                      f"nac label exists={Path(nac_label).exists()}"))
            continue
        with rasterio.open(nac_label) as nac:
            _, src, ref, _, _, geo = prepare_pair(
                labels[0], nac, float(gsd), float(extra.get("window_m", 3000.0)),
                float(extra.get("margin_m", 1000.0)), _stored_shift(extra))
        out = save_registered_geotiff(
            src, np.asarray(r.transform), ref.shape[:2], f"{REGISTERED_DIR}/{pair_id}.tif",
            crs=NAC_PROJ,
            origin_xy=(NAC_X0 + geo["c0"] * NAC_PX_M, NAC_Y0 - geo["r0"] * NAC_PX_M),
            pixel_size=float(gsd),
            tags={"pair_id": pair_id, "source": r.source_id, "reference": r.reference_id,
                  "matcher": r.matcher, "model": extra.get("model", "homography"),
                  "min_inliers": extra.get("min_inliers", 8),
                  "georeference": "corrected NAC transform, see PROVENANCE.json (~1 km absolute)"})
        written.append(out["path"])
        print(f"  wrote {out['path']}  ({out['valid_fraction']:.0%} of grid covered)")
    print(f"{len(ids)} stored OHRC result(s): {len(written)} exported, {len(problems)} not")
    for pair_id, why in problems:
        print(f"  NOT exported {pair_id}: {why}")
    return 0 if not problems else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gsd", type=float, default=4.0, help="common ground sample distance, m/px")
    ap.add_argument("--window-m", type=float, default=3000.0, help="OHRC window along-track, m")
    ap.add_argument("--margin-m", type=float, default=1000.0, help="NAC crop margin, m")
    ap.add_argument("--matchers", default="sift,akaze,asift,lightglue",
                    help="comma list; also accepts rift2, loftr")
    ap.add_argument("--coarse", action=argparse.BooleanOptionalAction, default=True,
                    help="coarse LightGlue pass (8 m/px, 4 km margin) to re-centre the "
                         "reference crop")
    ap.add_argument("--model", default="homography",
                    choices=("homography", "affine", "partial_affine"))
    ap.add_argument("--min-inliers", type=int, default=DEFAULT_MIN_INLIERS,
                    help="fewest RANSAC inliers accepted as a result")
    ap.add_argument("--ransac-px", type=float, default=3.0, help="RANSAC threshold, px")
    ap.add_argument("--prior-shift", default=DEFAULT_PRIOR_SHIFT, metavar="E,S",
                    help="fallback shift (m, east,south) of the reference crop from the "
                         "label prior, used only when the coarse pass fails; pass '' to "
                         "disable")
    ap.add_argument("--nac", type=int, choices=(1, 2), default=1, help="NAC orthoimage epoch")
    ap.add_argument("--only", default="", help="only products whose id contains this")
    ap.add_argument("--save-registered", action=argparse.BooleanOptionalAction, default=True,
                    help=f"write each registered OHRC window as a GeoTIFF under {REGISTERED_DIR}")
    ap.add_argument("--export-only", action="store_true",
                    help="no matching: write registered GeoTIFFs for results already in the "
                         "store, using their stored transforms")
    ap.add_argument("--dry-run", action="store_true", help="prepare and report, do not match")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.WARNING)
    if args.export_only:
        return export_stored(args.only)

    import rasterio

    from lunar_reg.align.warp import save_registered_geotiff
    from lunar_reg.pipeline import PipelineConfig, RunStatus, register_pair
    from lunar_reg.results import save_results

    nac_id = NAC_IDS[args.nac]
    ref_sensor = REFERENCE_SENSOR if args.nac == 1 else f"{REFERENCE_SENSOR}_E2"
    variant = "" if args.model == "homography" else f"_{args.model}"
    labels = sorted(glob.glob("data/raw/ohrc_vikram/*/data/raw/*/*_d_img_*.xml"))
    labels = [x for x in labels if args.only in x]
    if not labels:
        print("no OHRC labels under data/raw/ohrc_vikram")
        return 1

    results, outcomes = [], []
    with rasterio.open(f"{NAC_DIR}/{nac_id}.xml") as nac:
        for label in labels:
            shift, coarse_note = (0.0, 0.0), "none"
            if args.coarse:
                shift, coarse_note = coarse_shift(label, nac, args)
            search_prior = "coarse pass" if shift != (0.0, 0.0) else "label corners"
            if shift == (0.0, 0.0) and args.prior_shift:
                shift = tuple(float(v) for v in args.prior_shift.split(","))
                search_prior = f"prior shift {args.prior_shift} m (E,S)"
            product, src, ref, prior, ref_valid, geo = prepare_pair(
                label, nac, args.gsd, args.window_m, args.margin_m, shift)
            tag = Path(label).stem.split("_")[3]  # e.g. 20230823T1450475804
            sun = (product["sun_azimuth_deg"], product["sun_elevation_deg"])
            print(f"\n{tag}: source {src.shape[1]}x{src.shape[0]}"
                  f"  reference {ref.shape[1]}x{ref.shape[0]}"
                  f"  ref valid {ref_valid:.0%}  sun az {sun[0]:.1f} el {sun[1]:.1f}")
            if args.dry_run:
                cv2.imwrite(f"/tmp/vikram_{tag}_src.png", src)
                cv2.imwrite(f"/tmp/vikram_{tag}_ref.png", ref)
                continue
            for matcher in args.matchers.split(","):
                pair_id = f"{SOURCE_SENSOR}_{tag}-{ref_sensor}_{matcher}{variant}"
                config = PipelineConfig(
                    matcher=matcher, gsd_m=args.gsd, model=args.model,
                    min_inliers=args.min_inliers, ransac_threshold_px=args.ransac_px,
                    extra={"window_m": args.window_m, "margin_m": args.margin_m,
                           "site": "Vikram (Chandrayaan-2 landing site)",
                           "ohrc_level": "raw (nrp) -- not radiometrically calibrated",
                           "coarse_pass": coarse_note, "search_prior": search_prior,
                           "gsd_m": args.gsd,
                           "model": args.model, "min_inliers": args.min_inliers,
                           "ransac_threshold_px": args.ransac_px,
                           "reference_sun": REFERENCE_SUN_NOTE},
                )
                outcome = register_pair(
                    src, ref, pair_id, config,
                    source_id=product.product_id.rsplit(":", 1)[-1], reference_id=nac_id,
                    source_sensor=SOURCE_SENSOR, reference_sensor=ref_sensor,
                    source_sun=None, reference_sun=None, synthetic=False,
                    notes=("Real data. No ground truth: RMSE is the fit's self-residual. "
                           "label_offset_m compares the matched transform with the "
                           "label-corner + corrected-NAC-georeference prior."),
                )
                row = {"tag": tag, "matcher": matcher, "status": outcome.status.value,
                       "detail": outcome.detail}
                if outcome.status is RunStatus.OK:
                    r = outcome.result
                    offset = centre_offset_m(r.transform, prior, src.shape, args.gsd)
                    r.extra.update({"label_offset_m": offset,
                                    "ohrc_sun_azimuth": sun[0], "ohrc_sun_elevation": sun[1]})
                    if args.save_registered:
                        out = save_registered_geotiff(
                            src, np.asarray(r.transform), ref.shape[:2],
                            f"{REGISTERED_DIR}/{pair_id}.tif", crs=NAC_PROJ,
                            origin_xy=(NAC_X0 + geo["c0"] * NAC_PX_M,
                                       NAC_Y0 - geo["r0"] * NAC_PX_M),
                            pixel_size=args.gsd,
                            tags={"pair_id": pair_id, "source": r.source_id,
                                  "reference": nac_id, "matcher": matcher,
                                  "model": args.model, "min_inliers": args.min_inliers,
                                  "search_prior": search_prior,
                                  "georeference": "corrected NAC transform, see "
                                                  "PROVENANCE.json (~1 km absolute)"})
                        r.extra["registered_geotiff"] = out["path"]
                    results.append(r)
                    m = r.metrics
                    row.update(inliers=m.get("n_inliers"), matches=m.get("n_matches"),
                               rmse=m.get("rmse_px"), uni=r.uniformity.get("score"),
                               offset=offset)
                outcomes.append(row)
                print(f"   {matcher:<10} {row['status']:<18} "
                      + (f"inliers {row['inliers']}/{row['matches']}  self-RMSE {row['rmse']:.2f}px"
                         f"  uniformity {row['uni']:.2f}  label offset {row['offset']:.0f} m"
                         if row["status"] == "ok" else str(row["detail"])[:90]))

    if results:
        frame = save_results(results, RESULTS_ROOT)
        print(f"\nsaved {len(results)} result(s); index now covers {len(frame)} pair(s)")
    failed = [o for o in outcomes if o["status"] != "ok"]
    print(f"{len(outcomes)} run(s): {len(outcomes) - len(failed)} ok, {len(failed)} not ok")
    for o in failed:
        print(f"   {o['tag']} {o['matcher']}: {o['status']} -- {str(o['detail'])[:120]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
