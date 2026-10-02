"""Export stored pipeline results for the showcase site.

The Streamlit dashboard stays the live tool -- it reads the ``.npz`` store
directly and is what gets demonstrated to stakeholders. This exporter produces a
*static snapshot* of the same data so the web showcase can be deployed anywhere
without a Python process behind it.

Because it is a snapshot, it can go stale. Every export stamps the source
directory (relative to the repository root) and a UTC timestamp into the JSON,
and the site displays both, so a viewer can always tell how old the figures are
rather than assuming they are live.

The export is swapped in atomically: everything is written under
``<out>/.export_tmp/`` first, and only a complete export replaces the current
``<out>/pairs`` and ``<out>/results.json``. A failed export leaves the current
one untouched. Failed registrations from ``failures.parquet`` are exported
alongside the pairs (``failures``, ``nFailures``), never dropped.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

logger = logging.getLogger("export_web_data")

#: Longest edge of the exported preview images. Smaller than the stored
#: thumbnails: these travel over a network to a browser, and four images per
#: pair at full thumbnail size would make the site slow to load.
WEB_PREVIEW_PX = 720

#: Repository root; ``sourceDirectory`` is written relative to it so the
#: exported JSON does not leak the exporting machine's absolute paths.
REPO_ROOT = Path(__file__).resolve().parents[1]

#: Fields of one failed run copied from ``failures.parquet`` into the export.
FAILURE_FIELDS = ("status", "detail", "stage", "pair_id", "created_utc")

#: Names of the two scratch directories the atomic swap uses under ``--out``.
#: These two paths, and nothing else, are ever removed with ``shutil.rmtree``.
TMP_DIRNAME = ".export_tmp"
OLD_DIRNAME = ".export_old"


def _write(image, path: Path, max_px: int = WEB_PREVIEW_PX) -> str:
    import cv2

    array = np.asarray(image)
    longest = max(array.shape[:2])
    if longest > max_px:
        scale = max_px / longest
        array = cv2.resize(
            array,
            (int(array.shape[1] * scale), int(array.shape[0] * scale)),
            interpolation=cv2.INTER_AREA,
        )
    if array.ndim == 3:
        array = cv2.cvtColor(array, cv2.COLOR_RGB2BGR)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), array, [cv2.IMWRITE_JPEG_QUALITY, 88]):
        raise OSError(f"cv2.imwrite failed for {path}")
    return path.name


def _plain(value):
    """A parquet cell as a JSON-safe value (NaN/NaT/None -> None, numpy -> Python)."""
    if value is None:
        return None
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    try:
        import pandas as pd

        if value is pd.NaT or (not isinstance(value, (str, bytes)) and pd.isna(value)):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _failures(root: str) -> list[dict]:
    from lunar_reg.results import load_failures

    frame = load_failures(root)
    return [
        {key: _plain(row.get(key)) for key in FAILURE_FIELDS}
        for row in frame.to_dict(orient="records")
    ]


def _swap_in(out: Path, tmp: Path) -> None:
    """Replace ``out/pairs`` and ``out/results.json`` with the finished ``tmp`` export.

    The current ``pairs`` is renamed to ``.export_old`` first and only removed
    after both new entries are in place. If either rename fails, everything
    already moved is put back, so the current export is left untouched.
    """
    old = out / OLD_DIRNAME
    current = out / "pairs"
    if old.exists():
        shutil.rmtree(old)
    moved_old = False
    if current.exists():
        os.replace(current, old)
        moved_old = True
    try:
        os.replace(tmp / "pairs", current)
    except BaseException:
        if moved_old:
            os.replace(old, current)
        raise
    try:
        os.replace(tmp / "results.json", out / "results.json")
    except BaseException:
        # The new pairs are in place but results.json is still the old one:
        # move the new pairs back into the scratch directory and restore the old.
        os.replace(current, tmp / "pairs")
        if moved_old:
            os.replace(old, current)
        raise
    if moved_old:
        shutil.rmtree(old)
    shutil.rmtree(tmp)


def _recover_interrupted_swap(out: Path) -> None:
    """Repair what an export killed mid-swap left behind (only the two scratch paths).

    ``_swap_in`` runs only after ``.export_tmp/results.json`` is written and
    fsynced, so the scratch directory holding ``results.json`` but no ``pairs``
    means the kill came between the two renames: the new pairs are already
    current and the swap is finished by moving the new ``results.json`` in.
    """
    old = out / OLD_DIRNAME
    tmp = out / TMP_DIRNAME
    current = out / "pairs"
    staged_results = tmp / "results.json"
    if old.exists() and not current.exists():
        # Killed between renaming the current pairs aside and moving the new
        # ones in: the old export is still the current one, put it back.
        os.replace(old, current)
        logger.warning("restored %s from an interrupted export", current)
    elif current.exists() and staged_results.exists() and not (tmp / "pairs").exists():
        # Killed between moving the new pairs in and replacing results.json.
        os.replace(staged_results, out / "results.json")
        logger.warning("completed an interrupted export swap into %s", out)
    if old.exists():
        shutil.rmtree(old)
    if tmp.exists():
        shutil.rmtree(tmp)


def main(argv=None) -> int:
    from lunar_reg.results import load_index

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", default="data/processed/results")
    parser.add_argument("--out", default="web/public/data")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    frame = load_index(args.results)
    if not len(frame):
        logger.error("no results under %s -- run scripts/build_demo_results.py first", args.results)
        return 1

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    _recover_interrupted_swap(out)
    tmp = out / TMP_DIRNAME
    images = tmp / "pairs"
    images.mkdir(parents=True, exist_ok=True)
    try:
        payload, skipped = _export(frame, args.results, images)
        # allow_nan=False: fail loudly here, at export time, rather than writing a
        # file that parses fine on the Python side (json.load accepts bare NaN)
        # and only breaks later in a browser's strict JSON.parse -- the failure
        # mode that once shipped a "No exported results found" page.
        text = json.dumps(payload, indent=1, allow_nan=False)
        with open(tmp / "results.json", "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
    except BaseException:
        # The current export is untouched; only the scratch directory goes.
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    _swap_in(out, tmp)

    logger.info(
        "exported %d pair(s) and %d failed run(s) to %s",
        payload["nPairs"],
        payload["nFailures"],
        out / "results.json",
    )
    if skipped:
        # A row in the index whose arrays cannot be read is a real
        # inconsistency, not a tidy-up detail: count by error type, name one.
        counts = Counter(kind for _, kind, _ in skipped)
        logger.warning(
            "%d indexed pair(s) could not be loaded and were not exported (%s), e.g. %s: %s",
            len(skipped),
            ", ".join(f"{k}={n}" for k, n in sorted(counts.items())),
            skipped[0][0],
            skipped[0][2],
        )
    return 0


def _export(frame, results_root, images: Path):
    """Render every indexed pair into ``images`` and build the JSON payload.

    Returns ``(payload, skipped)``; ``skipped`` lists ``(pair_id, error type,
    message)`` for every indexed pair whose arrays could not be loaded.
    """
    from lunar_reg.eval.conditioning import EXTRAPOLATION_GATE_PX, conditioning_map
    from lunar_reg.provenance import Sourced, ValueSource
    from lunar_reg.results import load_pair
    from lunar_reg.viz.figures import (
        checkerboard,
        coverage_heatmap,
        overlay_heatmap,
        points_outside,
        side_by_side_matches,
        thumbnail_transform,
    )

    pairs, skipped = [], []
    for _, row in frame.iterrows():
        pair_id = row["pair_id"]
        try:
            result = load_pair(pair_id, results_root)
        except Exception as exc:  # noqa: BLE001 -- every load error is counted, not only a missing file
            skipped.append((pair_id, type(exc).__name__, str(exc)))
            continue

        src_scale = float(result.extra.get("source_scale", 1.0))
        ref_scale = float(result.extra.get("reference_scale", 1.0))
        thumb_transform = thumbnail_transform(result.transform, src_scale, ref_scale)
        files = {
            "matches": _write(
                side_by_side_matches(
                    result.source_image,
                    result.reference_image,
                    result.src_pts,
                    result.dst_pts,
                    result.inlier_mask,
                    max_lines=110,
                    src_scale=src_scale,
                    ref_scale=ref_scale,
                ),
                images / f"{pair_id}_matches.jpg",
            ),
            "checkerboard": _write(
                checkerboard(result.source_image, result.reference_image, thumb_transform),
                images / f"{pair_id}_checker.jpg",
            ),
            "source": _write(result.source_image, images / f"{pair_id}_src.jpg", 420),
            "reference": _write(result.reference_image, images / f"{pair_id}_ref.jpg", 420),
        }

        mask = result.inlier_mask
        n_outside = None
        model = result.metrics.get("model")
        model_used = (
            Sourced(model, ValueSource.MEASURED, "metrics['model'] of the stored run")
            if model
            else Sourced("homography", ValueSource.INFERRED, "model not recorded in the stored run")
        )
        if mask is not None and mask.sum() >= 8:
            thumb_shape = result.source_image.shape[:2]
            full_shape = (
                int(round(thumb_shape[0] / src_scale)),
                int(round(thumb_shape[1] / src_scale)),
            )
            n_outside = points_outside(result.src_pts[mask], full_shape)
            if n_outside:
                logger.warning(
                    "%s: %d inlier point(s) fall outside the %dx%d source frame",
                    pair_id,
                    n_outside,
                    full_shape[1],
                    full_shape[0],
                )
            spread = conditioning_map(
                result.src_pts[mask],
                result.dst_pts[mask],
                full_shape,
                model=model_used.value,
            )
            files["conditioning"] = _write(
                overlay_heatmap(result.source_image, coverage_heatmap(spread, thumb_shape)),
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

        pairs.append(
            {
                "id": pair_id,
                "sourceId": result.source_id,
                "referenceId": result.reference_id,
                "sourceSensor": result.source_sensor,
                "referenceSensor": result.reference_sensor,
                "matcher": result.matcher,
                "licence": result.extra.get("licence"),
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
                "conditioningModel": model_used.as_dict(),
                # Inlier source points outside the full-resolution frame
                # round(thumbnail shape / source_scale); counted, never dropped.
                "conditioningPointsOutside": Sourced(
                    n_outside,
                    ValueSource.COMPUTED,
                    "inlier source points outside round(thumbnail shape / source_scale)"
                    if n_outside is not None
                    else "no conditioning map (fewer than 8 inliers)",
                ).as_dict(),
                "images": files,
            }
        )

    failures = _failures(results_root)
    payload = {
        "generatedUtc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sourceDirectory": os.path.relpath(Path(results_root).resolve(), REPO_ROOT),
        "extrapolationGatePx": EXTRAPOLATION_GATE_PX,
        "nPairs": len(pairs),
        "allSynthetic": all(p["synthetic"] for p in pairs),
        "pairs": pairs,
        "nFailures": len(failures),
        "failures": failures,
        "nLoadErrors": len(skipped),
    }
    return payload, skipped


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    sys.exit(main())
