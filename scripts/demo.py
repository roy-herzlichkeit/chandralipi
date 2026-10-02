"""One-pair end-to-end demo, for the video and the internal-round submission.

Runs the full pipeline on a chosen illumination case, prints the metrics the
problem statement asks for, and writes the figures the narration refers to. It
reuses :mod:`lunar_reg.viz.figures` -- the same renderers the dashboard uses --
so what appears in the video is what appears in the tool.

Every number printed comes from the run that just happened. The scene is
generated, not lunar, and the script says so in its own output rather than
leaving that for a caption.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np

CASES = {
    "same-sun": ((285.0, 45.0), (285.0, 45.0)),
    "mild-15deg": ((285.0, 45.0), (300.0, 50.0)),
    "hard-30deg": ((285.0, 35.0), (315.0, 55.0)),
    "extreme-180deg": ((285.0, 6.0), (105.0, 62.0)),
}


def main(argv=None) -> int:
    import cv2

    from lunar_reg.eval.conditioning import EXTRAPOLATION_GATE_PX, conditioning_map
    from lunar_reg.eval.error_budget import transform_rms_px
    from lunar_reg.eval.scenes import illumination_pair
    from lunar_reg.ingest.pseudo_gt import NOMINAL_GSD_M, scale_ratio
    from lunar_reg.pipeline import PipelineConfig, register_pair
    from lunar_reg.viz.figures import (
        blend,
        checkerboard,
        coverage_heatmap,
        overlay_heatmap,
        points_outside,
        side_by_side_matches,
    )

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default="hard-30deg", choices=sorted(CASES))
    parser.add_argument("--matcher", default="asift")
    parser.add_argument("--source-sensor", default="OHRC")
    parser.add_argument("--reference-sensor", default="LRO_NAC")
    parser.add_argument("--size", type=int, default=512)
    parser.add_argument("--seed", type=int, default=41)
    parser.add_argument("--out", default="data/processed/demo")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    source_sun, reference_sun = CASES[args.case]
    source, reference, truth, _ = illumination_pair(
        shape=(args.size, args.size),
        seed=args.seed,
        source_sun=source_sun,
        reference_sun=reference_sun,
    )

    ratio = scale_ratio(args.source_sensor, args.reference_sensor)
    rule = "=" * 74
    print(rule)
    print("SIH26166  Multi-modal, sun-angle and scale invariant image correspondence")
    print(rule)
    print(
        f"  source     : {args.source_sensor} @ {NOMINAL_GSD_M.get(args.source_sensor)} m/px, "
        f"sun az {source_sun[0]:.0f} el {source_sun[1]:.0f}"
    )
    print(
        f"  reference  : {args.reference_sensor} @ "
        f"{NOMINAL_GSD_M.get(args.reference_sensor)} m/px, "
        f"sun az {reference_sun[0]:.0f} el {reference_sun[1]:.0f}"
    )
    print(f"  sun azimuth difference : {abs(source_sun[0] - reference_sun[0]):.0f} deg")
    print(f"  nominal scale ratio    : {ratio:.0f}x" if ratio else "  scale ratio: unknown")
    print(f"  matcher    : {args.matcher}")
    print()
    print("  SYNTHETIC SCENE: this scene is synthetic (generated). The terrain is a")
    print("  rendered height field lit under controlled sun angles, not a Chandrayaan-2")
    print("  product. That is why a ground-truth transform exists here and the accuracy")
    print("  line below can be printed at all -- on real data that line is not measurable.")
    print(rule)

    outcome = register_pair(
        source,
        reference,
        pair_id=f"demo_{args.case}_{args.matcher}",
        config=PipelineConfig(matcher=args.matcher, gsd_m=NOMINAL_GSD_M.get(args.source_sensor)),
        source_sensor=args.source_sensor,
        reference_sensor=args.reference_sensor,
        source_sun=source_sun,
        reference_sun=reference_sun,
        synthetic=True,
        notes=f"demo, {args.case}",
    )

    if not outcome.ok:
        print(f"\n  NOT REGISTERED: {outcome.status.value}")
        print(f"  {outcome.detail}")
        print("\n  This is a real outcome, not a crash. Classical descriptors fail")
        print("  outright once the sun azimuth swings far enough; see docs/.")
        return 1

    result = outcome.result
    metrics, uniformity, conditioning = result.metrics, result.uniformity, result.conditioning
    true_rms = transform_rms_px(result.transform, truth, (args.size, args.size))

    print("\n  RESULTS")
    print(f"    matches                    {result.n_matches}")
    print(f"    inliers                    {result.n_inliers} ({metrics['inlier_ratio']:.1%})")
    print(
        f"    RMSE, self-residual        {metrics['rmse_px']:.4f} px"
        f"   <- the metric Makharia et al. report"
    )
    print(f"    RMSE, vs ground truth      {true_rms:.4f} px   <- the honest accuracy")
    print(f"    uniformity U               {uniformity['score']:.3f}")
    print(
        f"    extrapolation p95          {conditioning.get('p95_px', float('nan')):.3f} px"
        f"   (gate {EXTRAPOLATION_GATE_PX} px)"
    )
    print(f"    ECC prefilter chosen       {result.extra.get('ecc_prefilter')}")
    verdict = (
        "SUB-PIXEL ACROSS THE IMAGE"
        if (true_rms < 1.0 and conditioning.get("p95_px", np.inf) <= EXTRAPOLATION_GATE_PX)
        else "sub-pixel at the matched points, NOT established across the image"
    )
    print(f"    verdict                    {verdict}")

    if metrics["rmse_px"] > 0 and true_rms > 0:
        print(f"\n    Note the two RMSE lines differ by {metrics['rmse_px'] / true_rms:.0f}x.")
        print("    The self-residual is the spread of the correspondences about their")
        print("    own fit; it is not registration accuracy, and no published number")
        print("    using that definition can be compared against a truth-based one.")

    mask = result.inlier_mask
    figures = {
        "01_matches.png": side_by_side_matches(
            source, reference, result.src_pts, result.dst_pts, mask, max_lines=120
        ),
        "02_checkerboard.png": checkerboard(source, reference, result.transform),
        "03_blend.png": blend(source, reference, result.transform),
    }
    if mask is not None and mask.sum() >= 8:
        # The demo renders the full-resolution scene (scale 1), so the source
        # shape is the full-resolution frame the points live in.
        n_outside = points_outside(result.src_pts[mask], source.shape[:2])
        if n_outside:
            print(f"\n    {n_outside} inlier point(s) fall outside the source frame")
        spread = conditioning_map(
            result.src_pts[mask],
            result.dst_pts[mask],
            source.shape[:2],
            model=result.metrics["model"],
        )
        figures["04_conditioning.png"] = overlay_heatmap(
            source, coverage_heatmap(spread, source.shape[:2])
        )

    print("\n  FIGURES")
    for name, image in figures.items():
        path = out / f"{args.case}_{args.matcher}_{name}"
        cv2.imwrite(str(path), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
        print(f"    {path}")
    print(rule)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    sys.exit(main())
