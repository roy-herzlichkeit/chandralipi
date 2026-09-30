"""Phase 2 benchmark scorer -> benchmark/score.json (RUBRIC.md). Protected (G05).

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
PHASE = "2"
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


# ----------------------------------------------------------------- phase 2 quality

ANCHOR = "20240425T1406019344"
PROFILE = REPO / "configs/device_profiles/rtx4060-laptop.json"
LIVE = REPO / "data/processed/results"


def q_profile() -> dict:
    doc = json.loads(PROFILE.read_text())
    entries = [e for m in doc["matchers"].values() for e in m.values()]
    ok = doc.get("source") == "measured" and entries and all(len(e["points"]) >= 3 for e in entries)
    return {"value": float(bool(ok)), "entries": len(entries)}


def _gpu_anchor_rows():
    from lunar_reg.results import load_index

    idx = load_index(LIVE)
    rows = idx[idx["pair_id"].str.contains(ANCHOR)]
    return rows[rows["x_device"].astype(str).str.startswith("cuda")]


def q_native() -> dict:
    rows = _gpu_anchor_rows()
    nat = rows[rows["x_native_status"].notna()] if "x_native_status" in rows else rows.iloc[0:0]
    if not len(nat):
        return {"value": 0.0, "detail": "no native refinement row"}
    r = nat.iloc[0]
    ok = r["x_native_status"] == "ok" and float(r["x_native_drift_coarse_px"]) <= 1.0
    return {"value": float(ok), "status": r["x_native_status"],
            "drift_coarse_px": float(r["x_native_drift_coarse_px"])}


def q_vram_headroom() -> dict:
    doc = json.loads(PROFILE.read_text())
    rows = _gpu_anchor_rows()
    peaks = rows["x_peak_vram_bytes"].dropna().astype(float).tolist() if len(rows) else []
    if not peaks:
        return {"value": 0.0, "detail": "no peak_vram_bytes recorded"}
    limit = 0.75 * float(doc["total_bytes"])
    return {"value": float(max(peaks) <= limit), "max_peak_bytes": max(peaks), "limit": limit}


def q_no_oom() -> dict:
    from lunar_reg.runrecord import read_run_record

    p = REPO / "data/processed/gpu_run/anchor/run_record.json"
    rec = read_run_record(p)
    n = int(rec.outcome_counts.get("oom", 0))
    ok = int(rec.outcome_counts.get("ok", 0))
    return {"value": float(n == 0 and ok > 0), "oom": n, "ok": ok}   # review RC36


def synthetic_native() -> dict:
    import cv2

    from lunar_reg.align.native import refine_native_arrays
    from lunar_reg.eval.scenes import add_craters, fractal_terrain, hillshade

    h = add_craters(fractal_terrain((2048, 2048), seed=11), n=720, seed=11)
    src = np.maximum(hillshade(h, azimuth_deg=315, elevation_deg=35), 1).astype(np.uint8)
    at_1m = cv2.resize(src, (512, 512), interpolation=cv2.INTER_AREA)
    R = np.array([[0.25, 0.0, -0.375], [0.0, 0.25, -0.375], [0.0, 0.0, 1.0]])
    a = np.radians(1.0)
    A = np.array([[np.cos(a), -np.sin(a), 30.0], [np.sin(a), np.cos(a), 20.0], [0, 0, 1.0]])
    ref = cv2.warpAffine(at_1m, A[:2], (600, 600), flags=cv2.INTER_LINEAR)
    T = A @ R
    prior = T.copy()
    prior[0, 2] += 2.0
    out = refine_native_arrays(src, ref, prior, source_native_gsd_m=0.25, reference_native_gsd_m=1.0,
                               matcher="sift", tile_px=256)
    probes = np.array([[200.0, 200.0], [1800.0, 200.0], [200.0, 1800.0], [1800.0, 1800.0]])
    if out.transform is None:
        return {"max_err_px": float("inf"), "status": out.status.value}
    pa = np.c_[probes, np.ones(4)] @ out.transform.T
    pb = np.c_[probes, np.ones(4)] @ T.T
    err = np.abs(pa[:, :2] / pa[:, 2:] - pb[:, :2] / pb[:, 2:]).max()
    return {"max_err_px": float(err), "status": out.status.value}


# ----------------------------------------------------------------- main


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--work", type=Path, required=True)
    args = ap.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")

    harness = run_pytest(["Phase_2/harness/tests"], args.work / "bench_harness_junit.xml")
    contracts = run_pytest(["Phase_2/harness/tests/test_contracts_P2.py",
                            "Phase_1/harness/tests/test_contracts_P1.py",
                            "Phase_0/harness/tests/test_contracts_P0.py"],
                           args.work / "bench_contracts_junit.xml")
    suite = run_pytest(["tests", "-m", "not gpu and not data and not weights"],
                       args.work / "bench_suite_junit.xml")
    parts = {}
    for name, fn in (("profile_measured", q_profile), ("native_within_1_coarse_px", q_native),
                     ("vram_headroom", q_vram_headroom), ("no_oom", q_no_oom)):
        try:
            parts[name] = fn()
        except Exception:  # noqa: BLE001
            parts[name] = {"value": 0.0, "error": traceback.format_exc(limit=3)[-600:]}
    q_pass = {k: v["value"] >= 1.0 for k, v in parts.items()}
    try:
        syn = synthetic_native()
    except Exception:  # noqa: BLE001
        syn = {"max_err_px": float("inf"), "error": traceback.format_exc(limit=3)[-600:]}
    axes = {
        "correctness": axis(min(fraction(harness), fraction(suite)), 1.0,
                            detail={"harness": harness, "cpu_suite": suite},
                            weight=WEIGHTS["correctness"]),
        "spec_conformance": axis(fraction(contracts), 1.0, detail={"contracts": contracts},
                                 weight=WEIGHTS["spec_conformance"]),
        "quality": axis(sum(q_pass.values()) / len(q_pass), 1.0,
                        detail={"parts": parts, "pass": q_pass}, weight=WEIGHTS["quality"]),
        "synthetic": axis(syn["max_err_px"], 0.5, higher_is_better=False,
                          detail={"label": "SYNTHETIC — native refinement vs known transform (Q19)",
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
