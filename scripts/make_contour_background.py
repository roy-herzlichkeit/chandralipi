"""Generate the site's background: real lunar contour lines.

The showcase site needs a faint topographic field behind the content. Rather
than draw a decorative one, this traces **actual iso-elevation contours from
NASA's LOLA lunar elevation model** — the same raster the 3D Moon uses as its
bump map. The lines a visitor sees are the Moon's real hypsometry.

That distinction matters beyond taste: a generic topo pattern is ornament, and
ornament on a research project reads as filler. Contours derived from the
mission data are a quiet restatement of what the project does.

Output is SVG, not a raster: it scales to any viewport without a second asset,
stays a few tens of kilobytes, and its stroke colour can be driven from CSS so
the same file serves the light and dark themes.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

#: Iso-elevation levels to trace. Enough to read as terrain, few enough that the
#: field stays quiet behind text. Real contour maps use an even interval, so
#: these are evenly spaced through the elevation range rather than chosen.
DEFAULT_LEVELS = 26

#: Contours shorter than this are dropped. Below it a contour is a speckle of
#: noise in the DEM rather than a landform, and thousands of them turn a quiet
#: field into grey mud.
MIN_CONTOUR_POINTS = 14

#: Douglas-Peucker tolerance in source pixels. The output is displayed at least
#: four times larger than the source raster, so simplification this gentle is
#: invisible while removing most of the file size.
SIMPLIFY_EPSILON = 0.6


def trace_contours(
    elevation: np.ndarray,
    levels: int,
    min_points: int = MIN_CONTOUR_POINTS,
    epsilon: float = SIMPLIFY_EPSILON,
) -> list[np.ndarray]:
    """Iso-elevation polylines through an elevation raster."""
    smoothed = cv2.GaussianBlur(elevation.astype(np.float32), (0, 0), 1.6)
    low, high = float(smoothed.min()), float(smoothed.max())
    if high <= low:
        raise ValueError("elevation raster is flat; nothing to contour")

    polylines: list[np.ndarray] = []
    for value in np.linspace(low, high, levels + 2)[1:-1]:
        mask = (smoothed >= value).astype(np.uint8)
        found, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
        for contour in found:
            if len(contour) < min_points:
                continue
            simplified = cv2.approxPolyDP(contour, epsilon, True)
            if len(simplified) >= 4:
                polylines.append(simplified.reshape(-1, 2))
    return polylines


def to_svg(polylines, width: int, height: int, stroke_width: float = 0.9) -> str:
    """Wrap polylines in an SVG whose stroke colour is inherited from CSS.

    ``stroke="currentColor"`` is the whole trick: the file is theme-agnostic and
    the page decides whether the lines are dark on paper or light on ink.
    """
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" fill="none" stroke="currentColor" '
        f'stroke-width="{stroke_width}" stroke-linejoin="round" '
        'stroke-linecap="round" aria-hidden="true">'
    ]
    for line in polylines:
        points = " ".join(f"{x:.0f},{y:.0f}" for x, y in line)
        parts.append(f'<polygon points="{points}"/>')
    parts.append("</svg>")
    return "".join(parts)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="web/public/textures/moon_displacement.jpg")
    parser.add_argument("--out", default="web/public/textures/lunar-contours.svg")
    parser.add_argument("--levels", type=int, default=DEFAULT_LEVELS)
    # The full equirectangular map is badly distorted at the poles and its
    # aspect is wrong for a page background, so a nearside crop is used.
    parser.add_argument("--crop", default="0.30,0.18,0.46,0.62",
                        help="x,y,w,h as fractions of the source raster")
    parser.add_argument("--scale", type=int, default=3)
    parser.add_argument("--min-points", type=int, default=MIN_CONTOUR_POINTS)
    parser.add_argument("--epsilon", type=float, default=SIMPLIFY_EPSILON)
    args = parser.parse_args(argv)

    elevation = cv2.imread(args.source, cv2.IMREAD_GRAYSCALE)
    if elevation is None:
        print(f"could not read {args.source}", file=sys.stderr)
        return 1

    fx, fy, fw, fh = (float(v) for v in args.crop.split(","))
    rows, cols = elevation.shape
    x0, y0 = int(fx * cols), int(fy * rows)
    x1, y1 = int((fx + fw) * cols), int((fy + fh) * rows)
    patch = elevation[y0:y1, x0:x1]

    # Upscale before tracing so the contours are smooth curves rather than the
    # staircase you get from tracing a small raster and scaling the result.
    patch = cv2.resize(
        patch, (patch.shape[1] * args.scale, patch.shape[0] * args.scale),
        interpolation=cv2.INTER_CUBIC,
    )

    polylines = trace_contours(patch, args.levels, args.min_points, args.epsilon)
    svg = to_svg(polylines, patch.shape[1], patch.shape[0])

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg)

    print(f"{len(polylines)} contour(s) from {args.levels} levels")
    print(f"{out}  {out.stat().st_size / 1024:.1f} kB  {patch.shape[1]}x{patch.shape[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
