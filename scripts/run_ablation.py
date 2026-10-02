"""Preprocessing-preset ablation: the measured input to the default preset (P1.18 runs it).

``Phase_1/LLD/jaxa_cli_ablation.md`` §2; the output format and the decision rule
are ``Phase_1/LLD/preprocess_presets.md`` §3
(:func:`lunar_reg.preprocess.presets.choose_default_preset`).

Two kinds of rows, kept apart and labelled:

``anchor`` (real data)
    For each preset, :func:`lunar_reg.sites.runner.run_site` on the anchor OHRC
    raw strip against the LRO NAC orthoimage, one row per (preset, matcher):
    ``status``, ``n_inliers`` and ``u_score``. These have no ground truth; the
    rule counts how often a preset clears the Q18 targets (>= 20 inliers,
    uniformity >= 0.7).
``synthetic`` (SYNTHETIC)
    :func:`lunar_reg.eval.scenes.illumination_pair` scenes with a known
    homography, the reference sun rotated by each of :data:`AZIMUTH_DELTAS`
    degrees, for each of :data:`SEEDS`; ``truth_rms_px`` is
    :func:`lunar_reg.eval.error_budget.transform_rms_px` against that truth.
    Every synthetic row carries ``"label": "SYNTHETIC"``.

Writes ``<out>/ablation.json`` (rows + ``winner`` + ``reason``) and
``<out>/run_record.json``; prints a table and the winner on every run.

Usage::

    .venv/bin/python scripts/run_ablation.py --anchor-tag 20240425T1406019344 \\
        --presets none,ohrc_nac,clahe_shadow --matchers sift,akaze,asift,lightglue \\
        --out data/processed/ablation [--skip-anchor] [--skip-synthetic]
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import math
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

ANCHOR_TAG = "20240425T1406019344"
DEFAULT_PRESETS = ("none", "ohrc_nac", "clahe_shadow")
DEFAULT_MATCHERS = ("sift", "akaze", "asift", "lightglue")
#: Matchers of the synthetic sweep (LLD §2); intersected with ``--matchers``.
SYNTHETIC_MATCHERS = ("sift", "lightglue")
#: Reference-sun azimuth offsets (degrees) of the synthetic sweep. Module level so tests shrink it.
AZIMUTH_DELTAS = (0, 15, 30, 60)
#: Scene seeds of the synthetic sweep. Module level so tests shrink it.
SEEDS = (0, 1, 2, 3, 4)
SYNTHETIC_SHAPE = (512, 512)
SOURCE_SUN = (300.0, 20.0)
REFERENCE_ELEVATION_DEG = 45.0
ANCHOR_MIN_INLIERS = 8
NOT_RUN = "not_run"


def _finite(value) -> float | None:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def anchor_rows(report, preset: str, matchers: tuple[str, ...]) -> list[dict]:
    """One row per matcher from a :class:`~lunar_reg.sites.runner.SiteReport`.

    A matcher without an outcome (product not found, or pair preparation failed)
    gets ``status = "not_run"`` and the reason in ``detail``, never no row.
    """
    outcomes = {}
    reasons = []
    for run in report.runs:
        if run.prep.is_failure:
            reasons.append(f"{run.product_id}: prep {run.prep.value} ({run.prep_detail[:120]})")
        for o in run.outcomes:
            outcomes.setdefault(o.extra.get("matcher", ""), o)
    if not report.runs:
        reasons.append("anchor product not selected (absent from the catalog or filtered out)")
    rows = []
    for matcher in matchers:
        o = outcomes.get(matcher)
        if o is None:
            rows.append(
                {
                    "preset": preset,
                    "matcher": matcher,
                    "status": NOT_RUN,
                    "n_inliers": 0,
                    "u_score": 0.0,
                    "detail": "; ".join(reasons) or "no outcome",
                }
            )
        elif o.ok:
            u = _finite(o.result.uniformity.get("score"))
            rows.append(
                {
                    "preset": preset,
                    "matcher": matcher,
                    "status": o.status.value,
                    "n_inliers": int(o.result.n_inliers),
                    "u_score": u,
                    "pair_id": o.pair_id,
                }
            )
        else:
            rows.append(
                {
                    "preset": preset,
                    "matcher": matcher,
                    "status": o.status.value,
                    "n_inliers": int(o.extra.get("n_refit_inliers") or 0),
                    "u_score": 0.0,
                    "pair_id": o.pair_id,
                    "detail": o.detail[:200],
                }
            )
    return rows


def run_anchor(args, presets, matchers, artefacts: list) -> list[dict]:
    from lunar_reg.sites.runner import SiteConfig, run_site

    rows = []
    for preset in presets:
        cfg = SiteConfig(
            only=args.anchor_tag,
            instruments=("OHRC",),
            levels=("raw",),
            preprocess=preset,
            matchers=matchers,
            results_root=args.out / "store",
            out_dir=args.out / f"anchor_{preset}",
            save_registered=False,
            overwrite=True,
            min_inliers=ANCHOR_MIN_INLIERS,
        )
        report = run_site(cfg)
        print(report.report())
        if report.run_record_path is not None:
            artefacts.append(report.run_record_path)
        rows.extend(anchor_rows(report, preset, matchers))
    return rows


def run_synthetic(presets, matchers) -> list[dict]:
    from lunar_reg.eval.error_budget import transform_rms_px
    from lunar_reg.eval.scenes import illumination_pair
    from lunar_reg.pipeline import PipelineConfig, register_pair

    rows = []
    for delta in AZIMUTH_DELTAS:
        for seed in SEEDS:
            src, ref, truth, _ = illumination_pair(
                shape=SYNTHETIC_SHAPE,
                seed=seed,
                source_sun=SOURCE_SUN,
                reference_sun=(SOURCE_SUN[0] + delta, REFERENCE_ELEVATION_DEG),
            )
            for preset in presets:
                for matcher in matchers:
                    pair_id = f"synthetic_d{delta}_s{seed}_{preset}_{matcher}"
                    config = PipelineConfig(matcher=matcher, preprocess=preset, n_bootstrap=0)
                    o = register_pair(src, ref, pair_id, config, synthetic=True)
                    rms = None
                    if o.ok:
                        rms = _finite(transform_rms_px(o.result.transform, truth, SYNTHETIC_SHAPE))
                    row = {
                        "label": "SYNTHETIC",
                        "preset": preset,
                        "matcher": matcher,
                        "azimuth_delta_deg": delta,
                        "seed": seed,
                        "status": o.status.value,
                        "truth_rms_px": rms,
                        "n_inliers": int(o.result.n_inliers)
                        if o.ok
                        else int(o.extra.get("n_refit_inliers") or 0),
                        "pair_id": pair_id,
                    }
                    if not o.ok:
                        row["detail"] = o.detail[:200]
                    rows.append(row)
    return rows


def _sample(row: dict) -> str:
    """``"<item id>: <detail>"`` (<= 200 chars) for one anchor or synthetic row."""
    item = row.get("pair_id") or f"{row['preset']}/{row['matcher']}"
    return f"{item}: {row.get('detail') or row['status']}"[:200]


def outcome_diagnostics(anchor: list[dict], synthetic: list[dict]):
    """Counts and the first sample per ``<kind>_<status>`` over both row kinds."""
    counts: dict[str, int] = {}
    samples: dict[str, str] = {}
    for kind, rows in (("anchor", anchor), ("synthetic", synthetic)):
        for r in rows:
            key = f"{kind}_{r['status']}"
            counts[key] = counts.get(key, 0) + 1
            samples.setdefault(key, _sample(r))
    return counts, samples


def format_outcomes(counts: dict[str, int], samples: dict[str, str]) -> str:
    """One header line, then ``  <kind>_<status>: <count>  e.g. <sample>`` per key, sorted."""
    total = sum(counts.values())
    lines = [f"outcomes: {total} row(s)" if total else "outcomes: no rows"]
    for key in sorted(counts):
        lines.append(f"  {key}: {counts[key]}  e.g. {samples[key]}")
    return "\n".join(lines)


def format_table(doc: dict, presets) -> str:
    """Per preset: anchor passes / rows and synthetic OK count with median truth RMS."""
    import numpy as np

    from lunar_reg.preprocess.presets import ANCHOR_MIN_INLIERS as PASS_INLIERS
    from lunar_reg.preprocess.presets import ANCHOR_MIN_U_SCORE as PASS_U

    lines = [f"{'preset':<14} {'anchor pass':>12} {'synthetic ok':>13} {'median truth_rms_px':>20}"]
    for p in presets:
        a = [r for r in doc["anchor"] if r["preset"] == p]
        n_pass = sum(
            r["status"] == "ok"
            and (r["n_inliers"] or 0) >= PASS_INLIERS
            and (r["u_score"] or 0.0) >= PASS_U
            for r in a
        )
        s = [r for r in doc["synthetic"] if r["preset"] == p]
        ok = [r["truth_rms_px"] for r in s if r["status"] == "ok" and r["truth_rms_px"] is not None]
        med = f"{float(np.median(ok)):.4g}" if ok else "n/a"
        lines.append(f"{p:<14} {f'{n_pass}/{len(a)}':>12} {f'{len(ok)}/{len(s)}':>13} {med:>20}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--anchor-tag", default=ANCHOR_TAG)
    parser.add_argument("--presets", default=",".join(DEFAULT_PRESETS))
    parser.add_argument("--matchers", default=",".join(DEFAULT_MATCHERS))
    parser.add_argument("--out", type=Path, default=Path("data/processed/ablation"))
    parser.add_argument("--skip-anchor", action="store_true")
    parser.add_argument("--skip-synthetic", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    from lunar_reg.preprocess.presets import PRESET_NAMES, choose_default_preset
    from lunar_reg.provenance import ValueSource
    from lunar_reg.runrecord import finish_run, start_run, write_run_record

    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    presets = tuple(p.strip() for p in args.presets.split(",") if p.strip())
    unknown = [p for p in presets if p not in PRESET_NAMES]
    if unknown:
        print(f"unknown preset(s) {unknown}; choose from {PRESET_NAMES}", file=sys.stderr)
        return 2
    matchers = tuple(m.strip() for m in args.matchers.split(",") if m.strip())
    synthetic_matchers = tuple(m for m in SYNTHETIC_MATCHERS if m in matchers)
    args.out.mkdir(parents=True, exist_ok=True)
    record = start_run(
        ["scripts/run_ablation.py", *(sys.argv[1:] if argv is None else argv)],
        {
            "anchor_tag": args.anchor_tag,
            "presets": list(presets),
            "matchers": list(matchers),
            "synthetic_matchers": list(synthetic_matchers),
            "azimuth_deltas": list(AZIMUTH_DELTAS),
            "seeds": list(SEEDS),
            "synthetic_shape": list(SYNTHETIC_SHAPE),
            "source_sun": list(SOURCE_SUN),
            "reference_elevation_deg": REFERENCE_ELEVATION_DEG,
            "skip_anchor": args.skip_anchor,
            "skip_synthetic": args.skip_synthetic,
        },
    )

    artefacts: list = []
    anchor = [] if args.skip_anchor else run_anchor(args, presets, matchers, artefacts)
    synthetic = [] if args.skip_synthetic else run_synthetic(presets, synthetic_matchers)
    doc = {
        "anchor": anchor,
        "synthetic": synthetic,
        "labels": {"anchor": "REAL", "synthetic": "SYNTHETIC"},
        "value_sources": {
            "n_inliers": ValueSource.MEASURED.value,
            "u_score": ValueSource.MEASURED.value,
            "truth_rms_px": ValueSource.COMPUTED.value,
        },
    }
    winner, reason = choose_default_preset(doc)
    doc.update({"winner": winner, "reason": reason})
    path = args.out / "ablation.json"
    path.write_text(json.dumps(doc, indent=2) + "\n")

    counts, samples = outcome_diagnostics(anchor, synthetic)
    failure_samples = [
        f"first {key}: {samples[key]}" for key in sorted(samples) if not key.endswith("_ok")
    ]
    note = f"winner {winner}: {reason}"
    record = dataclasses.replace(
        record, notes="; ".join(x for x in (record.notes, note, *failure_samples) if x)
    )
    rr_path = write_run_record(finish_run(record, counts, [path, *artefacts]), args.out)

    print(format_table(doc, presets))
    print(format_outcomes(counts, samples))
    print(f"winner: {winner}  ({reason})")
    print(f"wrote {path}; run record {rr_path}")
    any_ok = any(r["status"] == "ok" for r in anchor + synthetic)
    return 0 if any_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
