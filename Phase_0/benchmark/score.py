"""Phase 0 benchmark scorer -> benchmark/score.json (RUBRIC.md). Protected (G05).

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
PHASE = "0"
WEIGHTS = {"correctness": 0.4, "spec_conformance": 0.3, "quality": 0.3}


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


# ----------------------------------------------------------------- phase 0 quality


def _scene(seed: int, shape=(384, 384)):
    from lunar_reg.eval.scenes import illumination_pair

    return illumination_pair(shape=shape, seed=seed, source_sun=(300, 35), reference_sun=(300, 35))


def q_counts(seeds=range(10)) -> dict:
    """Count/ratio/mask invariants on synthetic pairs (G34)."""
    from lunar_reg.pipeline import PipelineConfig, register_pair

    ok, bad, errors = 0, [], 0
    truth_err = []
    for seed in seeds:
        src, ref, H, _ = _scene(seed)
        try:
            out = register_pair(src, ref, f"s{seed}", PipelineConfig(matcher="sift", n_bootstrap=0))
        except Exception:  # noqa: BLE001 - an exception here is itself the finding
            errors += 1
            bad.append(f"seed {seed}: raised {traceback.format_exc(limit=1).strip()[-160:]}")
            continue
        if not out.ok:
            bad.append(f"seed {seed}: {out.status.value} {out.detail[:80]}")
            continue
        r, m = out.result, out.result.metrics
        cond = (
            m["n_matches"] == r.n_matches >= m["n_ransac_inliers"] >= m["n_inliers"] == r.n_inliers
            and abs(m["inlier_ratio"] - m["n_inliers"] / m["n_matches"]) < 1e-12
            and r.ransac_mask is not None and not np.any(r.inlier_mask & ~r.ransac_mask)
        )
        if cond:
            ok += 1
        else:
            bad.append(f"seed {seed}: invariant broken {m.get('n_matches')}/"
                       f"{m.get('n_ransac_inliers')}/{m.get('n_inliers')}")
        from lunar_reg.eval.error_budget import transform_rms_px

        truth_err.append(float(transform_rms_px(np.asarray(r.transform), H, src.shape[:2])))
    n = len(list(seeds))
    return {"value": ok / n, "unclassified_exceptions": errors, "samples": bad[:5],
            "truth_rms_px": truth_err}


def q_ecc_affine(n=10) -> dict:
    import cv2

    from lunar_reg.align.estimate import Transform
    from lunar_reg.align.refine import EccStatus, ecc_refine

    rng = np.random.default_rng(0)
    ok, samples = 0, []
    probes = np.array([[40.0, 40.0], [200.0, 40.0], [40.0, 200.0], [200.0, 200.0]])
    for i in range(n):
        g = cv2.GaussianBlur(rng.normal(0, 1, (256, 256)).astype(np.float32), (0, 0), 2.0)
        src = ((g - g.min()) / (g.max() - g.min()) * 255).astype(np.uint8)
        A = np.array([[1 + rng.uniform(-0.03, 0.03), rng.uniform(-0.03, 0.03), rng.uniform(-6, 6)],
                      [rng.uniform(-0.03, 0.03), 1 + rng.uniform(-0.03, 0.03), rng.uniform(-6, 6)]])
        ref = cv2.warpAffine(src, A, (256, 256), flags=cv2.INTER_CUBIC)
        start = A.copy()
        start[:, 2] += rng.uniform(-0.8, 0.8, 2)
        try:
            out = ecc_refine(Transform(start, "affine", 50, 50), src, ref)
        except Exception:  # noqa: BLE001
            samples.append(f"{i}: raised")
            continue
        truth = np.c_[probes, np.ones(4)] @ A.T
        err = float(np.abs(out.transform.apply(probes) - truth).max())
        if out.status is EccStatus.APPLIED and out.transform.matrix.shape == (2, 3) and err < 0.1:
            ok += 1
        else:
            samples.append(f"{i}: {out.status.value} shape {out.transform.matrix.shape} err {err:.3f}")
    return {"value": ok / n, "samples": samples[:5]}


def q_determinism() -> dict:
    from lunar_reg.pipeline import PipelineConfig, register_pair

    src, ref, _, _ = _scene(0)
    cfg = PipelineConfig(matcher="sift", n_bootstrap=0)
    a = register_pair(src, ref, "d", cfg)
    b = register_pair(src, ref, "d", cfg)
    if not (a.ok and b.ok):
        return {"value": 0.0, "samples": [a.status.value, b.status.value]}
    same = np.asarray(a.result.transform).tobytes() == np.asarray(b.result.transform).tobytes()
    code = ("import sys, numpy as np; sys.path.insert(0, 'Phase_0/benchmark');"
            "import score; from lunar_reg.pipeline import PipelineConfig, register_pair;"
            "s, r, _, _ = score._scene(0);"
            "o = register_pair(s, r, 'd', PipelineConfig(matcher='sift', n_bootstrap=0));"
            "print(np.asarray(o.result.transform).tobytes().hex())")
    proc = subprocess.run([sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True,
                          timeout=600)
    sub_same = proc.stdout.strip() == np.asarray(a.result.transform).tobytes().hex()
    return {"value": float(same and sub_same), "in_process": same, "subprocess": sub_same}


# ----------------------------------------------------------------- main


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--work", type=Path, required=True)
    args = ap.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(REPO / "Phase_0" / "harness" / "tests"))
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")

    harness = run_pytest(["Phase_0/harness/tests"], args.work / "bench_harness_junit.xml")
    contracts = run_pytest(["Phase_0/harness/tests/test_contracts_P0.py"],
                           args.work / "bench_contracts_junit.xml")
    suite = run_pytest(["tests", "-m", "not gpu and not data and not weights"],
                       args.work / "bench_suite_junit.xml")

    quality_parts = {}
    for name, fn in (("counts", q_counts), ("ecc_affine", q_ecc_affine),
                     ("determinism", q_determinism)):
        try:
            quality_parts[name] = fn()
        except Exception:  # noqa: BLE001 - a crashing metric scores 0 and is reported
            quality_parts[name] = {"value": 0.0, "error": traceback.format_exc(limit=3)[-600:]}

    counts = quality_parts["counts"]
    q_thresholds = {"counts": 1.0, "ecc_affine": 0.9, "determinism": 1.0}
    q_pass = {k: quality_parts[k]["value"] >= t for k, t in q_thresholds.items()}
    q_pass["no_unclassified_exceptions"] = counts.get("unclassified_exceptions", 1) == 0
    quality_value = sum(q_pass.values()) / len(q_pass)

    truth = counts.get("truth_rms_px") or []
    synthetic_median = float(np.median(truth)) if truth else float("inf")

    axes = {
        "correctness": axis(min(fraction(harness), fraction(suite)), 1.0,
                            detail={"harness": harness, "cpu_suite": suite},
                            weight=WEIGHTS["correctness"]),
        "spec_conformance": axis(fraction(contracts), 1.0, detail={"contracts": contracts},
                                 weight=WEIGHTS["spec_conformance"]),
        "quality": axis(quality_value, 1.0, detail={"parts": quality_parts,
                                                     "thresholds": q_thresholds,
                                                     "pass": q_pass},
                        weight=WEIGHTS["quality"]),
        "synthetic": axis(synthetic_median, 0.5, higher_is_better=False,
                          detail={"label": "SYNTHETIC — truth-based error on generated scenes, "
                                           "never merged with real-data axes (Q19)",
                                  "metric": "median transform_rms_px vs known homography, sift, "
                                            "same illumination, 10 seeds",
                                  "values_px": truth},
                          weight=0.0),
    }
    skips = Counter()
    for res in (harness, suite):
        skips.update(res["skip_reasons"])
    total = sum(a["weight"] * (1.0 if a["pass"] else a["value"] if a["value"] <= 1 else 0.0)
                for a in axes.values() if a["weight"])
    score = {
        "schema": 1, "phase": PHASE, "created_utc": started, "git_sha": git_sha(),
        "provenance": "measured", "axes": axes,
        "skips": {"count": sum(skips.values()), "reasons": dict(skips)},
        "weighted_total": round(total, 4),
        "pass": all(a["pass"] for a in axes.values()),
    }
    args.out.write_text(json.dumps(score, indent=2, sort_keys=True, default=float))
    print(json.dumps({k: {"value": v["value"], "pass": v["pass"]} for k, v in axes.items()},
                     indent=2, default=float))
    print(f"score.json -> {args.out}  pass={score['pass']}  weighted_total={score['weighted_total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
