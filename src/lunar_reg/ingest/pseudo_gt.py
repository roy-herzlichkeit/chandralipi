"""Weak ground truth for cross-sensor pairs, from georeferencing alone.

Why this module exists
----------------------
There is no labelled correspondence set for OHRC/TMC-2/IIRS. Every learned
cross-modal matcher in the literature is trained on pairs whose correspondences
are known, and the standard trick when they are not (MINIMA, arXiv:2412.19412)
is to *synthesise* the hard modality from an easy one so the labels come along
for free. We cannot do that here -- an IIRS cube is not a style transfer of a
TMC-2 frame, it is a different physical measurement at 1/16th the sampling.

What we have instead is that both products are independently georeferenced. A
lat/lon in the overlap region maps into each product's pixel grid on its own,
without either image ever being looked at. Those two pixel positions are a
correspondence. It costs nothing, it is available for every overlapping pair,
and it is uniformly distributed by construction because we choose the sample
grid.

The catch, stated up front
--------------------------
**These correspondences are exactly as accurate as the two products' geometry
metadata, and no more.** They are not measurements of the imagery. Two specific
traps follow, and both are handled explicitly below:

1. *Self-consistency proves nothing.* Because every correspondence is defined
   through ground coordinates, any consistency check routed through ground
   coordinates closes perfectly by construction -- including a three-product
   loop. A naive implementation reports zero residual and calls it high
   confidence. See :func:`loop_closure_residual_m`, which exists to make that
   trap explicit rather than to certify anything.
2. *The dominant error term is unknown to us.* Absolute pointing accuracy for
   Chandrayaan-2 products is not something this project has established, and
   the corner coordinates the transform is fitted from are themselves marked
   UNVERIFIED in :mod:`lunar_reg.ingest.fieldmap`. So the honest total is not a
   number; it is a lower bound plus a named gap. :class:`ConfidenceEstimate`
   refuses to sum terms it does not know.

What *can* be established without external truth is the residual against an
independent estimate of the same transform -- a feature matcher's fit on a pair
where matching actually works (same-modality, moderate scale ratio). That
residual is the accuracy of georeference-derived ground truth, measured rather
than assumed. :func:`validate_against_transform` is that measurement, and
:func:`recommended_validation_plan` says which pairs to run it on.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from enum import Enum

#: Largest source/reference GSD ratio to attempt with a single matcher. One value
#: in one place: this is ``constants.MAX_SAFE_SCALE_RATIO`` under the name that
#: ``overlap.find_cross_sensor_pairs`` imports. PLACEHOLDER to tune -- no paper
#: states a threshold for this pipeline. SIFT tolerates a few octaves;
#: detector-free transformers are trained near 1:1 and degrade sooner. Pairs
#: beyond this should be chained through an intermediate sensor rather than
#: matched directly.
from lunar_reg.constants import MAX_SAFE_SCALE_RATIO as MAX_DIRECT_SCALE_RATIO
from lunar_reg.ingest.overlap import (
    MOON_RADIUS_M,
    FootprintPolygon,
    _strip_closing_duplicate,
    geographic_to_pixel_transform,
    to_fit_plane,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sensor scale table
#
# DOCUMENTED, not measured: these are the nominal ground sample distances from
# the problem statement and the payload documentation, not values read off a
# product label. A real product's GSD varies with orbit altitude and off-nadir
# angle. Once a label is parsed, prefer its own value.
# ---------------------------------------------------------------------------
NOMINAL_GSD_M: dict[str, float] = {
    "OHRC": 0.25,
    "TMC2": 5.0,
    "IIRS": 80.0,
    "LRO_NAC": 0.5,
}


def scale_ratio(sensor_a: str, sensor_b: str) -> float | None:
    """Coarser/finer GSD ratio for two sensors, or ``None`` if either is unknown."""
    a, b = NOMINAL_GSD_M.get(sensor_a), NOMINAL_GSD_M.get(sensor_b)
    if a is None or b is None:
        return None
    return max(a, b) / min(a, b)


def bridge_sensor(sensor_a: str, sensor_b: str) -> str | None:
    """Suggest an intermediate sensor that splits an over-wide scale gap.

    IIRS to OHRC is roughly 320x, which no matcher bridges. TMC-2 sits between
    them at 16x and 20x respectively, both of which are still wide but are at
    least approachable with GSD-aware resampling. Returns the sensor whose
    insertion minimises the larger of the two resulting ratios, or ``None`` when
    the direct ratio is already acceptable or nothing helps.
    """
    direct = scale_ratio(sensor_a, sensor_b)
    if direct is None or direct <= MAX_DIRECT_SCALE_RATIO:
        return None

    best, best_worst = None, direct
    for candidate in NOMINAL_GSD_M:
        if candidate in (sensor_a, sensor_b):
            continue
        first, second = scale_ratio(sensor_a, candidate), scale_ratio(candidate, sensor_b)
        if first is None or second is None:
            continue
        worst = max(first, second)
        if worst < best_worst:
            best, best_worst = candidate, worst
    return best


# ---------------------------------------------------------------------------
# Sampling the overlap
# ---------------------------------------------------------------------------


def point_in_ring(lat: float, lon: float, ring) -> bool:
    """Crossing-number point-in-polygon on a lat/lon ring.

    Written out rather than pulled from a geometry library because the rings
    here are 3-8 vertices and adding a dependency for that is not worth it. The
    ring must not be closed; pass it through
    :func:`~lunar_reg.ingest.overlap._strip_closing_duplicate` first.
    """
    inside = False
    n = len(ring)
    for i in range(n):
        lat_i, lon_i = ring[i]
        lat_j, lon_j = ring[(i - 1) % n]
        if (lat_i > lat) != (lat_j > lat):
            # Longitude of the edge at this latitude.
            span = lat_j - lat_i
            if span == 0:
                continue
            crossing = lon_i + (lat - lat_i) / span * (lon_j - lon_i)
            if lon < crossing:
                inside = not inside
    return inside


def _metres_per_degree(lat_deg: float) -> tuple[float, float]:
    """Local metres per degree of latitude and of longitude on the Moon."""
    per_lat = math.pi * MOON_RADIUS_M / 180.0
    per_lon = per_lat * math.cos(math.radians(lat_deg))
    return per_lat, per_lon


def sample_grid_in_polygon(polygon, spacing_m: float) -> list[tuple[float, float]]:
    """Regular ground grid clipped to a polygon, as ``[(lat, lon), ...]``.

    A regular grid is chosen over random sampling deliberately. The problem
    statement asks for correspondences "maintaining uniform distribution across
    the images", and unlike matcher output -- which clusters on whatever texture
    the scene happens to have -- a grid is uniform by construction. That makes
    this set a useful reference distribution for
    :mod:`lunar_reg.eval.uniformity` even where its absolute accuracy is weak.
    """
    ring = _strip_closing_duplicate(tuple(polygon))
    if len(ring) < 3 or spacing_m <= 0:
        return []

    lats = [p[0] for p in ring]
    lons = [p[1] for p in ring]
    mid_lat = (min(lats) + max(lats)) / 2.0
    per_lat, per_lon = _metres_per_degree(mid_lat)
    if per_lon <= 0:
        # Effectively *at* a pole, where a lat/lon grid has no spacing to speak
        # of. This is now stricter than the overlap machinery, which since the
        # polar-frame change clips polar footprints rather than rejecting them,
        # so a pair can be a usable overlap and still get no grid here.
        # The grid below is still built in lat/lon. Measured on the real OHRC
        # overlap at -85 degrees it recovers the clipped area to within 0.6% at
        # 500 m spacing and 0.1% at 250 m, so it is adequate there -- but it has
        # not been checked any closer to the pole, where it must get worse.
        # TODO: build the grid in the pair's PolarFrame instead.
        return []

    d_lat = spacing_m / per_lat
    d_lon = spacing_m / per_lon

    points: list[tuple[float, float]] = []
    n_lat = int((max(lats) - min(lats)) / d_lat) + 1
    n_lon = int((max(lons) - min(lons)) / d_lon) + 1
    for i in range(n_lat):
        lat = min(lats) + (i + 0.5) * d_lat
        for j in range(n_lon):
            lon = min(lons) + (j + 0.5) * d_lon
            if point_in_ring(lat, lon, ring):
                points.append((lat, lon))
    return points


def project_to_pixels(footprint: FootprintPolygon, points):
    """Map ``[(lat, lon), ...]`` into a product's pixel grid.

    Returns an ``(N, 2)`` array of ``(col, row)``, or ``None`` when the
    footprint has no usable corner-to-pixel transform.

    Points go through :func:`~lunar_reg.ingest.overlap.to_fit_plane` first, so
    a polar footprint's matrix -- fitted in its ``PolarFrame`` -- is applied to
    plane coordinates rather than to raw lat/lon (A051).
    """
    import numpy as np

    matrix = geographic_to_pixel_transform(footprint)
    if matrix is None or not points:
        return None

    plane = to_fit_plane(footprint, points)
    pts = np.array([[b, a] for a, b in plane], dtype=np.float64)
    homogeneous = np.hstack([pts, np.ones((len(pts), 1))]) @ matrix.T
    denom = homogeneous[:, 2:3]
    if not np.all(np.isfinite(denom)) or np.any(np.abs(denom) < 1e-12):
        return None
    return homogeneous[:, :2] / denom


# ---------------------------------------------------------------------------
# Confidence
# ---------------------------------------------------------------------------


class TermSource(str, Enum):
    """Where a confidence term's value came from."""

    #: Derived from quantities we know exactly (pixel size, sampling geometry).
    COMPUTED = "computed"
    #: Observed on real data during this run.
    MEASURED = "measured"
    #: Named, believed to matter, and not established by this project.
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ConfidenceTerm:
    """One contribution to the positional error of a pseudo-correspondence."""

    name: str
    sigma_m: float | None
    source: TermSource
    note: str

    def __str__(self) -> str:
        value = "unknown" if self.sigma_m is None else f"{self.sigma_m:8.2f} m"
        return f"  {self.name:<26} {value:>12}  [{self.source.value}]  {self.note}"


@dataclass
class ConfidenceEstimate:
    """Error budget for a pseudo-ground-truth set.

    Deliberately refuses to produce a single headline number while any term is
    UNKNOWN. Summing over a missing dominant term would produce a confident
    figure that is wrong by however large that term happens to be, which is the
    precise failure this class exists to prevent. What it will give is
    :attr:`lower_bound_sigma_m` -- the root-sum-square of what *is* known,
    explicitly labelled a floor.
    """

    terms: list[ConfidenceTerm] = field(default_factory=list)

    def add(self, name: str, sigma_m: float | None, source: TermSource, note: str) -> None:
        self.terms.append(ConfidenceTerm(name, sigma_m, source, note))

    @property
    def unknown_terms(self) -> list[ConfidenceTerm]:
        return [t for t in self.terms if t.source is TermSource.UNKNOWN]

    @property
    def lower_bound_sigma_m(self) -> float:
        """RSS of the known terms. A floor on the true error, never the total."""
        known = [t.sigma_m for t in self.terms if t.sigma_m is not None]
        return math.sqrt(sum(s * s for s in known))

    @property
    def total_sigma_m(self) -> float | None:
        """The full budget, or ``None`` while any term is unestablished."""
        if self.unknown_terms:
            return None
        return self.lower_bound_sigma_m

    def report(self, gsd_m: float | None = None) -> str:
        lines = ["pseudo-ground-truth error budget (1 sigma, ground distance)", ""]
        lines += [str(t) for t in self.terms]
        lines.append("")

        total = self.total_sigma_m
        if total is not None:
            lines.append(f"total: {total:.2f} m (1 sigma)")
        else:
            lines += [
                f"total: NOT ESTABLISHED. Lower bound {self.lower_bound_sigma_m:.2f} m "
                f"from the known terms alone.",
                "",
                f"{len(self.unknown_terms)} term(s) are unestablished, and at least one of",
                "them is expected to dominate. Do not quote the lower bound as the",
                "accuracy of this ground truth -- it is the accuracy the ground truth",
                "would have if the unknown terms were zero, which they are not:",
            ]
            lines += [f"  - {t.name}: {t.note}" for t in self.unknown_terms]

        if gsd_m:
            reference = total if total is not None else self.lower_bound_sigma_m
            qualifier = "" if total is not None else " (from the lower bound)"
            lines.append(f"       = {reference / gsd_m:.2f} px at {gsd_m:g} m/px{qualifier}")
        return "\n".join(lines)


def estimate_confidence(
    source_sensor: str,
    reference_sensor: str,
    measured_residual_m: float | None = None,
    n_validation_pairs: int = 0,
) -> ConfidenceEstimate:
    """Build the error budget for georeference-derived correspondences.

    ``measured_residual_m`` is the output of :func:`validate_against_transform`
    on same-modality pairs. Supplying it is what converts the dominant term from
    UNKNOWN into MEASURED, and it is the only route to a real total: it folds
    absolute pointing error, corner-ordering error and homography model error
    into one observed number, because all three show up as the same residual.
    """
    estimate = ConfidenceEstimate()

    for role, sensor in (("source", source_sensor), ("reference", reference_sensor)):
        gsd = NOMINAL_GSD_M.get(sensor)
        if gsd is None:
            estimate.add(
                f"{role} quantisation",
                None,
                TermSource.UNKNOWN,
                f"GSD for sensor {sensor!r} is not in NOMINAL_GSD_M",
            )
        else:
            # A ground point is only known to lie somewhere within its pixel.
            # Variance of a uniform distribution over a pixel of side g is
            # g^2/12, so sigma = g/sqrt(12) per axis. Irreducible.
            estimate.add(
                f"{role} quantisation",
                gsd / math.sqrt(12.0),
                TermSource.COMPUTED,
                f"{sensor} at {gsd:g} m/px; uniform-over-pixel, irreducible",
            )

    if measured_residual_m is not None:
        estimate.add(
            "georeference (measured)",
            measured_residual_m,
            TermSource.MEASURED,
            f"observed against matcher-derived transforms on {n_validation_pairs} "
            f"same-modality pair(s)",
        )
    else:
        estimate.add(
            "absolute pointing",
            None,
            TermSource.UNKNOWN,
            "Chandrayaan-2 geolocation accuracy has not been established by this "
            "project and is not carried in the parsed label fields",
        )
        estimate.add(
            "corner-transform model",
            None,
            TermSource.UNKNOWN,
            "geographic_to_pixel_transform fits a homography to four corners; for "
            "a long pushbroom strip that is an approximation of unmeasured size",
        )
        # Resolved 2026-09-05 against a real OHRC label: the corners are named
        # upper_left / upper_right / lower_left / lower_right and
        # footprint_from_row traverses them 1, 2, 4, 3, which reproduces the
        # physically expected 78.89 km^2 strip area. This term is no longer a
        # source of error, so it is recorded as computed-and-zero rather than
        # dropped -- a term that silently disappears from a budget looks like an
        # oversight, and someone will re-add it as UNKNOWN.
        estimate.add(
            "corner ordering",
            0.0,
            TermSource.COMPUTED,
            "verified against a real OHRC label; ring traversal confirmed correct",
        )

    return estimate


# ---------------------------------------------------------------------------
# The pseudo-ground-truth set
# ---------------------------------------------------------------------------


@dataclass
class PseudoGTSet:
    """Georeference-derived correspondences for one overlapping pair."""

    source_id: str | None
    reference_id: str | None
    source_sensor: str | None
    reference_sensor: str | None
    #: ``(N, 2)`` arrays of ``(col, row)`` in each product's pixel grid.
    src_pts: object
    dst_pts: object
    #: The ground points the correspondences were generated from.
    latlon: list[tuple[float, float]]
    spacing_m: float
    confidence: ConfidenceEstimate
    scale_ratio: float | None = None

    def __len__(self) -> int:
        return 0 if self.src_pts is None else int(self.src_pts.shape[0])

    def to_match_result(self):
        """Expose this set through the ordinary matcher interface.

        Lets the evaluation code in :mod:`lunar_reg.eval` treat pseudo ground
        truth exactly like a matcher's output, so the same RMSE and uniformity
        machinery applies. The matcher name carries the ``pseudo-gt`` prefix so
        a result table can never be mistaken for a measured match.
        """
        from lunar_reg.match.base import MatchResult

        if not len(self):
            return MatchResult.empty("pseudo-gt/georeference")
        total = self.confidence.total_sigma_m
        return MatchResult(
            src_pts=self.src_pts,
            dst_pts=self.dst_pts,
            matcher="pseudo-gt/georeference",
            meta={
                "spacing_m": self.spacing_m,
                "sigma_m": total,
                "sigma_is_lower_bound": total is None,
                "sigma_lower_bound_m": self.confidence.lower_bound_sigma_m,
                "unknown_terms": [t.name for t in self.confidence.unknown_terms],
            },
        )


def build_pseudo_gt(
    source: FootprintPolygon,
    reference: FootprintPolygon,
    polygon,
    spacing_m: float | None = None,
    measured_residual_m: float | None = None,
    n_validation_pairs: int = 0,
) -> PseudoGTSet | None:
    """Generate correspondences for one pair from georeferencing alone.

    ``spacing_m`` defaults to eight times the coarser sensor's GSD, which keeps
    neighbouring samples from landing in the same coarse pixel while still
    yielding a dense grid. Returns ``None`` when either footprint has no usable
    corner-to-pixel transform -- a metadata gap, and the caller should count it
    rather than treating it as a matching failure.
    """
    src_sensor = source.sensor or ""
    ref_sensor = reference.sensor or ""

    if spacing_m is None:
        coarse = max(NOMINAL_GSD_M.get(src_sensor, 1.0), NOMINAL_GSD_M.get(ref_sensor, 1.0))
        spacing_m = 8.0 * coarse

    points = sample_grid_in_polygon(polygon, spacing_m)
    if not points:
        return None

    src_pts = project_to_pixels(source, points)
    dst_pts = project_to_pixels(reference, points)
    if src_pts is None or dst_pts is None:
        return None

    # A projected point can land outside the product when the footprint ring and
    # the overlap polygon disagree at the sub-pixel level. Keep only points
    # inside both grids; silently emitting out-of-range pixel coordinates would
    # poison any training set built from this.
    import numpy as np

    keep = np.ones(len(points), dtype=bool)
    for pts, fp in ((src_pts, source), (dst_pts, reference)):
        if fp.samples is None or fp.lines is None:
            continue
        keep &= (
            (pts[:, 0] >= 0)
            & (pts[:, 0] <= fp.samples - 1)
            & (pts[:, 1] >= 0)
            & (pts[:, 1] <= fp.lines - 1)
        )
    n_dropped = int((~keep).sum())
    if n_dropped:
        logger.info(
            "pseudo-gt %s/%s: %d of %d sample(s) projected outside a product grid",
            source.product_id,
            reference.product_id,
            n_dropped,
            len(points),
        )

    return PseudoGTSet(
        source_id=source.product_id,
        reference_id=reference.product_id,
        source_sensor=source.sensor,
        reference_sensor=reference.sensor,
        src_pts=src_pts[keep],
        dst_pts=dst_pts[keep],
        latlon=[p for p, k in zip(points, keep, strict=True) if k],
        spacing_m=spacing_m,
        confidence=estimate_confidence(
            src_sensor, ref_sensor, measured_residual_m, n_validation_pairs
        ),
        scale_ratio=scale_ratio(src_sensor, ref_sensor),
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    """How far pseudo ground truth sits from an independent transform."""

    n_points: int
    rmse_px: float
    median_px: float
    p95_px: float
    rmse_m: float | None
    reference_gsd_m: float | None

    def __str__(self) -> str:
        metres = "" if self.rmse_m is None else f" = {self.rmse_m:.1f} m"
        return (
            f"{self.n_points} point(s): RMSE {self.rmse_px:.2f} px{metres}, "
            f"median {self.median_px:.2f} px, p95 {self.p95_px:.2f} px"
        )


def validate_against_transform(
    gt: PseudoGTSet, homography, reference_gsd_m: float | None = None
) -> ValidationResult | None:
    """Measure pseudo ground truth against an independently estimated transform.

    ``homography`` is a 3x3 source-to-reference matrix obtained *without* using
    georeferencing -- in practice a matcher's RANSAC fit on the same pair. The
    residual between where that transform sends each source point and where the
    georeferencing says it should go is the quantity this whole module needs:
    an observed error for georeference-derived correspondences.

    This only works on pairs a matcher can actually solve, which means same
    modality and a moderate scale ratio. The result is then *transferred* to the
    cross-modal pairs, and that transfer is an assumption -- that geolocation
    error is a property of the spacecraft's pointing rather than of the
    instrument. Reasonable, and not verified. Label it wherever it is used.
    """
    import numpy as np

    if not len(gt) or homography is None:
        return None

    src = np.asarray(gt.src_pts, dtype=np.float64)
    dst = np.asarray(gt.dst_pts, dtype=np.float64)
    homogeneous = np.hstack([src, np.ones((len(src), 1))]) @ np.asarray(homography).T
    denom = homogeneous[:, 2:3]
    if not np.all(np.isfinite(denom)) or np.any(np.abs(denom) < 1e-12):
        return None
    predicted = homogeneous[:, :2] / denom

    errors = np.linalg.norm(predicted - dst, axis=1)
    rmse_px = float(np.sqrt(np.mean(errors**2)))
    return ValidationResult(
        n_points=len(errors),
        rmse_px=rmse_px,
        median_px=float(np.median(errors)),
        p95_px=float(np.percentile(errors, 95)),
        rmse_m=rmse_px * reference_gsd_m if reference_gsd_m else None,
        reference_gsd_m=reference_gsd_m,
    )


def loop_closure_residual_m(footprints, polygon, spacing_m: float) -> float:
    """Round-trip a ground grid through every footprint and back.

    **This is a trap detector, not a confidence measure.** Every pseudo
    correspondence is defined through lat/lon, so a loop routed through lat/lon
    closes to floating-point precision no matter how wrong the georeferencing
    is. A non-zero result here therefore means a numerical or inversion bug; a
    zero result means nothing at all about accuracy.

    It is implemented and exported precisely because "the consistency check
    passed" is the most plausible way this module could be misread as
    trustworthy, and the fastest way to refute that is to let someone run the
    check and read this docstring.
    """
    import numpy as np

    points = sample_grid_in_polygon(polygon, spacing_m)
    if not points or not footprints:
        return 0.0

    worst = 0.0
    ground = np.array([[lon, lat] for lat, lon in points], dtype=np.float64)
    for footprint in footprints:
        matrix = geographic_to_pixel_transform(footprint)
        if matrix is None:
            continue
        forward = np.hstack([ground, np.ones((len(ground), 1))]) @ matrix.T
        pixels = forward[:, :2] / forward[:, 2:3]
        back = np.hstack([pixels, np.ones((len(pixels), 1))]) @ np.linalg.inv(matrix).T
        recovered = back[:, :2] / back[:, 2:3]

        mid_lat = float(np.mean(ground[:, 1]))
        per_lat, per_lon = _metres_per_degree(mid_lat)
        d_lon = (recovered[:, 0] - ground[:, 0]) * per_lon
        d_lat = (recovered[:, 1] - ground[:, 1]) * per_lat
        worst = max(worst, float(np.max(np.hypot(d_lon, d_lat))))
    return worst


def recommended_validation_plan() -> str:
    """Which pairs to run :func:`validate_against_transform` on, and why."""
    return "\n".join(
        [
            "To replace the UNKNOWN terms with a measured number, run the validation on",
            "pairs where a matcher genuinely works, then transfer the residual:",
            "",
            "  1. TMC2 x TMC2   ratio 1.0   same instrument, same modality. Isolates",
            "                               pointing error with nothing else in the way.",
            "  2. OHRC x TMC2   ratio 20    same modality, wide scale gap. The difference",
            "                               from (1) is the scale-and-model contribution.",
            "  3. TMC2 x LRO_NAC ratio 10   cross-mission. LRO NAC geolocation is the",
            "                               better-controlled of the two, so this leans",
            "                               closest to an absolute check.",
            "",
            "IIRS pairs cannot appear in this list: if a matcher could solve them, the",
            "pseudo ground truth would not be needed. Their confidence is inherited from",
            "(1)-(3) by assumption, not measured.",
        ]
    )


__all__ = [
    "MAX_DIRECT_SCALE_RATIO",
    "NOMINAL_GSD_M",
    "ConfidenceEstimate",
    "ConfidenceTerm",
    "PseudoGTSet",
    "TermSource",
    "ValidationResult",
    "bridge_sensor",
    "build_pseudo_gt",
    "estimate_confidence",
    "loop_closure_residual_m",
    "point_in_ring",
    "project_to_pixels",
    "recommended_validation_plan",
    "sample_grid_in_polygon",
    "scale_ratio",
    "validate_against_transform",
]
