"""Cross-instrument pairs at any site (thin CLI over :mod:`lunar_reg.cross`, G41).

Two sub-commands (``Phase_1/LLD/cross_pairs.md`` §6):

``find``
    Test every Chandrayaan-2 product that has a geometry grid against every
    reference in ``configs/references.json``, in the reference's own projection,
    write the C28 ``overlaps.json`` and print the overlap report. Exit 1 only
    when a failure status (unreadable grid or reference) occurred.

        python scripts/run_cross.py find --references configs/references.json \\
            --instruments TMC2,IIRS --out data/processed/cross/overlaps.json

``run``
    Register every ``overlap`` candidate of an ``overlaps.json`` with the site
    runner, centred on the deepest overlap node, then write the aggregate run
    record ``<record-dir>/run_record.json`` (C15). Exit 0 when every candidate
    ran (registration failures are classified, not fatal); exit 1 on a setup
    error.

        python scripts/run_cross.py run --overlaps data/processed/cross/overlaps.json \\
            --references configs/references.json --matchers sift,akaze,lightglue \\
            --results-root data/processed/results --out-dir data/processed/cross/runs

Results against a reference whose ``independent`` is false (a Chandrayaan-2
product such as the TMC-2 ortho) are relative only: their absolute position is
not an independent check. Every saved result carries ``reference_independent``.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

#: Working window = this many working-GSD pixels on a side (LLD §6).
WINDOW_PX = 400


def _csv(text: str) -> tuple[str, ...]:
    return tuple(t.strip() for t in text.split(",") if t.strip())


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    try:
        with open(tmp, "w") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def cmd_find(args) -> int:
    from lunar_reg.cross import find_overlaps, load_references

    refs = load_references(args.references)
    report = find_overlaps(
        Path(args.raw_root),
        refs,
        instruments=_csv(args.instruments),
        levels=_csv(args.levels),
        min_inside=args.min_inside,
    )
    out = Path(args.out)
    _atomic_write_text(out, report.to_json())
    print(report.report())
    print(f"wrote {out}")
    failed = any(c.status.is_failure for c in report.candidates)
    return 1 if failed else 0


def working_gsd_m(source_gsd_m: float, reference_pixel_m: float) -> float:
    """``max(source, reference)`` rounded up to the next 0.5 m (LLD §6)."""
    return math.ceil(max(source_gsd_m, reference_pixel_m) * 2.0) / 2.0


def cmd_run(args) -> int:
    from lunar_reg.constants import SENSORS
    from lunar_reg.cross import load_references, reference_georeference, resolve_reference_path
    from lunar_reg.ingest.catalog import InstrumentStatus, build_catalog
    from lunar_reg.runrecord import finish_run, start_run, write_run_record
    from lunar_reg.sites.runner import SiteConfig, _tag, run_site

    params = {k: v for k, v in vars(args).items() if k != "func"}
    record = start_run(list(sys.argv), params)
    overlaps_path = Path(args.overlaps)
    doc = json.loads(overlaps_path.read_text())
    if doc.get("schema") != 1:
        print(f"{overlaps_path}: unsupported schema {doc.get('schema')!r}", file=sys.stderr)
        return 1
    refs = {r.name: r for r in load_references(args.references)}
    wanted = _csv(args.instruments) if args.instruments else None
    candidates = [c for c in doc["candidates"] if wanted is None or c["instrument"] in wanted]
    instruments = wanted or tuple(sorted({c["instrument"] for c in candidates}))

    counts: dict[str, int] = {}
    notes: list[str] = []
    artefacts: list[str] = [str(overlaps_path)]

    catalog = build_catalog(Path(args.raw_root))
    for inst in instruments:
        status = catalog.status.get(inst)
        counts[f"instrument_{inst}_{status.value if status else 'unknown'}"] = 1
        if status is InstrumentStatus.ABSENT:
            notes.append(f"{inst}: absent, not run")
    for c in candidates:
        key = f"overlap_{c['status']}"
        counts[key] = counts.get(key, 0) + 1
        if c["status"] == "disjoint":
            d = c.get("min_distance_km")
            near = "unknown" if d is None else f"{d:.1f} km"
            notes.append(f"{c['source_product_id']} vs {c['reference']}: disjoint, nearest {near}")

    pairs_run = registrations_ok = registrations_failed = setup_errors = 0
    for c in (c for c in candidates if c["status"] == "overlap"):
        spec = refs.get(c["reference"])
        pid = c["source_product_id"]
        if spec is None:
            setup_errors += 1
            notes.append(f"{pid} vs {c['reference']}: reference not in {args.references}")
            continue
        try:
            geo = reference_georeference(spec)
        except (OSError, ValueError) as exc:  # LabelGeoreferenceError is a ValueError
            setup_errors += 1
            notes.append(f"{pid} vs {spec.name}: reference georeference failed: {exc}"[:300])
            continue
        source_gsd = float(SENSORS[c["instrument"]].gsd_m)
        ref_px = max(geo.pixel_size_x_m, geo.pixel_size_y_m)
        gsd = working_gsd_m(source_gsd, ref_px)
        window_m = WINDOW_PX * gsd
        tag = _tag(pid)
        cfg = SiteConfig(
            site=f"cross_{spec.name}",
            reference_label=resolve_reference_path(spec),
            reference_sensor=spec.sensor,
            raw_root=Path(args.raw_root),
            instruments=(c["instrument"],),
            only=pid,
            levels=(c["level"],),
            gsd_m=gsd,
            window_m=window_m,
            margin_m=0.5 * window_m,
            matchers=_csv(args.matchers),
            coarse=False,
            prior_shift_m=None,
            band_reduction="pca",
            results_root=Path(args.results_root),
            out_dir=Path(args.out_dir) / spec.name / tag,
            overwrite=args.overwrite,
            reference_sun_json=None,
            label_convention_json=None,
            reference_georef=spec.georef,
            reference_name=spec.name,
            reference_independent=spec.independent,
            centres={pid: (int(c["centre_line"]), int(c["centre_sample"]))},
        )
        try:
            report = run_site(cfg)
        except (OSError, ValueError) as exc:
            setup_errors += 1
            notes.append(f"{pid} vs {spec.name}: run_site setup error: {exc}"[:300])
            continue
        print(report.report())
        pairs_run += 1
        n_ok = sum(o.ok for o in report.batch.outcomes)
        registrations_ok += n_ok
        registrations_failed += len(report.batch.outcomes) - n_ok
        if report.run_record_path is not None:
            artefacts.append(str(report.run_record_path))
        if not spec.independent:
            notes.append(f"relative only: reference {spec.name} is not independent")

    counts.update(
        pairs_run=pairs_run,
        registrations_ok=registrations_ok,
        registrations_failed=registrations_failed,
        setup_errors=setup_errors,
    )
    record_dir = Path(args.record_dir) if args.record_dir else overlaps_path.parent
    record = finish_run(record, counts, artefacts)
    record.notes = "; ".join(x for x in (record.notes, *notes) if x)
    path = write_run_record(record, record_dir)
    print(
        f"cross run: {pairs_run} pair(s) run, {registrations_ok} registration(s) ok, "
        f"{registrations_failed} failed, {setup_errors} setup error(s); run record {path}"
    )
    return 1 if setup_errors else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="command", required=True)

    f = sub.add_parser("find", help="classify every (product, reference) overlap")
    f.add_argument("--references", default="configs/references.json")
    f.add_argument("--instruments", default="OHRC,TMC2,IIRS")
    f.add_argument("--levels", default="raw,calibrated")
    f.add_argument("--raw-root", default="data/raw")
    f.add_argument("--min-inside", type=int, default=4)
    f.add_argument("--out", default="data/processed/cross/overlaps.json")
    f.set_defaults(func=cmd_find)

    r = sub.add_parser("run", help="register every overlap candidate")
    r.add_argument("--overlaps", default="data/processed/cross/overlaps.json")
    r.add_argument("--references", default="configs/references.json")
    r.add_argument("--matchers", default="sift,akaze,lightglue")
    r.add_argument("--instruments", default="", help="comma list; default: all in overlaps.json")
    r.add_argument("--raw-root", default="data/raw")
    r.add_argument("--results-root", default="data/processed/results")
    r.add_argument("--out-dir", default="data/processed/cross/runs")
    r.add_argument(
        "--record-dir",
        default="",
        help="where the aggregate run_record.json goes (default: next to --overlaps)",
    )
    r.add_argument("--overwrite", action="store_true")
    r.set_defaults(func=cmd_run)

    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.WARNING)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
