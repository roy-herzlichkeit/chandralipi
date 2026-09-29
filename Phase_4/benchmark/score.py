"""Phase 4 benchmark scorer -> benchmark/score.json (RUBRIC.md). Protected (G05).

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
PHASE = "4"
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


# ----------------------------------------------------------------- phase 4 quality

RUN = REPO / "data/processed/multihost/anchor"


def _record():
    return json.loads((RUN / "run_record.json").read_text())


def q_worker_lost() -> dict:
    counts = _record()["outcome_counts"]
    return {"value": float(counts.get("lost_events", 0) >= 1), "lost_events": counts.get("lost_events")}


def q_idempotent() -> dict:
    counts = _record()["outcome_counts"]
    return {"value": float(counts.get("mismatched", 1) == 0),
            "duplicates": counts.get("duplicates"), "mismatched": counts.get("mismatched")}


def q_bytes_per_host() -> dict:
    per_host = Counter()
    missing = 0
    for d in RUN.glob("results_*"):
        for p in d.glob("*.json"):
            doc = json.loads(p.read_text())
            if doc.get("status") == "ok":
                if int(doc.get("bytes_read", 0)) <= 0:
                    missing += 1
                per_host[doc.get("host", "?")] += int(doc.get("bytes_read", 0))
    return {"value": float(len(per_host) >= 2 and missing == 0), "bytes_per_host": dict(per_host),
            "ok_results_without_bytes": missing}


def q_no_oom() -> dict:
    n = int(_record()["outcome_counts"].get("oom", 0))
    return {"value": float(n == 0), "oom": n}


def main() -> int:
    ap_ = argparse.ArgumentParser()
    ap_.add_argument("--out", type=Path, required=True)
    ap_.add_argument("--work", type=Path, required=True)
    args = ap_.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    harness = run_pytest(["Phase_4/harness/tests"], args.work / "bench_harness_junit.xml")
    contracts = run_pytest(["Phase_4/harness/tests/test_contracts_P4.py",
                            "Phase_3/harness/tests/test_contracts_P3.py",
                            "Phase_0/harness/tests/test_contracts_P0.py"],
                           args.work / "bench_contracts_junit.xml")
    suite = run_pytest(["tests", "-m", "not gpu and not data and not weights"],
                       args.work / "bench_suite_junit.xml")
    parts = {}
    for name, fn in (("worker_lost_reclaimed", q_worker_lost), ("idempotent_merge", q_idempotent),
                     ("bytes_per_host", q_bytes_per_host), ("no_oom", q_no_oom)):
        try:
            parts[name] = fn()
        except Exception:  # noqa: BLE001
            parts[name] = {"value": 0.0, "error": traceback.format_exc(limit=3)[-600:]}
    q_pass = {k: v["value"] >= 1.0 for k, v in parts.items()}
    axes = {
        "correctness": axis(min(fraction(harness), fraction(suite)), 1.0,
                            detail={"harness": harness, "cpu_suite": suite},
                            weight=WEIGHTS["correctness"]),
        "spec_conformance": axis(fraction(contracts), 1.0, detail={"contracts": contracts},
                                 weight=WEIGHTS["spec_conformance"]),
        "quality": axis(sum(q_pass.values()) / len(q_pass), 1.0,
                        detail={"parts": parts, "pass": q_pass}, weight=WEIGHTS["quality"]),
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
