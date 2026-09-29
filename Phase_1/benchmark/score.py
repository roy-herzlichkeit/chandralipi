"""Phase 1 benchmark scorer -> benchmark/score.json (RUBRIC.md). Protected (G05).

Every number written here is produced by this run (ValueSource MEASURED).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import traceback
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PHASE = "1"
WEIGHTS = {"correctness": 0.35, "spec_conformance": 0.25, "quality": 0.4}


# ----------------------------------------------------------------- common


def run_pytest(targets: list[str], junit: Path, extra: list[str] | None = None) -> dict:
    cmd = [sys.executable, "-m", "pytest", "-o", "addopts=", "--strict-markers", "-q", "-rs",
           "-p", "no:cacheprovider", f"--junitxml={junit}", *targets, *(extra or [])]
    proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=2400)
    return parse_junit(junit) | {"returncode": proc.returncode, "tail": proc.stdout[-1500:]}


def parse_junit(path: Path) -> dict:
    counts = Counter()
    reasons = Counter()
    failed = []
    if not path.exists():
        return {"passed": 0, "failed": 0, "skipped": 0, "errors": 1, "failed_ids": ["no junit"],
                "skip_reasons": {}}
    for case in ET.parse(path).getroot().iter("testcase"):
        tid = f"{case.get('classname')}::{case.get('name')}"
        if case.find("failure") is not None or case.find("error") is not None:
            counts["failed"] += 1
            failed.append(tid)
        elif case.find("skipped") is not None:
            counts["skipped"] += 1
            reasons[(case.find("skipped").get("message") or "")[:120]] += 1
        else:
            counts["passed"] += 1
    return {"passed": counts["passed"], "failed": counts["failed"], "skipped": counts["skipped"],
            "errors": 0, "failed_ids": failed[:50], "skip_reasons": dict(reasons)}


def fraction(res: dict) -> float:
    total = res["passed"] + res["failed"] + res["errors"]
    return res["passed"] / total if total else 0.0


def axis(value, threshold, higher_is_better=True, detail=None, weight=None):
    ok = (value >= threshold) if higher_is_better else (value <= threshold)
    return {"weight": weight, "value": value, "threshold": threshold,
            "direction": ">=" if higher_is_better else "<=", "pass": bool(ok),
            "detail": detail or {}}


def git_sha() -> str:
    out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True)
    return out.stdout.strip()


# ----------------------------------------------------------------- phase 1 quality

ANCHOR = "20240425T1406019344"
TAGS_2023 = ("20230823T1450475804", "20230823T1647285085", "20230823T1647285315")
CLASSES = ("PRIOR", "ILLUMINATION_SUSPECTED", "DATA", "UNRESOLVED")
LIVE = REPO / "data/processed/results"


def _strip_results(tag):
    from lunar_reg.results import load_index, load_pair

    idx = load_index(LIVE)
    if not len(idx):
        return []
    ids = [i for i in idx["pair_id"] if tag in i]
    return [load_pair(i, LIVE) for i in ids]


def q_anchor() -> dict:
    """2024 anchor meets the Q18 targets: >=20 inliers, U>=0.7, pre-ECC agreement <1 px (>=2 matchers)."""
    from lunar_reg.eval.agreement import agreement_for_stored

    results = _strip_results(ANCHOR)
    ok = [r for r in results if r.schema_version == 2]
    best = max(ok, key=lambda r: r.n_inliers, default=None)
    if best is None:
        return {"value": 0.0, "detail": "no v2 anchor result in the live store"}
    agree = agreement_for_stored([r for r in ok if r.pre_ecc_transform is not None])
    u = float(best.uniformity.get("score", 0.0))
    passes = best.n_inliers >= 20 and u >= 0.7 and agree.passes
    return {"value": float(passes), "best_matcher": best.matcher, "n_inliers": best.n_inliers,
            "u_score": u, "agreement_px": agree.max_disagreement_px, "n_matchers": agree.n_matchers}


def q_2023_diagnosed() -> dict:
    """Every 2023 strip has a cause class other than UNRESOLVED, or passes the targets (C20)."""
    gate_path = REPO / "data/processed/vikram/exp1_gate.json"
    doc_path = REPO / "docs/VIKRAM_2023_DIAGNOSIS.md"
    if not gate_path.exists() or not doc_path.exists():
        return {"value": 0.0, "detail": "gate or diagnosis doc missing"}
    gate = json.loads(gate_path.read_text())
    text = doc_path.read_text()
    diagnosed, per = 0, {}
    for strip in gate["strips"]:
        tag = strip["tag"]
        section = text.split(tag, 1)[1][:4000] if tag in text else ""
        cls = next((c for c in CLASSES if c in section), None)
        per[tag] = {"class": cls, "passes": strip["passes_targets"]}
        if strip["passes_targets"] or (cls and cls != "UNRESOLVED"):
            diagnosed += 1
    return {"value": diagnosed / len(TAGS_2023), "per_strip": per, "decision": gate["decision"]}


def q_failures_persisted() -> dict:
    """failures.parquet holds at least as many rows as the failures the Phase 1 run records counted."""
    from lunar_reg.results import load_failures
    from lunar_reg.runrecord import read_run_record

    n_rows = len(load_failures(LIVE))
    counted = 0
    for rel in ("data/processed/vikram/runs/p1_19_anchor/run_record.json",
                "data/processed/vikram/exp1/raw_prior/run_record.json"):
        p = REPO / rel
        if p.exists():
            rec = read_run_record(p)
            counted += sum(v for k, v in rec.outcome_counts.items()
                           if k in {"too_few_matches", "estimation_failed", "too_few_inliers",
                                    "matcher_error", "refinement_failed", "eval_failed",
                                    "preprocess_failed", "oom"})
    return {"value": float(n_rows >= counted), "failures_rows": n_rows, "run_record_failures": counted}


def q_skip_if_absent() -> dict:
    from lunar_reg.ingest.catalog import INSTRUMENTS, build_catalog

    cat = build_catalog(REPO / "data/raw")
    statuses = {k: v.value for k, v in cat.status.items()}
    return {"value": float(set(statuses) == set(INSTRUMENTS)), "statuses": statuses}


def synthetic_axis() -> dict:
    path = REPO / "data/processed/ablation/ablation.json"
    if not path.exists():
        return {"median": float("inf"), "detail": "ablation.json missing"}
    doc = json.loads(path.read_text())
    rows = [r for r in doc["synthetic"] if r["preset"] == doc["winner"] and r["status"] == "ok"
            and r["azimuth_delta_deg"] <= 30 and r.get("truth_rms_px") is not None]
    vals = [float(r["truth_rms_px"]) for r in rows]
    return {"median": float(np.median(vals)) if vals else float("inf"), "n": len(vals),
            "preset": doc["winner"]}


# ----------------------------------------------------------------- main


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--work", type=Path, required=True)
    args = ap.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")

    harness = run_pytest(["Phase_1/harness/tests"], args.work / "bench_harness_junit.xml")
    contracts = run_pytest(["Phase_1/harness/tests/test_contracts_P1.py",
                            "Phase_0/harness/tests/test_contracts_P0.py"],
                           args.work / "bench_contracts_junit.xml")
    suite = run_pytest(["tests", "-m", "not gpu and not data and not weights"],
                       args.work / "bench_suite_junit.xml")

    parts = {}
    for name, fn in (("anchor", q_anchor), ("diagnosed_2023", q_2023_diagnosed),
                     ("failures_persisted", q_failures_persisted),
                     ("skip_if_absent", q_skip_if_absent)):
        try:
            parts[name] = fn()
        except Exception:  # noqa: BLE001 - a crashing metric scores 0 and is reported
            parts[name] = {"value": 0.0, "error": traceback.format_exc(limit=3)[-600:]}
    thresholds = {"anchor": 1.0, "diagnosed_2023": 1.0, "failures_persisted": 1.0,
                  "skip_if_absent": 1.0}
    q_pass = {k: parts[k]["value"] >= t for k, t in thresholds.items()}
    try:
        syn = synthetic_axis()
    except Exception:  # noqa: BLE001
        syn = {"median": float("inf"), "error": traceback.format_exc(limit=3)[-600:]}

    axes = {
        "correctness": axis(min(fraction(harness), fraction(suite)), 1.0,
                            detail={"harness": harness, "cpu_suite": suite},
                            weight=WEIGHTS["correctness"]),
        "spec_conformance": axis(fraction(contracts), 1.0, detail={"contracts": contracts},
                                 weight=WEIGHTS["spec_conformance"]),
        "quality": axis(sum(q_pass.values()) / len(q_pass), 1.0,
                        detail={"parts": parts, "thresholds": thresholds, "pass": q_pass},
                        weight=WEIGHTS["quality"]),
        "synthetic": axis(syn["median"], 0.5, higher_is_better=False,
                          detail={"label": "SYNTHETIC — truth-based error on generated scenes, "
                                           "never merged with real-data axes (Q19)",
                                  "metric": "median truth_rms_px of the default preset over "
                                            "ablation synthetic rows with azimuth delta <= 30 deg",
                                  **syn}, weight=0.0),
    }
    skips = Counter()
    for res in (harness, suite):
        skips.update(res["skip_reasons"])
    total = sum(a["weight"] * (1.0 if a["pass"] else min(max(a["value"], 0.0), 1.0))
                for a in axes.values() if a["weight"])
    score = {"schema": 1, "phase": PHASE, "created_utc": started, "git_sha": git_sha(),
             "provenance": "measured", "axes": axes,
             "skips": {"count": sum(skips.values()), "reasons": dict(skips)},
             "weighted_total": round(total, 4), "pass": all(a["pass"] for a in axes.values())}
    args.out.write_text(json.dumps(score, indent=2, sort_keys=True, default=float))
    print(json.dumps({k: {"value": v["value"], "pass": v["pass"]} for k, v in axes.items()},
                     indent=2, default=float))
    print(f"score.json -> {args.out}  pass={score['pass']}  weighted_total={score['weighted_total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
