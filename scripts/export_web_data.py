"""Export stored pipeline results for the showcase site.

The Streamlit dashboard stays the live tool -- it reads the ``.npz`` store
directly and is what gets demonstrated to stakeholders. This exporter produces a
*static snapshot* of the same data so the web showcase can be deployed anywhere
without a Python process behind it.

Because it is a snapshot, it can go stale. Every export stamps the source
directory and a UTC timestamp into the JSON, and the site displays both, so a
viewer can always tell how old the figures are rather than assuming they are
live.
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

logger = logging.getLogger("export_web_data")

#: Longest edge of the exported preview images. Smaller than the stored
#: thumbnails: these travel over a network to a browser, and four images per
#: pair at full thumbnail size would make the site slow to load.
WEB_PREVIEW_PX = 720


def _write(image, path: Path, max_px: int = WEB_PREVIEW_PX) -> str:
    import cv2

    array = np.asarray(image)
    longest = max(array.shape[:2])
    if longest > max_px:
        scale = max_px / longest
        array = cv2.resize(
            array, (int(array.shape[1] * scale), int(array.shape[0] * scale)),
            interpolation=cv2.INTER_AREA,
        )
    if array.ndim == 3:
        array = cv2.cvtColor(array, cv2.COLOR_RGB2BGR)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), array, [cv2.IMWRITE_JPEG_QUALITY, 88])
    return path.name


def main(argv=None) -> int:
    from lunar_reg.eval.conditioning import EXTRAPOLATION_GATE_PX, conditioning_map
    from lunar_reg.results import load_index, load_pair
    from lunar_reg.viz.figures import (
        checkerboard,
        coverage_heatmap,
        overlay_heatmap,
        side_by_side_matches,
    )

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", default="data/processed/results")
    parser.add_argument("--out", default="web/public/data")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    frame = load_index(args.results)
    if not len(frame):
        logger.error(
            "no results under %s -- run scripts/build_demo_results.py first", args.results
        )
        return 1

    out = Path(args.out)
    images = out / "pairs"
    if images.exists():
        shutil.rmtree(images)
    images.mkdir(parents=True, exist_ok=True)

    pairs, skipped = [], []
    for _, row in frame.iterrows():
        pair_id = row["pair_id"]
        try:
            result = load_pair(pair_id, args.results)
        except FileNotFoundError as exc:
            skipped.append((pair_id, str(exc)))
            continue

        scale = float(result.extra.get("source_scale", 1.0))
        files = {
            "matches": _write(
                side_by_side_matches(
                    result.source_image, result.reference_image,
                    result.src_pts, result.dst_pts, result.inlier_mask,
                    max_lines=110, scale=scale,
                ),
                images / f"{pair_id}_matches.jpg",
            ),
            "checkerboard": _write(
                checkerboard(result.source_image, result.reference_image, result.transform),
                images / f"{pair_id}_checker.jpg",
            ),
            "source": _write(result.source_image, images / f"{pair_id}_src.jpg", 420),
            "reference": _write(result.reference_image, images / f"{pair_id}_ref.jpg", 420),
        }

        mask = result.inlier_mask
        if mask is not None and mask.sum() >= 8:
            spread = conditioning_map(
                result.src_pts[mask], result.dst_pts[mask], result.source_image.shape[:2]
            )
            files["conditioning"] = _write(
                overlay_heatmap(
                    result.source_image,
                    coverage_heatmap(spread, result.source_image.shape[:2]),
                ),
                images / f"{pair_id}_cond.jpg",
            )

        def number(key, default=None, r=row):
            value = r.get(key, default)
            if value is None or (isinstance(value, float) and not np.isfinite(value)):
                return None
            return float(value) if isinstance(value, (int, float, np.number)) else value

        def text(key, default="", r=row):
            """Like ``number`` but for string-typed columns.

            ``row`` comes from a DataFrame built out of several results' index
            rows, which need not share every ``extra`` key -- a result that
            never set e.g. ``ecc_prefilter`` leaves that *column* present
            (because another row did set it) but *this row's* value missing,
            and pandas fills the gap with float ``NaN`` rather than leaving
            the key absent. A plain ``row.get(key, default)`` therefore finds
            the column and returns that NaN instead of falling back -- and
            Python's ``json.dumps`` emits a bare ``NaN`` token, which is not
            valid JSON and breaks every strict parser (every browser's
            ``JSON.parse`` included), even though `json.load` on the Python
            side accepts it silently. Guard against float NaN explicitly.
            """
            value = r.get(key, default)
            if isinstance(value, float) and not np.isfinite(value):
                return default
            return value

        pairs.append({
            "id": pair_id,
            "sourceId": result.source_id,
            "referenceId": result.reference_id,
            "sourceSensor": result.source_sensor,
            "referenceSensor": result.reference_sensor,
            "matcher": result.matcher,
            "synthetic": bool(result.synthetic),
            "notes": result.notes,
            "case": text("x_case"),
            "nMatches": int(result.n_matches),
            "nInliers": int(result.n_inliers),
            "inlierRatio": number("m_inlier_ratio"),
            "rmseSelf": number("m_rmse_px"),
            "rmseTruth": number("x_true_rms_px"),
            "uniformity": number("u_score"),
            "extrapolationP95": number("c_p95_px"),
            "eccPrefilter": text("x_ecc_prefilter"),
            "sunAzimuthDelta": (
                # Both operands must be present: a DataFrame built from several
                # results' index rows fills a NaN wherever this row did not set a
                # column another row did (the same class the text() docstring
                # covers), so the source azimuth can be finite while the
                # reference one is missing -- abs(float - None) would raise.
                abs(number("x_source_sun_azimuth") - number("x_reference_sun_azimuth"))
                if number("x_source_sun_azimuth") is not None
                and number("x_reference_sun_azimuth") is not None
                else None
            ),
            "images": files,
        })

    payload = {
        "generatedUtc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sourceDirectory": str(Path(args.results).resolve()),
        "extrapolationGatePx": EXTRAPOLATION_GATE_PX,
        "nPairs": len(pairs),
        "allSynthetic": all(p["synthetic"] for p in pairs),
        "pairs": pairs,
    }
    # allow_nan=False: fail loudly here, at export time, rather than writing a
    # file that parses fine on the Python side (json.load accepts bare NaN)
    # and only breaks later in a browser's strict JSON.parse -- the failure
    # mode that just shipped a "No exported results found" page.
    (out / "results.json").write_text(json.dumps(payload, indent=1, allow_nan=False))

    logger.info("exported %d pair(s) to %s", len(pairs), out / "results.json")
    if skipped:
        # A row in the index with no array file is a real inconsistency, not a
        # tidy-up detail; name one so it can be chased.
        logger.warning(
            "%d indexed pair(s) had no stored arrays and were skipped, e.g. %s: %s",
            len(skipped), skipped[0][0], skipped[0][1],
        )
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    sys.exit(main())
