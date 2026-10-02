"""One site runner: catalog -> pair preparation -> coarse pass -> prior -> register -> store.

``Phase_1/LLD/site_runner.md``. This is the library form of the matching logic
that used to live in ``scripts/run_vikram.py``; the script is now a thin CLI
around :func:`run_site`.

For every PRESENT Chandrayaan-2 product of the requested instruments (OHRC,
TMC-2, IIRS) and levels, the runner

1. optionally runs a **coarse pass** (low resolution, wide margin, one matcher)
   to find where the source window really sits in the reference;
2. chooses the **search prior** for the fine pass: the coarse result, else the
   measured prior shift (only for instruments in
   ``SiteConfig.prior_shift_instruments``, DECISIONS G38), else the label
   corners or geometry grid as prepared;
3. prepares the **fine** window pair at ``gsd_m``
   (:func:`lunar_reg.pairs.prepare_window_pair`);
4. registers it with every matcher (:func:`lunar_reg.pipeline.register_pair`),
   saves each OK result at once, and writes an optional registered GeoTIFF.

Nothing is skipped silently: an instrument that is not PRESENT is counted in
:meth:`SiteReport.report` (G24); a pair that cannot be prepared keeps its
:class:`~lunar_reg.pairs.PrepStatus`; every failed registration is appended to
``failures.parquet``; and ``run_record.json`` (C15) holds counts per
``RunStatus``, per ``PrepStatus`` and one ``instrument_<INSTRUMENT>_<status>``
key per requested instrument. The library logs one summary line; the caller
prints :meth:`SiteReport.report` on every run.

:func:`compute_exp1_gate` turns the stored results of the three 2023 strips into
the C20 exp-1 gate document.

Test seam (LLD §1): ``build_catalog``, ``georeference_from_label``,
``prepare_window_pair``, ``register_pair`` and ``sun_from_label`` are imported by
name at module level and called through this module's attributes, so tests can
monkeypatch them here.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import math
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from lunar_reg.ingest.catalog import InstrumentStatus, ProductCatalog, build_catalog
from lunar_reg.ingest.lro import GeoReference, georeference_from_label
from lunar_reg.ingest.pds4 import read_label
from lunar_reg.ingest.sun import FRAME_NORTH, SunGeometry, sun_from_label
from lunar_reg.pairs import (
    PrepDiagnostics,
    PrepStatus,
    PriorSource,
    WindowPair,
    prepare_window_pair,
)
from lunar_reg.pipeline import BatchReport, PipelineConfig, RunOutcome, RunStatus, register_pair
from lunar_reg.provenance import ValueSource

logger = logging.getLogger(__name__)

__all__ = [
    "CH2_INSTRUMENTS",
    "DEFAULT_PRIOR_SHIFT_M",
    "DEFAULT_PRIOR_SHIFT_SOURCE",
    "EXP1_MIN_INLIERS",
    "EXP1_MIN_U_SCORE",
    "EXP1_RULE",
    "LABEL_AZIMUTH_CONVENTIONS",
    "ProductRun",
    "SiteConfig",
    "SiteReport",
    "compute_exp1_gate",
    "run_site",
]

#: Instruments the runner can register (the Chandrayaan-2 members of C09 INSTRUMENTS).
CH2_INSTRUMENTS = ("OHRC", "TMC2", "IIRS")

#: Shift (east, south) in metres of the reference crop from the label prior,
#: measured on OHRC 20240425T1406019344 from its coarse (8 m/px) and fine
#: (4 m/px) registrations (``scripts/run_vikram.py`` DEFAULT_PRIOR_SHIFT,
#: 2026-09-28). Used only as the fallback search centre of the instruments in
#: ``SiteConfig.prior_shift_instruments`` (G38).
DEFAULT_PRIOR_SHIFT_M = (556.0, -2888.0)
DEFAULT_PRIOR_SHIFT_SOURCE = ValueSource.MEASURED

#: The four ways an ISRO label azimuth ``a`` may relate to clockwise-from-north
#: (``Phase_1/LLD/sun_geometry.md`` §2 step 4); the convention that applies is
#: chosen by ``scripts/fit_reference_sun.py --label-convention``.
LABEL_AZIMUTH_CONVENTIONS = {
    "as_is": lambda a: a % 360.0,
    "plus_180": lambda a: (a + 180.0) % 360.0,
    "mirror": lambda a: (360.0 - a) % 360.0,
    "mirror_plus_180": lambda a: (180.0 - a) % 360.0,
}

#: C20 targets: a strip passes with at least this many final inliers ...
EXP1_MIN_INLIERS = 20
#: ... and at least this uniformity score (both thresholds are the C20 rule,
#: chosen targets rather than measurements).
EXP1_MIN_U_SCORE = 0.7
EXP1_THRESHOLDS_SOURCE = ValueSource.INFERRED
#: C20 ``rule`` text, verbatim.
EXP1_RULE = (
    "SKIP_1B iff every 2023 strip has >=1 matcher with n_inliers>=20 and u_score>=0.7 "
    "and agreement passes (<1 px pre-ECC, >=2 matchers)"
)

#: The provenance text every real-data result carries (from scripts/run_vikram.py).
RESULT_NOTES = (
    "Real data. No ground truth: RMSE is the fit's self-residual. "
    "label_offset_m compares the matched transform with the "
    "label-corner + corrected-NAC-georeference prior."
)

_TAG = re.compile(r"\d{8}T\d{10}", re.IGNORECASE)
_SAMPLE_MAX = 200


# ---------------------------------------------------------------------------
# types (LLD §1)
# ---------------------------------------------------------------------------


@dataclass
class SiteConfig:
    site: str = "vikram"
    reference_label: Path = Path(
        "data/raw/reference/lro_nac_vikram/NAC_DTM_VIKRAMSITE1_M1442997156_100CM.xml"
    )
    reference_sensor: str = "LRO_NAC_ORTHO"
    raw_root: Path = Path("data/raw")
    instruments: tuple[str, ...] = ("OHRC", "TMC2", "IIRS")
    only: str = ""  # substring filter on product id
    levels: tuple[str, ...] = ("raw", "calibrated")
    gsd_m: float = 4.0
    window_m: float = 3000.0
    margin_m: float = 1000.0
    matchers: tuple[str, ...] = ("sift", "akaze", "asift", "lightglue")
    model: str = "homography"
    min_inliers: int = 8
    ransac_threshold_px: float = 3.0
    preprocess: str = "none"
    ecc_prefilter: str = "none"
    coarse: bool = True
    coarse_gsd_m: float = 8.0
    coarse_margin_m: float = 4000.0
    coarse_matcher: str = "lightglue"
    # MEASURED on the 2024 OHRC strip (DEFAULT_PRIOR_SHIFT_M / _SOURCE)
    prior_shift_m: tuple[float, float] | None = DEFAULT_PRIOR_SHIFT_M
    # G38: the shift applies only to these instruments
    prior_shift_instruments: tuple[str, ...] = ("OHRC",)
    band_reduction: str = "pca"  # IIRS
    results_root: Path = Path("data/processed/results")
    out_dir: Path = Path("data/processed/vikram/runs/latest")
    save_registered: bool = True
    overwrite: bool = False
    dry_run: bool = False
    reference_sun_json: Path | None = Path("data/processed/vikram/reference_sun/reference_sun.json")
    label_convention_json: Path | None = Path(
        "data/processed/vikram/reference_sun/label_convention.json"
    )


@dataclass
class ProductRun:
    product_id: str
    instrument: str
    level: str
    prep: PrepStatus
    prep_detail: str
    coarse_note: str
    search_prior: str
    outcomes: list[RunOutcome]

    def as_dict(self) -> dict:
        """JSON-safe summary (no arrays)."""
        rows = []
        for o in self.outcomes:
            row = {
                "pair_id": o.pair_id,
                "matcher": o.extra.get("matcher", ""),
                "status": o.status.value,
                "detail": o.detail[:_SAMPLE_MAX],
            }
            if o.ok:
                row["n_inliers"] = int(o.result.n_inliers)
                row["u_score"] = _u_score(o.result)
            rows.append(row)
        return {"product_id": self.product_id, "instrument": self.instrument,
                "level": self.level, "prep": self.prep.value, "prep_detail": self.prep_detail,
                "coarse_note": self.coarse_note, "search_prior": self.search_prior,
                "outcomes": rows}  # fmt: skip


@dataclass
class SiteReport:
    catalog: ProductCatalog
    runs: list[ProductRun]
    batch: BatchReport
    run_record_path: Path | None
    # additions beyond LLD §1, all with defaults (see Phase_1/QUESTIONS.md Q-P1.16-1)
    instruments: tuple[str, ...] = ()
    prep: PrepDiagnostics = field(default_factory=PrepDiagnostics)
    saved: list[str] = field(default_factory=list)
    not_saved: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    dry_run: bool = False
    #: ``"<pair_id>: <error>"`` per failed registered-GeoTIFF write (result still saved)
    geotiff_failures: list[str] = field(default_factory=list)

    @property
    def any_ok(self) -> bool:
        return any(o.ok for o in self.batch.outcomes)

    def report(self) -> str:
        """Instrument statuses, prep outcomes (counts + sample), per-product lines, batch report."""
        lines = [
            f"site runner: {len(self.runs)} product(s) selected"
            + (" (dry run: prepared only, no matching)" if self.dry_run else "")
        ]
        lines.append("instruments:")
        for inst in self.instruments:
            status = self.catalog.status.get(inst)
            if status is InstrumentStatus.PRESENT:
                n_all = len(self.catalog.products(inst))
                n_sel = sum(r.instrument == inst for r in self.runs)
                lines.append(f"  {inst}: present, {n_all} data product(s), {n_sel} selected")
            else:
                value = "unknown" if status is None else status.value
                lines.append(f"  {inst}: {value.upper()} -- not run (G24 skip-if-absent)")
        lines.append(self.prep.report())
        lines.append("products:")
        for run in self.runs:
            parts = [f"prep {run.prep.value}"]
            if run.prep.is_failure or run.prep_detail:
                parts[-1] += f" ({run.prep_detail[:120]})"
            parts.append(f"coarse: {run.coarse_note}")
            parts.append(f"prior: {run.search_prior}")
            for o in run.outcomes:
                matcher = o.extra.get("matcher", "?")
                if o.ok:
                    parts.append(
                        f"{matcher} ok {o.result.n_inliers} inliers u={_u_score(o.result):.2f}"
                    )
                else:
                    parts.append(f"{matcher} {o.status.value}")
            lines.append(f"  {run.instrument} {run.level} {run.product_id}: " + "; ".join(parts))
        if not self.runs:
            lines.append("  (none)")
        if not self.dry_run:
            line = f"store: {len(self.saved)} saved, {len(self.not_saved)} NOT saved"
            if self.not_saved:
                line += f" (already stored; pass --overwrite), e.g. {self.not_saved[0]}"
            lines.append(line)
            if self.geotiff_failures:
                lines.append(
                    f"registered GeoTIFF: {len(self.geotiff_failures)} write(s) FAILED "
                    f"(results still saved), e.g. {self.geotiff_failures[0]}"
                )
            lines.append(self.batch.report())
        lines.extend(self.notes)
        if self.run_record_path is not None:
            lines.append(f"run record: {self.run_record_path}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _u_score(result) -> float:
    value = result.uniformity.get("score") if result is not None else None
    return float(value) if value is not None else float("nan")


def _tag(product_id: str) -> str:
    """The ``YYYYMMDDTHHMMSSffff`` token, else the id made pair-id safe."""
    match = _TAG.search(product_id)
    if match:
        return match.group(0)
    return re.sub(r"[^A-Za-z0-9._]", "_", product_id) or "product"


def _sensor(instrument: str, level: str) -> str:
    if instrument == "OHRC" and level == "raw":
        return "CH2_OHRC_RAW"
    if instrument == "OHRC" and level == "calibrated":
        return "CH2_OHRC_CAL"
    return f"CH2_{instrument}_{level.upper()}"


def _variant(model: str, preprocess: str) -> str:
    out = "" if model == "homography" else f"_{model}"
    if preprocess != "none":
        out += f"_pp-{preprocess}"
    return out


def _as3x3(matrix) -> np.ndarray:
    m = np.asarray(matrix, dtype=np.float64)
    if m.shape == (2, 3):
        m = np.vstack([m, [0.0, 0.0, 1.0]])
    return m


def _map_point(matrix, x: float, y: float) -> tuple[float, float]:
    out = cv2.perspectiveTransform(np.array([[[x, y]]], np.float64), _as3x3(matrix))[0, 0]
    return float(out[0]), float(out[1])


def _centre_offset_m(found, prior, shape, gsd_m: float) -> float:
    """Distance in metres between where ``found`` and ``prior`` put the source centre.

    Same arithmetic as the former ``run_vikram.centre_offset_m``.
    """
    h, w = shape[:2]
    a = _map_point(found, w / 2, h / 2)
    b = _map_point(prior, w / 2, h / 2)
    return float(math.hypot(a[0] - b[0], a[1] - b[1]) * gsd_m)


def _coarse_shift_m(pair: WindowPair, transform, geo: GeoReference) -> tuple[float, float]:
    """(east, south) metres from the prior window centre to the found one (LLD §2 step 4a)."""
    h, w = pair.source.shape[:2]
    found = _map_point(transform, w / 2, h / 2)
    prior = _map_point(pair.prior, w / 2, h / 2)
    to_native = np.asarray(pair.reference_to_native, dtype=np.float64)
    fx, fy = _map_point(to_native, *found)
    px, py = _map_point(to_native, *prior)
    return (fx - px) * float(geo.pixel_size_x_m), (fy - py) * float(geo.pixel_size_y_m)


def _load_json_key(path: Path | None, key: str, what: str):
    """``json.load(path)[key]`` when the file exists, else None (LLD §2 step 3)."""
    if path is None or not Path(path).exists():
        return None
    try:
        return json.loads(Path(path).read_text())[key]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        # A file that exists but cannot be used is a setup error, not a per-pair outcome.
        raise ValueError(f"{what} {path}: cannot read key {key!r}: {exc}") from exc


def _source_sun(entry, convention: str | None) -> SunGeometry:
    """Label sun of one product; OHRC azimuths converted to north_clockwise with a convention."""
    try:
        product = read_label(entry.label_path)
        sun = sun_from_label(product)
    except (OSError, ValueError, KeyError) as exc:
        note = f"label unreadable: {exc}"[:_SAMPLE_MAX]
        return SunGeometry(
            None, None, ValueSource.UNKNOWN, ValueSource.UNKNOWN, "label_unverified", note=note
        )
    if convention is None or entry.instrument != "OHRC" or sun.azimuth_deg is None:
        return sun
    convert = LABEL_AZIMUTH_CONVENTIONS.get(convention)
    if convert is None:
        logger.warning("unknown label azimuth convention %r; label azimuth left as is", convention)
        return sun
    return SunGeometry(
        azimuth_deg=float(convert(float(sun.azimuth_deg))),
        elevation_deg=sun.elevation_deg,
        azimuth_source=ValueSource.COMPUTED,
        elevation_source=sun.elevation_source,
        azimuth_frame=FRAME_NORTH,
        note=f"{sun.note}; label azimuth {sun.azimuth_deg:g} converted with convention "
        f"{convention} (ValueSource.COMPUTED)",
    )


def _sun_extra(src_sun: SunGeometry, ref_sun: dict | None) -> dict:
    extra: dict = {}
    if src_sun.azimuth_deg is not None:
        extra["source_sun_azimuth"] = float(src_sun.azimuth_deg)
    if src_sun.elevation_deg is not None:
        extra["source_sun_elevation"] = float(src_sun.elevation_deg)
    # one ValueSource per numeric value (a label convention changes the azimuth only)
    extra["source_sun_azimuth_source"] = src_sun.azimuth_source.value
    extra["source_sun_elevation_source"] = src_sun.elevation_source.value
    extra["source_sun_frame"] = src_sun.azimuth_frame
    if ref_sun:
        if ref_sun.get("azimuth_deg") is not None:
            extra["reference_sun_azimuth"] = float(ref_sun["azimuth_deg"])
        if ref_sun.get("elevation_deg") is not None:
            extra["reference_sun_elevation"] = float(ref_sun["elevation_deg"])
        # C04 reserved key: the azimuth's source; per-component keys beside it
        extra["reference_sun_source"] = str(ref_sun.get("azimuth_source", "unknown"))
        extra["reference_sun_azimuth_source"] = str(ref_sun.get("azimuth_source", "unknown"))
        extra["reference_sun_elevation_source"] = str(ref_sun.get("elevation_source", "unknown"))
        extra["reference_sun_frame"] = str(ref_sun.get("azimuth_frame", "unknown"))
    return extra


def _sun_args(src_sun: SunGeometry, ref_sun: dict | None):
    """``(source_sun, reference_sun)`` for register_pair, only when both share a frame."""
    if not ref_sun or src_sun.as_tuple() is None:
        return None, None
    if ref_sun.get("azimuth_deg") is None or ref_sun.get("elevation_deg") is None:
        return None, None
    if ref_sun.get("azimuth_frame") != src_sun.azimuth_frame:
        return None, None
    return src_sun.as_tuple(), (float(ref_sun["azimuth_deg"]), float(ref_sun["elevation_deg"]))


def _params(cfg: SiteConfig) -> dict:
    out = {}
    for f in dataclasses.fields(cfg):
        value = getattr(cfg, f.name)
        if isinstance(value, Path):
            value = str(value)
        elif isinstance(value, tuple):
            value = list(value)
        out[f.name] = value
    return out


# ---------------------------------------------------------------------------
# run_site (LLD §2)
# ---------------------------------------------------------------------------


@dataclass
class _Tally:
    """Per-run bookkeeping shared by the product loop."""

    batch: BatchReport = field(default_factory=BatchReport)
    prep: PrepDiagnostics = field(default_factory=PrepDiagnostics)
    saved: list[str] = field(default_factory=list)
    not_saved: list[str] = field(default_factory=list)
    artefacts: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    geotiff_failures: list[str] = field(default_factory=list)

    def bump(self, key: str) -> None:
        self.counts[key] = self.counts.get(key, 0) + 1


def _coarse(entry, cfg: SiteConfig, geo: GeoReference, tag: str):
    """Coarse pass (LLD §2 step 4a): ``(shift or None, note)``."""
    prep = prepare_window_pair(
        entry.label_path, cfg.reference_label, geo,
        gsd_m=cfg.coarse_gsd_m, window_m=cfg.window_m, margin_m=cfg.coarse_margin_m,
        geometry_grid_path=entry.geometry_grid_path, band_reduction=cfg.band_reduction,
    )  # fmt: skip
    if prep.status is not PrepStatus.OK:
        return None, f"coarse pass failed (prep {prep.status.value})"
    pair = prep.pair
    outcome = register_pair(
        pair.source, pair.reference, f"coarse_{tag}",
        PipelineConfig(matcher=cfg.coarse_matcher, use_ecc=False, n_bootstrap=0,
                       min_inliers=cfg.min_inliers, gsd_m=cfg.coarse_gsd_m),
        source_valid=pair.source_valid, reference_valid=pair.reference_valid,
    )  # fmt: skip
    if not outcome.ok:
        # A112: say only that it failed, not which prior the fine pass used.
        return None, f"coarse pass failed ({outcome.status.value})"
    e, s = _coarse_shift_m(pair, outcome.result.transform, geo)
    note = (
        f"{cfg.coarse_gsd_m:g} m/px {cfg.coarse_matcher}, {outcome.result.n_inliers} inliers, "
        f"shift {e:+.3f},{s:+.3f} m (E,S)"
    )
    return (e, s), note


def _write_preview(path: Path, image: np.ndarray) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    return bool(cv2.imwrite(str(path), image))


def _run_product(entry, cfg: SiteConfig, geo: GeoReference, ref_sun: dict | None,
                 convention: str | None, tally: _Tally) -> ProductRun:  # fmt: skip
    tag = _tag(entry.product_id)
    sensor = _sensor(entry.instrument, entry.level)

    # a. coarse pass
    coarse_shift = None
    if cfg.dry_run:
        coarse_note = "not run (dry run)"
    elif cfg.coarse:
        coarse_shift, coarse_note = _coarse(entry, cfg, geo, tag)
        tally.bump("coarse_ok" if coarse_shift is not None else "coarse_failed")
    else:
        coarse_note = "not run (disabled)"

    # b. prior
    shift, search_prior = (0.0, 0.0), None
    if coarse_shift is not None:
        shift, search_prior = coarse_shift, "coarse pass"
    elif cfg.prior_shift_m is not None and entry.instrument in cfg.prior_shift_instruments:
        e, s = (float(v) for v in cfg.prior_shift_m)
        shift, search_prior = (e, s), f"prior shift {e:g},{s:g} m (E,S)"

    # c. fine prep
    prep = prepare_window_pair(
        entry.label_path, cfg.reference_label, geo,
        gsd_m=cfg.gsd_m, window_m=cfg.window_m, margin_m=cfg.margin_m, shift_m=shift,
        geometry_grid_path=entry.geometry_grid_path, band_reduction=cfg.band_reduction,
    )  # fmt: skip
    tally.prep.record(prep, entry.product_id)
    if search_prior is None:
        grid = prep.pair is not None and prep.pair.prior_source is PriorSource.GEOMETRY_GRID
        search_prior = "geometry grid" if grid else "label corners"
    run = ProductRun(entry.product_id, entry.instrument, entry.level, prep.status, prep.detail,
                     coarse_note, search_prior, [])  # fmt: skip
    if prep.status is not PrepStatus.OK:
        return run
    pair = prep.pair
    if not run.prep_detail:
        (sh, sw), (rh, rw) = pair.source.shape[:2], pair.reference.shape[:2]
        run.prep_detail = (
            f"source {sw}x{sh}, reference {rw}x{rh} at {pair.gsd_m:g} m/px, reference valid "
            f"{float(np.mean(pair.reference_valid)):.0%}, prior from {pair.prior_source.value}"
        )

    # d. dry run: previews only
    if cfg.dry_run:
        failed = []
        for side, image in (("src", pair.source), ("ref", pair.reference)):
            path = Path(cfg.out_dir) / "preview" / f"{sensor}_{tag}_{side}.png"
            if _write_preview(path, image):
                tally.artefacts.append(str(path))
            else:
                failed.append(str(path))
                tally.bump("preview_write_failed")
        if failed:
            run.prep_detail = (run.prep_detail + "; " if run.prep_detail else "") + (
                f"preview write failed: {', '.join(failed)}"
            )
        return run

    # e. register with every matcher
    src_sun = _source_sun(entry, convention)
    source_sun, reference_sun = _sun_args(src_sun, ref_sun)
    sun_extra = _sun_extra(src_sun, ref_sun)
    extra_base = {
        **pair.geometry_extra(),
        "site": cfg.site,
        "level": entry.level,
        "window_m": float(cfg.window_m),
        "margin_m": float(cfg.margin_m),
        "coarse_pass": coarse_note,
        "search_prior": search_prior,
        **sun_extra,
    }
    variant = _variant(cfg.model, cfg.preprocess)
    for matcher in cfg.matchers:
        pair_id = f"{sensor}_{tag}-{cfg.reference_sensor}_{matcher}{variant}"
        config = PipelineConfig(
            matcher=matcher, model=cfg.model, min_inliers=cfg.min_inliers,
            ransac_threshold_px=cfg.ransac_threshold_px, gsd_m=cfg.gsd_m,
            preprocess=cfg.preprocess, ecc_prefilter=cfg.ecc_prefilter, extra=dict(extra_base),
        )  # fmt: skip
        outcome = register_pair(
            pair.source, pair.reference, pair_id, config,
            source_id=pair.source_id, reference_id=pair.reference_id,
            source_sensor=sensor, reference_sensor=cfg.reference_sensor,
            source_sun=source_sun, reference_sun=reference_sun, synthetic=False,
            notes=RESULT_NOTES,
            source_valid=pair.source_valid, reference_valid=pair.reference_valid,
        )  # fmt: skip
        tally.batch.outcomes.append(outcome)
        run.outcomes.append(outcome)
        if outcome.ok:
            _keep(outcome, pair, pair_id, matcher, cfg, geo, search_prior, sun_extra, tally)
    return run


def _keep(outcome: RunOutcome, pair: WindowPair, pair_id: str, matcher: str, cfg: SiteConfig,
          geo: GeoReference, search_prior: str, sun_extra: dict,
          tally: _Tally) -> None:  # fmt: skip
    """LLD §2 step 4f: sun keys, label offset, registered GeoTIFF, immediate save."""
    from lunar_reg.align.warp import save_registered_geotiff
    from lunar_reg.results import save_results

    r = outcome.result
    # register_pair writes the C04 sun keys from its source_sun/reference_sun
    # arguments (None when the frames differ); the stored record keeps both suns
    # as the runner read them (LLD §2 step 4e, A113), with their frames.
    r.extra.update(sun_extra)
    r.extra["label_offset_m"] = _centre_offset_m(r.transform, pair.prior, pair.source.shape,
                                                 cfg.gsd_m)  # fmt: skip
    r.extra["label_offset_source"] = ValueSource.COMPUTED.value
    npz = Path(cfg.results_root) / "pairs" / f"{pair_id}.npz"
    if not cfg.overwrite and npz.exists():
        # Not saved: leave the stored result's GeoTIFF untouched as well.
        tally.not_saved.append(pair_id)
        return
    if cfg.save_registered:
        r0, c0 = pair.reference_window[0], pair.reference_window[1]
        path = Path(cfg.out_dir) / "registered" / f"{pair_id}.tif"
        try:
            out = save_registered_geotiff(
                pair.source, np.asarray(r.transform), pair.reference.shape[:2], path,
                crs=geo.crs_proj4,
                origin_xy=(geo.x0_m + c0 * geo.pixel_size_x_m, geo.y0_m - r0 * geo.pixel_size_y_m),
                pixel_size=cfg.gsd_m,
                tags={"pair_id": pair_id, "source": r.source_id, "reference": r.reference_id,
                      "matcher": matcher, "model": cfg.model, "min_inliers": cfg.min_inliers,
                      "preprocess": cfg.preprocess, "search_prior": search_prior,
                      "crop_geometry_source": "recorded",
                      "georeference": f"reference label georeference ({geo.source.value})"},
            )  # fmt: skip
            r.extra["registered_geotiff"] = str(out["path"])
            tally.artefacts.append(str(out["path"]))
        except Exception as exc:  # noqa: BLE001 - GDAL/rasterio raise many types on a bad write
            r.extra["registered_geotiff_error"] = f"{type(exc).__name__}: {exc}"[:_SAMPLE_MAX]
            tally.bump("geotiff_write_failed")
            tally.geotiff_failures.append(f"{pair_id}: {r.extra['registered_geotiff_error']}")
    # Saved now, one by one: a crash on a later pair loses nothing.
    try:
        save_results([r], cfg.results_root, overwrite=cfg.overwrite)
    except FileExistsError:
        tally.not_saved.append(pair_id)
        return
    tally.saved.append(pair_id)
    tally.artefacts.append(str(npz))


def run_site(cfg: SiteConfig) -> SiteReport:
    """Run every selected product of a site (LLD §2).

    Prints nothing; the caller prints :meth:`SiteReport.report` on every run.
    """
    from lunar_reg.results import save_failures
    from lunar_reg.runrecord import finish_run, start_run, write_run_record

    unknown = [i for i in cfg.instruments if i not in CH2_INSTRUMENTS]
    if unknown:
        raise ValueError(f"instruments must be among {CH2_INSTRUMENTS}, got {unknown}")
    record = start_run(list(sys.argv) or ["run_site"], _params(cfg))

    # 1. catalog
    catalog = build_catalog(cfg.raw_root)
    # 2. reference georeference: LabelGeoreferenceError propagates (setup error)
    geo = georeference_from_label(cfg.reference_label)
    # 3. reference sun and label convention
    ref_sun = _load_json_key(cfg.reference_sun_json, "sun", "reference sun JSON")
    convention = _load_json_key(cfg.label_convention_json, "convention", "label convention JSON")

    tally = _Tally()
    runs: list[ProductRun] = []
    notes: list[str] = []
    for inst in cfg.instruments:
        status = catalog.status.get(inst)
        tally.counts[f"instrument_{inst}_{status.value if status else 'unknown'}"] = 1
        if status is not InstrumentStatus.PRESENT:
            notes.append(f"{inst}: {status.value if status else 'unknown'}, not run")
            continue
        for entry in catalog.products(inst):
            if entry.level not in cfg.levels or cfg.only not in entry.product_id:
                continue
            runs.append(_run_product(entry, cfg, geo, ref_sun, convention, tally))

    # 5. persist failures, then the run record
    save_failures(tally.batch.failures, cfg.results_root)
    products_path = Path(cfg.out_dir) / "products.json"
    products_path.parent.mkdir(parents=True, exist_ok=True)
    products_path.write_text(json.dumps([r.as_dict() for r in runs], indent=2))
    counts = dict(tally.counts)
    for s in RunStatus:
        counts[s.value] = sum(o.status is s for o in tally.batch.outcomes)
    for s in PrepStatus:
        counts[f"prep_{s.value}"] = int(tally.prep.counts.get(s.value, 0))
    counts["products"] = len(runs)
    counts["saved"] = len(tally.saved)
    counts["not_saved_exists"] = len(tally.not_saved)
    sun_note = (
        f"reference sun: {'none' if ref_sun is None else ref_sun.get('azimuth_frame')}; "
        f"label azimuth convention: {convention or 'none (label azimuth unverified)'}"
    )
    record = dataclasses.replace(
        record, notes="; ".join(x for x in (record.notes, *notes, sun_note) if x)
    )
    record = finish_run(record, counts, [*tally.artefacts, str(products_path)])
    rr_path = write_run_record(record, cfg.out_dir)

    n_ok = counts[RunStatus.OK.value]
    logger.info(
        "run_site %s: %d product(s), %d prepared, %d registration(s), %d ok, %d saved%s",
        cfg.site, len(runs), tally.prep.counts.get("ok", 0), len(tally.batch.outcomes), n_ok,
        len(tally.saved), " (dry run)" if cfg.dry_run else "",
    )  # fmt: skip
    return SiteReport(
        catalog=catalog, runs=runs, batch=tally.batch, run_record_path=rr_path,
        instruments=tuple(cfg.instruments), prep=tally.prep, saved=tally.saved,
        not_saved=tally.not_saved, notes=[*notes, sun_note], dry_run=cfg.dry_run,
        geotiff_failures=tally.geotiff_failures,
    )  # fmt: skip


# ---------------------------------------------------------------------------
# compute_exp1_gate (LLD §3, C20)
# ---------------------------------------------------------------------------


def _pair_variant(r) -> str:
    """The ``{variant}`` suffix of a site-runner pair id, or the whole id when it is not one."""
    head = f"-{r.reference_sensor}_{r.matcher}"
    i = r.pair_id.find(head)
    return r.pair_id if i < 0 else r.pair_id[i + len(head) :]


def _finite_or_none(value) -> float | None:
    if value is None:
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def _best(results: list):
    """LLD §3: most inliers among ``u_score >= 0.7``, else most inliers overall."""
    uniform = [r for r in results if _u_score(r) >= EXP1_MIN_U_SCORE]
    return max(uniform or results, key=lambda r: r.n_inliers)


def _group_key(r) -> tuple:
    """Results whose transforms are comparable: one source/reference pair, one variant."""
    return (r.source_id, r.reference_id, r.source_sensor, r.reference_sensor, _pair_variant(r))


def _evaluate_group(results: list, threshold_px: float, problems: dict) -> dict:
    """The §3 test on one comparable group (one result per matcher, Q-P1.12-1)."""
    from lunar_reg.eval.agreement import agreement_for_stored

    best = _best(results)
    group: dict[str, object] = {}
    for r in results:  # sorted by pair_id: the first result of each matcher
        group.setdefault(r.matcher, r)
    status, agreement_px, agree_ok = "ok", None, False
    try:
        agreement = agreement_for_stored(list(group.values()), threshold_px=threshold_px)
        agreement_px = _finite_or_none(agreement.max_disagreement_px)
        agree_ok = bool(agreement.passes)
    except ValueError as exc:
        status = "agreement_failed"
        problems["agreement_failed"] = problems.get("agreement_failed", 0) + 1
        problems.setdefault("first_agreement_error", f"{best.pair_id}: {exc}"[:_SAMPLE_MAX])
    u = _u_score(best)
    passes = bool(best.n_inliers >= EXP1_MIN_INLIERS and u >= EXP1_MIN_U_SCORE and agree_ok)
    return {"best": best, "status": status, "agreement_px": agreement_px, "passes": passes}


def _strip(tag: str, results: list, threshold_px: float, n_unloaded: int = 0,
           problems: dict | None = None) -> dict:  # fmt: skip
    """C20 strip row.

    The results of one tag may span several comparable groups (raw and
    calibrated sensors from exp-1a / exp-1b, pair-id variants), and agreement
    can only be computed inside one group (Q-P1.12-1). Each group is tested
    with the §3 rule; the strip passes when any group passes (C20: ">=1 matcher
    with ... and agreement passes"). The row reports the passing group with
    the most inliers, else the group of the strip-wide §3 best.
    """
    problems = {} if problems is None else problems
    if not results:
        status = "load_failed" if n_unloaded else "no_result"
        return {"tag": tag, "best_matcher": None, "status": status, "n_inliers": 0,
                "u_score": None, "agreement_px": None, "passes_targets": False}  # fmt: skip
    results = sorted(results, key=lambda r: r.pair_id)
    groups: dict[tuple, list] = {}
    for r in results:
        groups.setdefault(_group_key(r), []).append(r)
    evaluated = {key: _evaluate_group(rs, threshold_px, problems) for key, rs in groups.items()}
    passing = [e for e in evaluated.values() if e["passes"]]
    if passing:
        chosen = max(passing, key=lambda e: e["best"].n_inliers)
    else:
        chosen = evaluated[_group_key(_best(results))]
    best = chosen["best"]
    status = chosen["status"]
    if n_unloaded:
        status += f"; {n_unloaded} stored record(s) not loaded"
    return {"tag": tag, "best_matcher": best.matcher, "status": status,
            "n_inliers": int(best.n_inliers), "u_score": _finite_or_none(_u_score(best)),
            "agreement_px": chosen["agreement_px"], "passes_targets": chosen["passes"]}  # fmt: skip


def compute_exp1_gate(
    results_root,
    tags: tuple[str, ...],
    reference_sun: dict | None,
    run_record: str,
    threshold_px: float = 1.0,
) -> dict:
    """The C20 exp-1 gate document over the live store (LLD §3).

    A stored record that cannot be loaded is counted per strip (strip ``status``
    ``load_failed`` when none of its records loads, else a ``not loaded`` suffix)
    and in the one summary log line with the first reason; it is never dropped
    silently.
    """
    from lunar_reg.results import load_index, load_pair

    index = load_index(results_root)
    ids = [str(p) for p in index["pair_id"]] if "pair_id" in index.columns else []
    strips = []
    problems: dict = {}
    n_unloaded_total = 0
    for tag in tags:
        loaded, n_unloaded = [], 0
        for pair_id in (p for p in ids if tag in p):
            try:
                loaded.append(load_pair(pair_id, results_root))
            except Exception as exc:  # noqa: BLE001 - one unreadable record must not stop the gate
                n_unloaded += 1
                reason = f"{pair_id}: {type(exc).__name__}: {exc}"
                problems.setdefault("first_load_error", reason[:_SAMPLE_MAX])
        n_unloaded_total += n_unloaded
        strips.append(_strip(tag, loaded, threshold_px, n_unloaded, problems))
    n_pass = sum(bool(s["passes_targets"]) for s in strips)
    decision = "SKIP_1B" if strips and n_pass == len(strips) else "BUILD_1B"
    logger.info(
        "exp-1 gate: %d of %d strip(s) pass -> %s; %d stored record(s) not loaded%s; "
        "%d group(s) with agreement not computed%s",
        n_pass, len(strips), decision, n_unloaded_total,
        f" (first: {problems['first_load_error']})" if n_unloaded_total else "",
        problems.get("agreement_failed", 0),
        f" (first: {problems['first_agreement_error']})" if "agreement_failed" in problems else "",
    )  # fmt: skip
    return {
        "schema": 1,
        "decision": decision,
        "rule": EXP1_RULE,
        "strips": strips,
        "n_strips_passing": n_pass,
        "reference_sun": dict(reference_sun or {}),
        "run_record": str(run_record),
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
