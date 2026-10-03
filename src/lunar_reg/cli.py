"""Command-line entry point.

``lunar-reg env`` is worth running first on any new machine -- it reports the
device and the tile/keypoint budget the rest of the pipeline will use.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )


def cmd_env(args) -> int:
    from lunar_reg.device import describe_environment

    print(describe_environment())
    return 0


def cmd_inspect(args) -> int:
    """Print label metadata and the memory cost of a naive full load."""
    from lunar_reg.device import plan_dense_tile
    from lunar_reg.ingest.pds4 import read_label
    from lunar_reg.ingest.tiling import estimate_full_load_bytes, plan_tiles

    product = read_label(args.label)
    print(f"product:    {product.product_id}")
    print(f"sensor:     {product.sensor}")
    if product.image_path is not None:
        print(f"image:      {product.image_path.name}")
    else:
        print(
            f"image:      REJECTED (file_name {product.image_path_rejected!r} "
            f"points outside the label's directory)"
        )
    print(f"size:       {product.samples} x {product.lines} ({product.bands} band(s))")
    sun_azimuth = product["sun_azimuth_deg"]
    incidence = product["incidence_angle_deg"]
    if sun_azimuth is not None:
        print(f"sun azim:   {sun_azimuth:.2f} deg")
    if incidence is not None:
        print(f"incidence:  {incidence:.2f} deg")

    if product.lines and product.samples:
        full = estimate_full_load_bytes(product.lines, product.samples, product.bands)
        budget = plan_dense_tile()
        tiles = plan_tiles(product.lines, product.samples, budget.tile_px)
        print(f"\nfull float32 load would be {full / 1024**3:.2f} GB -- do not do this")
        print(f"tiled plan: {len(tiles)} tiles at {budget.tile_px}px ({budget})")
    return 0


#: How ``lunar-reg register`` prepares each input (recorded in the result's extra).
REGISTER_INPUT_PREP = (
    "band 1; non-positive / nodata / non-finite pixels invalid; INTER_AREA downsample so the "
    "longest side <= max_px; to_uint8(valid=data>0)"
)


def _read_for_register(path: Path, max_px: int):
    """Band 1 of ``path`` as uint8 plus its validity mask and the downsample factor.

    Rasterio opens GeoTIFFs; PDS4 goes through :func:`~lunar_reg.ingest.pds4.open_product`
    (which also resolves a ``.IMG`` to its label). Invalid pixels (``<= 0``, the
    dataset's nodata value, non-finite) are NaN before an ``INTER_AREA``
    downsample to a longest side of at most ``max_px``, so they never blend into
    valid ones; the stretch is ``to_uint8(valid=data > 0)``.
    """
    import cv2
    import numpy as np

    from lunar_reg.ingest.pds4 import open_product
    from lunar_reg.preprocess.radiometric import to_uint8

    with open_product(path) as dataset:
        data = dataset.read(1)
        nodata = dataset.nodata
    data = data.astype(np.float32)
    invalid = ~np.isfinite(data) | (data <= 0)
    if nodata is not None and np.isfinite(nodata):
        invalid |= data == np.float32(nodata)
    data[invalid] = np.nan
    height, width = data.shape
    factor = max(1.0, max(height, width) / float(max_px))
    if factor > 1.0:
        size = (max(1, round(width / factor)), max(1, round(height / factor)))
        data = cv2.resize(data, size, interpolation=cv2.INTER_AREA)
    valid = np.isfinite(data) & (data > 0)
    return to_uint8(data, valid=valid), valid, factor


def _register_pair_id(source: Path, reference: Path, matcher: str) -> str:
    """``<source stem>-<reference stem>_<matcher>`` reduced to the store's pair-id alphabet."""
    import re

    raw = f"{source.stem}-{reference.stem}_{matcher}"
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", raw)
    return cleaned if cleaned[:1].isalnum() else f"p{cleaned}"


def _plain_group(group: dict) -> dict:
    """A metrics/extra dict with the results-index conversion rules (P0.10 ``_plain_for_index``)."""
    from lunar_reg.results import _plain_for_index

    out = {}
    for key, value in group.items():
        try:
            out[str(key)] = _plain_for_index(str(key), value)
        except TypeError:
            out[str(key)] = str(value)
    return out


def register_document(outcome) -> dict:
    """The ``--output`` JSON of ``lunar-reg register`` (exactly the LLD §3 keys)."""
    import numpy as np

    result = outcome.result
    extra = dict(outcome.extra)
    if result is not None:
        extra = {**extra, **result.extra}
    return {
        "pair_id": outcome.pair_id,
        "status": outcome.status.value,
        "detail": outcome.detail,
        "stage": outcome.extra.get("stage"),
        "metrics": _plain_group(result.metrics) if result is not None else {},
        "uniformity": _plain_group(result.uniformity) if result is not None else {},
        "conditioning": _plain_group(result.conditioning) if result is not None else {},
        "transform": (
            np.asarray(result.transform, dtype=float).tolist() if result is not None else None
        ),
        "extra": _plain_group(extra),
    }


def cmd_register(args) -> int:
    """Register a source image against a reference with :func:`~lunar_reg.pipeline.register_pair`.

    Prints the classified outcome and its key metrics on every run; exit 0 only
    when the pair registered (``RunStatus.OK``).
    """
    from lunar_reg.pipeline import PipelineConfig, register_pair
    from lunar_reg.provenance import ValueSource

    source, source_valid, source_factor = _read_for_register(args.source, args.max_px)
    reference, reference_valid, reference_factor = _read_for_register(args.reference, args.max_px)
    pair_id = args.pair_id or _register_pair_id(args.source, args.reference, args.matcher)
    extra = {
        "input_prep": REGISTER_INPUT_PREP,
        "max_px": int(args.max_px),
        "source_file": str(args.source),
        "reference_file": str(args.reference),
        "source_downsample": float(source_factor),
        "reference_downsample": float(reference_factor),
        "downsample_source": ValueSource.COMPUTED.value,
    }
    config = PipelineConfig(
        matcher=args.matcher,
        model=args.model,
        ransac_threshold_px=args.threshold,
        preprocess=args.preprocess,
        extra=extra,
    )
    outcome = register_pair(
        source,
        reference,
        pair_id,
        config,
        source_id=args.source.stem,
        reference_id=args.reference.stem,
        source_valid=source_valid,
        reference_valid=reference_valid,
    )

    doc = register_document(outcome)
    print(f"{pair_id}: {doc['status']} (stage {doc['stage']})")
    if outcome.detail:
        print(f"  detail: {outcome.detail}")
    print(
        f"  input: source {source.shape[1]}x{source.shape[0]} (downsample {source_factor:.3g}), "
        f"reference {reference.shape[1]}x{reference.shape[0]} "
        f"(downsample {reference_factor:.3g})"
    )
    if outcome.ok:
        m = doc["metrics"]
        print(
            f"  matches {m.get('n_matches')}, inliers {m.get('n_inliers')}, "
            f"rmse {m.get('rmse_px')} px, median {m.get('median_px')} px (self-residual)"
        )
        print(f"  uniformity score {doc['uniformity'].get('score')}")

    if args.save_root:
        from lunar_reg.results import save_failures, save_results

        if outcome.ok:
            try:
                print(save_results([outcome.result], args.save_root).report())
            except FileExistsError as exc:
                print(f"  NOT saved: {exc}")
        else:
            path = save_failures([outcome], args.save_root)
            print(f"  failure recorded in {path}")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(doc, indent=2, allow_nan=True) + "\n")
        print(f"wrote {args.output}")
    return 0 if outcome.ok else 1


def cmd_probe_label(args) -> int:
    """Dump a real label's structure, so the field map stops guessing."""
    from lunar_reg.ingest.probe import format_report, suggest_fieldmap

    print(format_report(args.label, show_all=args.all))
    if args.suggest:
        print()
        print("=" * 70)
        print("SUGGESTED fieldmap.py BLOCK (paste over the UNVERIFIED section)")
        print("=" * 70)
        print(suggest_fieldmap(args.label))
    return 0


def cmd_fields(args) -> int:
    """Report which manifest fields are trusted and which are still guesses."""
    from lunar_reg.ingest.fieldmap import summary

    print(summary())
    return 0


def cmd_manifest(args) -> int:
    """Scan a directory of products into a Parquet manifest."""
    import pandas as pd

    from lunar_reg.ingest.lro import scan_lro_directory
    from lunar_reg.ingest.manifest import manifest_summary, scan_directory, write_manifest

    frames = []
    if args.chandrayaan2:
        frames.append(scan_directory(args.chandrayaan2, archive="chandrayaan2"))
    if args.lro:
        frames.append(scan_lro_directory(args.lro))
    if not frames:
        print("give at least one of --chandrayaan2 or --lro", file=sys.stderr)
        return 2

    frame = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]
    print(manifest_summary(frame))
    if args.output:
        write_manifest(frame, args.output)
        print(f"\nwrote {args.output}")
    return 0


def cmd_overlap(args) -> int:
    """Find OHRC/TMC-2 footprint overlaps and optionally crop to them."""
    from lunar_reg.ingest.manifest import read_manifest
    from lunar_reg.ingest.overlap import (
        crop_to_overlap,
        find_overlapping_pairs,
        footprint_from_row,
        intersect,
    )

    manifest = read_manifest(args.manifest)
    pairs, diagnostics = find_overlapping_pairs(
        manifest,
        source_sensor=args.source_sensor,
        reference_sensor=args.reference_sensor,
        min_source_fraction=args.min_fraction,
    )

    # Always print the full breakdown: a pair that produced a degenerate or
    # empty polygon must be visible, not silently absent from the output.
    print(diagnostics.report())
    print()
    print(f"usable pairs: {len(pairs)}")

    if len(pairs):
        cols = [
            "source_id",
            "reference_id",
            "overlap_area_km2",
            "source_fraction",
            "reference_fraction",
        ]
        print(pairs[cols].head(args.limit).to_string(index=False))

    if args.output and len(pairs):
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        pairs.to_parquet(args.output, index=False)
        print(f"\nwrote {args.output}")

    if args.crop_dir and len(pairs):
        by_id = {}
        for _, row in manifest.iterrows():
            poly = footprint_from_row(row)
            if poly is not None:
                by_id[poly.product_id] = poly
        n_cropped = 0
        # A pair whose footprint cannot be rebuilt from the manifest is counted
        # and named, never dropped silently (A115).
        n_skipped, skipped_sample = 0, ""
        for _, row in pairs.head(args.limit).iterrows():
            src, ref = by_id.get(row["source_id"]), by_id.get(row["reference_id"])
            if src is None or ref is None:
                n_skipped += 1
                if not skipped_sample:
                    skipped_sample = str(row["source_id"] if src is None else row["reference_id"])
                continue
            summary = crop_to_overlap(intersect(src, ref), args.crop_dir)
            for side, entry in summary["sides"].items():
                if "error" in entry:
                    print(f"  crop {side} {entry['product_id']}: {entry['error']}")
                else:
                    n_cropped += 1
        if n_skipped:
            print(f"skipped {n_skipped}, e.g. {skipped_sample} (footprint cannot be rebuilt)")
        else:
            print("skipped 0")
        print(f"\ncropped {n_cropped} image(s) into {args.crop_dir}")

    # Non-zero exit when nothing worked but something was attempted, so a CI
    # run cannot mistake an all-degenerate result for success.
    return 1 if (diagnostics.n_pairs_considered and not len(pairs)) else 0


def cmd_params(args) -> int:
    """Report which preprocessing parameters come from the paper and which are ours."""
    from lunar_reg.preprocess.params import provenance_report

    print(provenance_report())
    return 0


def cmd_catalog(args) -> int:
    """Print what is on disk per instrument; exit 1 only when one is UNREADABLE (G24)."""
    from lunar_reg.ingest.catalog import InstrumentStatus, build_catalog

    catalog = build_catalog(args.raw_root)
    print(catalog.report())
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(catalog.as_dict(), indent=2) + "\n")
        print(f"\nwrote {args.json}")
    unreadable = any(s is InstrumentStatus.UNREADABLE for s in catalog.status.values())
    return 1 if unreadable else 0


def cmd_preprocess(args) -> int:
    """Run the preprocessing pipeline (optionally an ablation sweep) on a product."""
    import numpy as np

    from lunar_reg.ingest.pds4 import open_product
    from lunar_reg.preprocess.config import (
        ablation_configs,
        iirs_wac_config,
        minimal_config,
        ohrc_nac_config,
    )
    from lunar_reg.preprocess.pipeline import PreprocessContext, run_pipeline

    presets = {
        "ohrc_nac": ohrc_nac_config,
        "iirs_wac": iirs_wac_config,
        "minimal": minimal_config,
    }
    config = presets[args.preset]()

    with open_product(args.product) as dataset:
        image = dataset.read() if dataset.count > 1 else dataset.read(1)
        context = PreprocessContext(src_dataset=dataset, src_gsd_m=args.src_gsd)
        configs = ablation_configs(config) if args.ablate else [config]
        for cfg in configs:
            result = run_pipeline(image, cfg, context)
            print(result.report())
            print()
            if args.output and cfg is configs[0]:
                out = np.asarray(result.image)
                np.save(args.output, out)
                print(f"wrote {args.output} {out.shape} {out.dtype}\n")
    return 0


def _tile_sizes(text: str) -> tuple[int, ...]:
    """``--tile-sizes`` parser: comma-separated positive integers."""
    try:
        sizes = tuple(int(v) for v in text.split(",") if v.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"not a comma-separated list of integers: {text!r}"
        ) from exc
    if not sizes or any(v <= 0 for v in sizes):
        raise argparse.ArgumentTypeError(f"tile sizes must be positive integers: {text!r}")
    return sizes


def _repo_path(path: Path) -> str:
    """Repo-relative POSIX path when ``path`` is under the repo, else absolute."""
    repo = Path(__file__).resolve().parents[2]
    resolved = Path(path).resolve()
    if resolved.is_relative_to(repo):
        return resolved.relative_to(repo).as_posix()
    return resolved.as_posix()


def cmd_benchmark(args) -> int:
    """Measure matcher peak memory per tile size; optionally fit a C16 device profile.

    Writes ``<out>/benchmark_<matcher>_<precision>.json`` (rows + outcome
    counts) and ``<out>/run_<matcher>_<precision>/run_record.json`` (C15), prints
    the table and the outcome report on every run, and with ``--profile-out``
    merges the fitted entry into that C16 profile. Exit 0 when every size was OK
    or the sweep ended at an OOM (and the profile, if asked for, was written);
    1 when a timeout / setup error / no-output was recorded or the profile could
    not be fitted or written; 2 for ``--profile-out`` with a non-CUDA device.
    """
    import dataclasses

    from lunar_reg.match import benchmark as bm
    from lunar_reg.provenance import ValueSource
    from lunar_reg.runrecord import finish_run, start_run, write_run_record

    device = args.device
    if args.profile_out and not device.startswith("cuda"):
        print(
            "benchmark: --profile-out needs --device cuda; a device profile (C16) is "
            "VRAM measured by the CUDA allocator, and a CPU run measures host RSS"
        )
        return 2

    out: Path = args.out
    stem = f"{args.matcher}_{args.precision}"
    bench_path = out / f"benchmark_{stem}.json"
    run_dir = out / f"run_{stem}"
    rr_path = run_dir / "run_record.json"
    params = {
        "matcher": args.matcher,
        "precision": args.precision,
        "device": device,
        "tile_sizes": list(args.tile_sizes),
        "timeout_s": int(args.timeout),
        "profile_out": str(args.profile_out) if args.profile_out else None,
        "lightglue_keypoints": bm.LIGHTGLUE_KEYPOINTS if args.matcher == "lightglue" else None,
    }
    record = start_run(list(sys.argv), params)
    # Read before the sweep and from the driver: a torch free-memory query here
    # would hold a CUDA context in this process for the whole sweep.
    free_before = bm.free_bytes_before_sweep(device)

    rows = bm.benchmark_matcher(
        args.matcher, args.tile_sizes, args.timeout, device=device, precision=args.precision
    )
    diag = bm.diagnose(rows)

    fit, fit_error = None, ""
    try:
        fit = bm.fit_profile(rows)
    except ValueError as exc:
        fit_error = str(exc)
    if fit is not None and not all(r.measurement.is_device_measurement for r in rows if r.ok):
        fit_note = "host RSS fit (NOT VRAM)"
    else:
        fit_note = "cuda allocator fit" if fit is not None else ""

    doc = {
        "matcher": args.matcher,
        "precision": args.precision,
        "device": device,
        "tile_sizes": list(args.tile_sizes),
        "timeout_s": int(args.timeout),
        "free_bytes_before": free_before,
        "free_bytes_before_source": (
            ValueSource.MEASURED if free_before is not None else ValueSource.UNKNOWN
        ).value,
        "rows": [r.as_dict() for r in rows],
        "outcome_counts": dict(diag.counts),
        "outcome_samples": dict(diag.samples),
        "stopped_at_oom_px": bm.oom_stop_px(rows),
        "fit": fit,
        "fit_source": ValueSource.INFERRED.value if fit is not None else None,
        "fit_note": fit_note,
        "fit_error": fit_error,
        "run_record": _repo_path(rr_path),
    }
    out.mkdir(parents=True, exist_ok=True)
    bench_path.write_text(json.dumps(doc, indent=2) + "\n")
    artefacts = [bench_path]

    profile_failed = False
    profile_msg = ""
    if args.profile_out:
        if fit is None:
            profile_failed = True
            profile_msg = f"profile NOT updated ({args.profile_out}): {fit_error}"
        elif fit_note != "cuda allocator fit":
            profile_failed = True
            profile_msg = (
                f"profile NOT updated ({args.profile_out}): an OK row was not measured "
                "by the CUDA allocator"
            )
        else:
            try:
                profile = bm.merge_profile_entry(
                    args.profile_out,
                    args.matcher,
                    args.precision,
                    fit,
                    facts=bm.cuda_device_facts(device),
                    measured_utc=record.started_utc,
                    run_record=_repo_path(rr_path),
                    free_bytes_at_measure=free_before,
                )
            except (ValueError, RuntimeError, OSError) as exc:
                profile_failed = True
                profile_msg = f"profile NOT updated ({args.profile_out}): {exc}"
            else:
                artefacts.append(Path(args.profile_out))
                entry = profile.entry(args.matcher, args.precision)
                profile_msg = (
                    f"profile {args.profile_out}: {args.matcher}/{args.precision} "
                    f"fixed_bytes {entry['fixed_bytes']}, "
                    f"bytes_per_px {entry['bytes_per_px']:.4g}, "
                    f"max_tile_px {entry['max_tile_px']}, {len(entry['points'])} points"
                )

    record = finish_run(record, diag.counts, artefacts)
    notes = [record.notes] if record.notes else []
    if doc["stopped_at_oom_px"] is not None:
        notes.append(f"sweep stopped at OOM at {doc['stopped_at_oom_px']}px")
    if fit_error:
        notes.append(f"no fit: {fit_error}")
    if profile_msg:
        notes.append(profile_msg)
    record = dataclasses.replace(record, notes="; ".join(notes))
    write_run_record(record, run_dir)

    print(bm.format_report(rows, device=device))
    print()
    print(diag.report())
    if fit is not None:
        print(
            f"fit ({fit_note}): fixed_bytes {fit['fixed_bytes']}, "
            f"bytes_per_px {fit['bytes_per_px']:.4g}, max_tile_px {fit['max_tile_px']}"
        )
    else:
        print(f"fit: none ({fit_error})")
    if profile_msg:
        print(profile_msg)
    print(f"wrote {bench_path}")
    print(f"wrote {rr_path}")

    hard_failure = any(
        r.outcome.is_failure and r.outcome is not bm.MeasureOutcome.OOM for r in rows
    )
    return 1 if (hard_failure or profile_failed) else 0


def build_parser() -> argparse.ArgumentParser:
    from lunar_reg.preprocess.presets import PRESET_NAMES

    parser = argparse.ArgumentParser(prog="lunar-reg", description=__doc__)
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("env", help="report device and VRAM budget").set_defaults(func=cmd_env)

    p_inspect = sub.add_parser("inspect", help="summarise a PDS4 product")
    p_inspect.add_argument("label", type=Path, help="path to the PDS4 XML label")
    p_inspect.set_defaults(func=cmd_inspect)

    p_reg = sub.add_parser("register", help="register a source image to a reference")
    p_reg.add_argument("source", type=Path, help="GeoTIFF, PDS4 label or other raster")
    p_reg.add_argument("reference", type=Path)
    p_reg.add_argument("--matcher", default="sift", help="any name in lunar_reg.match")
    p_reg.add_argument("--model", default="homography", help="homography | affine | partial_affine")
    p_reg.add_argument("--threshold", type=float, default=3.0, help="RANSAC threshold in px")
    p_reg.add_argument("--preprocess", default="none", choices=list(PRESET_NAMES))
    p_reg.add_argument(
        "--max-px",
        type=int,
        default=1152,
        help="downsample each image so its longest side is at most this",
    )
    p_reg.add_argument("--save-root", type=Path, help="results store to save the outcome in")
    p_reg.add_argument("--pair-id", help="pair id (default: <source>-<reference>_<matcher>)")
    p_reg.add_argument("--output", type=Path, help="write the JSON report here")
    p_reg.set_defaults(func=cmd_register)

    p_probe = sub.add_parser(
        "probe-label",
        help="dump a real label's structure (use this to verify the field map)",
    )
    p_probe.add_argument("label", type=Path, help="path to a real PDS4 or PDS3 label")
    p_probe.add_argument("--all", action="store_true", help="list every leaf element")
    p_probe.add_argument(
        "--suggest", action="store_true", help="emit a fieldmap.py block from what was found"
    )
    p_probe.set_defaults(func=cmd_probe_label)

    p_fields = sub.add_parser("fields", help="show field-mapping provenance")
    p_fields.set_defaults(func=cmd_fields)

    p_man = sub.add_parser("manifest", help="scan products into a Parquet manifest")
    p_man.add_argument("--chandrayaan2", type=Path, help="directory of CH-2 PDS4 labels")
    p_man.add_argument("--lro", type=Path, help="directory of LRO reference labels")
    p_man.add_argument("--output", type=Path, help="write the manifest here (.parquet)")
    p_man.set_defaults(func=cmd_manifest)

    p_cat = sub.add_parser("catalog", help="list what is on disk per instrument")
    p_cat.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    p_cat.add_argument("--json", type=Path, help="also write {status, entries} as JSON here")
    p_cat.set_defaults(func=cmd_catalog)

    p_ov = sub.add_parser("overlap", help="find footprint overlaps between two sensors")
    p_ov.add_argument("manifest", type=Path, help="manifest .parquet from `lunar-reg manifest`")
    p_ov.add_argument("--source-sensor", default="OHRC")
    p_ov.add_argument("--reference-sensor", default="TMC2")
    p_ov.add_argument(
        "--min-fraction",
        type=float,
        default=0.0,
        help="minimum fraction of the source covered by the overlap",
    )
    p_ov.add_argument("--limit", type=int, default=20, help="rows to show / pairs to crop")
    p_ov.add_argument("--output", type=Path, help="write matched pairs here (.parquet)")
    p_ov.add_argument("--crop-dir", type=Path, help="crop both images of each pair into here")
    p_ov.set_defaults(func=cmd_overlap)

    p_par = sub.add_parser("params", help="preprocessing parameter provenance (paper vs ours)")
    p_par.set_defaults(func=cmd_params)

    p_pre = sub.add_parser("preprocess", help="run the Makharia et al. preprocessing pipeline")
    p_pre.add_argument("product", type=Path, help="PDS4 label of the product to preprocess")
    p_pre.add_argument("--preset", default="ohrc_nac", choices=["ohrc_nac", "iirs_wac", "minimal"])
    p_pre.add_argument("--src-gsd", type=float, help="source ground sample distance in metres")
    p_pre.add_argument(
        "--ablate",
        action="store_true",
        help="also run a leave-one-out sweep over the enabled steps",
    )
    p_pre.add_argument("--output", type=Path, help="save the preprocessed array (.npy)")
    p_pre.set_defaults(func=cmd_preprocess)

    p_bench = sub.add_parser(
        "benchmark", help="measure matcher memory per tile size; fit a device profile"
    )
    p_bench.add_argument("--matcher", default="loftr", choices=["loftr", "lightglue"])
    p_bench.add_argument("--precision", default="fp16", choices=["fp16", "fp32"])
    p_bench.add_argument(
        "--tile-sizes",
        type=_tile_sizes,
        default=(256, 384, 512, 640, 768, 896, 1024),
        help="comma-separated tile sides in px (default 256,384,512,640,768,896,1024)",
    )
    p_bench.add_argument("--device", default="cuda", choices=["cuda", "cpu"])
    p_bench.add_argument("--out", type=Path, required=True, help="directory for the outputs")
    p_bench.add_argument(
        "--profile-out", type=Path, help="merge the fitted entry into this C16 profile JSON"
    )
    p_bench.add_argument("--timeout", type=int, default=900, help="seconds per tile size")
    p_bench.set_defaults(func=cmd_benchmark)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    _setup_logging(args.verbose)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
