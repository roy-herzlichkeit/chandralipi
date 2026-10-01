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
        print(f"image:      REJECTED (file_name {product.image_path_rejected!r} "
              f"points outside the label's directory)")
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


def cmd_register(args) -> int:
    """Register a source product against a reference and report metrics."""

    from lunar_reg.align.estimate import estimate_transform
    from lunar_reg.eval.metrics import compute_metrics
    from lunar_reg.eval.uniformity import compute_uniformity
    from lunar_reg.ingest.pds4 import open_product
    from lunar_reg.match.learned import build_matcher
    from lunar_reg.match.tiled import TiledMatcher
    from lunar_reg.preprocess.radiometric import standard_chain

    matcher = TiledMatcher(build_matcher(args.matcher), overlap=args.overlap)

    with open_product(args.source) as src, open_product(args.reference) as ref:
        result = matcher.match_datasets(src, ref, preprocess=standard_chain)
        shape = (src.height, src.width)

    if len(result) < 4:
        print(
            f"only {len(result)} correspondences found; cannot estimate a transform",
            file=sys.stderr,
        )
        return 1

    transform, result = estimate_transform(result, model=args.model, threshold_px=args.threshold)
    metrics = compute_metrics(result, transform)
    uniformity = compute_uniformity(result.inliers().src_pts, shape)

    report = {
        "source": str(args.source),
        "reference": str(args.reference),
        "metrics": metrics.as_dict(),
        "uniformity": uniformity.as_dict(),
        "transform": transform.matrix.tolist(),
    }
    text = json.dumps(report, indent=2)
    print(text)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text)
    return 0


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
        cols = ["source_id", "reference_id", "overlap_area_km2",
                "source_fraction", "reference_fraction"]
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
        for _, row in pairs.head(args.limit).iterrows():
            src, ref = by_id.get(row["source_id"]), by_id.get(row["reference_id"])
            if src is None or ref is None:
                continue
            summary = crop_to_overlap(intersect(src, ref), args.crop_dir)
            for side, entry in summary["sides"].items():
                if "error" in entry:
                    print(f"  crop {side} {entry['product_id']}: {entry['error']}")
                else:
                    n_cropped += 1
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lunar-reg", description=__doc__)
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("env", help="report device and VRAM budget").set_defaults(func=cmd_env)

    p_inspect = sub.add_parser("inspect", help="summarise a PDS4 product")
    p_inspect.add_argument("label", type=Path, help="path to the PDS4 XML label")
    p_inspect.set_defaults(func=cmd_inspect)

    p_reg = sub.add_parser("register", help="register a source product to a reference")
    p_reg.add_argument("source", type=Path)
    p_reg.add_argument("reference", type=Path)
    p_reg.add_argument("--matcher", default="loftr", help="loftr | lightglue | sift | akaze | orb")
    p_reg.add_argument("--model", default="homography", help="homography | affine | partial_affine")
    p_reg.add_argument("--threshold", type=float, default=2.0, help="RANSAC threshold in px")
    p_reg.add_argument("--overlap", type=float, default=0.25, help="tile overlap fraction")
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
    p_ov.add_argument("--min-fraction", type=float, default=0.0,
                      help="minimum fraction of the source covered by the overlap")
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
    p_pre.add_argument("--ablate", action="store_true",
                       help="also run a leave-one-out sweep over the enabled steps")
    p_pre.add_argument("--output", type=Path, help="save the preprocessed array (.npy)")
    p_pre.set_defaults(func=cmd_preprocess)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    _setup_logging(args.verbose)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
