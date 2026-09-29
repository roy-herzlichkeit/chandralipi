"""Phase 1B benchmark scorer -> benchmark/score.json (RUBRIC.md). Protected (G05).

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
PHASE = "1B"
WEIGHTS = {"correctness": 0.3, "spec_conformance": 0.2, "quality": 0.5}


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


# ----------------------------------------------------------------- phase 1B quality

TAGS_2023 = ("20230823T1450475804", "20230823T1647285085", "20230823T1647285315")
LIVE = REPO / "data/processed/results"


def q_targets() -> dict:
    """Fraction of 2023 strips whose best bridge row meets TBD 1.8 targets (>=20 inliers, U>=0.7, agreement<1px)."""
    from lunar_reg.results import load_index, load_pair

    idx = load_index(LIVE)
    per = {}
    for tag in TAGS_2023:
        ids = [i for i in idx["pair_id"] if tag in i and "_bridge-" in i]
        best = None
        for pid in ids:
            r = load_pair(pid, LIVE)
            u = float(r.uniformity.get("score", 0.0))
            agree = r.extra.get("consensus_agreement_px")
            ok = r.n_inliers >= 20 and u >= 0.7 and agree is not None and float(agree) < 1.0
            cand = {"pair_id": pid, "n_inliers": r.n_inliers, "u_score": u,
                    "agreement_px": agree, "passes": ok}
            if best is None or (ok and not best["passes"]) or r.n_inliers > best["n_inliers"]:
                best = cand
        per[tag] = best or {"passes": False, "detail": "no bridge row"}
    value = sum(1 for v in per.values() if v["passes"]) / len(TAGS_2023)
    return {"value": value, "per_strip": per}


def q_calibration() -> dict:
    doc = json.loads((REPO / "data/processed/bridge/azimuth_calibration.json").read_text())
    return {"value": float(doc["residual_deg"] <= 20.0), "residual_deg": doc["residual_deg"],
            "convention": doc["convention"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--work", type=Path, required=True)
    args = ap.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    harness = run_pytest(["Phase_1B/harness/tests"], args.work / "bench_harness_junit.xml")
    contracts = run_pytest(["Phase_1B/harness/tests/test_contracts_P1B.py",
                            "Phase_2/harness/tests/test_contracts_P2.py",
                            "Phase_1/harness/tests/test_contracts_P1.py",
                            "Phase_0/harness/tests/test_contracts_P0.py"],
                           args.work / "bench_contracts_junit.xml")
    suite = run_pytest(["tests", "-m", "not gpu and not data and not weights"],
                       args.work / "bench_suite_junit.xml")
    parts = {}
    for name, fn in (("targets_2023", q_targets), ("calibration", q_calibration)):
        try:
            parts[name] = fn()
        except Exception:  # noqa: BLE001
            parts[name] = {"value": 0.0, "error": traceback.format_exc(limit=3)[-600:]}
    axes = {
        "correctness": axis(min(fraction(harness), fraction(suite)), 1.0,
                            detail={"harness": harness, "cpu_suite": suite},
                            weight=WEIGHTS["correctness"]),
        "spec_conformance": axis(fraction(contracts), 1.0, detail={"contracts": contracts},
                                 weight=WEIGHTS["spec_conformance"]),
        "quality": axis(parts["targets_2023"]["value"], 1.0,
                        detail={"parts": parts,
                                "note": "fraction of 2023 strips meeting TBD 1.8 targets via the bridge; "
                                        "the calibration residual is reported, not scored"},
                        weight=WEIGHTS["quality"]),
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
