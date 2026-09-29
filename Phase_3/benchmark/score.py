"""Phase 3 benchmark scorer -> benchmark/score.json (RUBRIC.md). Protected (G05).

Every number written here is produced by this run (ValueSource MEASURED).
"""

from __future__ import annotations

import argparse
import dataclasses
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
PHASE = "3"
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


# ----------------------------------------------------------------- phase 3 quality

sys.path.insert(0, str(REPO / "Phase_3" / "harness" / "tests"))


def _plan(tmp):
    from _h3 import T_TRUE, write_pair
    from lunar_reg.distributed.planner import PlanInputs, plan_jobs

    write_pair(tmp)
    inputs = PlanInputs(run_id="bench", pair_id="bench", source_path="src.tif",
                        reference_path="ref.tif", reference_georef={},
                        source_window=(0, 0, 1024, 1024), reference_window=(0, 0, 320, 320),
                        prior_native=tuple(T_TRUE.ravel()), source_native_gsd_m=0.25,
                        reference_native_gsd_m=1.0)
    return plan_jobs(inputs, tile_px=128)


def q_faults(work: Path) -> dict:
    """Injected faults: every job terminal, each fault counted, reducer still OK."""
    import json as _json

    from lunar_reg.distributed.faults import FaultPlan, faulty_worker_main
    from lunar_reg.distributed.runner import run_local

    tmp = work / "faults"
    tmp.mkdir(parents=True, exist_ok=True)
    plan = _plan(tmp)
    fp = FaultPlan(kill_after_claims={"cpu0": 1}, oom_jobs={1}, read_fail_jobs={2},
                   duplicate_jobs={3})
    rep = run_local(plan, tmp / "run", gpu_workers=0, cpu_workers=3, lease_s=5.0,
                    reclaim_every_s=0.5, repo_root=tmp,
                    worker_target=faulty_worker_main(_json.dumps(dataclasses.asdict(fp),
                                                                 default=list)))
    counts = rep.reduce.diagnostics.counts
    checks = {
        "all_terminal": rep.queue.pending == 0 and rep.queue.leased == 0,
        "lost_counted": rep.queue.lost_events >= 1,
        "oom_counted": counts.get("oom", 0) == 1,
        "read_failed_counted": counts.get("read_failed", 0) == 1,
        "duplicates_counted": rep.reduce.diagnostics.n_duplicates == 1,
        "reducer_ok": rep.reduce.status.value == "ok",
    }
    return {"value": sum(checks.values()) / len(checks), "checks": checks, "counts": counts}


def q_order_independent(work: Path) -> dict:
    from lunar_reg.distributed.runner import run_local

    tmp = work / "order"
    tmp.mkdir(parents=True, exist_ok=True)
    plan = _plan(tmp)
    a = run_local(plan, tmp / "one", gpu_workers=0, cpu_workers=1, reclaim_every_s=0.5,
                  repo_root=tmp)
    b = run_local(plan, tmp / "three", gpu_workers=0, cpu_workers=3, reclaim_every_s=0.5,
                  repo_root=tmp)
    same = a.reduce.transform is not None and \
        a.reduce.transform.tobytes() == b.reduce.transform.tobytes()
    return {"value": float(same)}


def q_single_process_equivalence() -> dict:
    run = REPO / "data/processed/distributed/anchor"
    single = json.loads((run / "single_process.json").read_text())
    from lunar_reg.results import load_index, load_pair

    idx = load_index(REPO / "data/processed/results")
    pid = next(p for p in idx["pair_id"] if p.endswith("_dist"))
    dist = np.asarray(load_pair(pid, REPO / "data/processed/results").transform)
    T1 = np.asarray(single["transform"]).reshape(3, 3)
    probes = np.array([[0.0, 0.0], [4000.0, 0.0], [0.0, 4000.0], [4000.0, 4000.0], [2000.0, 2000.0]])

    def ap(H):
        h = np.c_[probes, np.ones(len(probes))] @ H.T
        return h[:, :2] / h[:, 2:]

    diff = float(np.abs(ap(dist) - ap(T1)).max())
    return {"value": float(diff <= 0.1), "max_probe_diff_ref_px": diff}


def main() -> int:
    ap_ = argparse.ArgumentParser()
    ap_.add_argument("--out", type=Path, required=True)
    ap_.add_argument("--work", type=Path, required=True)
    args = ap_.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    harness = run_pytest(["Phase_3/harness/tests"], args.work / "bench_harness_junit.xml")
    contracts = run_pytest(["Phase_3/harness/tests/test_contracts_P3.py",
                            "Phase_2/harness/tests/test_contracts_P2.py",
                            "Phase_1/harness/tests/test_contracts_P1.py",
                            "Phase_0/harness/tests/test_contracts_P0.py"],
                           args.work / "bench_contracts_junit.xml")
    suite = run_pytest(["tests", "-m", "not gpu and not data and not weights"],
                       args.work / "bench_suite_junit.xml")
    parts = {}
    for name, fn in (("faults_classified", lambda: q_faults(args.work)),
                     ("order_independent", lambda: q_order_independent(args.work)),
                     ("single_process_equivalence", q_single_process_equivalence)):
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
