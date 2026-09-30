"""P4.04 — hosts example, cluster_up dry run, CLI (Phase_4/LLD/hosts_runbook.md). Protected (G05)."""

from __future__ import annotations

import json
import os
import subprocess

from _h4 import REPO


def test_example_has_no_secrets():
    text = (REPO / "configs/hosts.example.json").read_text()
    assert "<fill>" in text and "password" not in json.loads(text)["broker"]


def test_cluster_up_dry_run_never_ssh(tmp_path):
    doc = json.loads((REPO / "configs/hosts.example.json").read_text())
    for h in doc["hosts"]:
        h.update(address="10.0.0.9", ssh_user="u", repo_path=str(REPO), cache_dir=str(tmp_path),
                 results_dir=str(tmp_path / "res"), source_root=str(tmp_path / "src"),
                 max_workers=1)
    hosts = tmp_path / "hosts.json"
    hosts.write_text(json.dumps(doc))
    fakebin = tmp_path / "bin"
    fakebin.mkdir()
    for tool in ("ssh", "rsync"):
        (fakebin / tool).write_text("#!/bin/sh\necho CALLED >&2\nexit 99\n")
        (fakebin / tool).chmod(0o755)
    env = {**os.environ, "PATH": f"{fakebin}:{os.environ['PATH']}", "REDIS_PASSWORD": "x"}
    out = subprocess.run(["bash", str(REPO / "scripts/cluster_up.sh"), str(hosts), "r1",
                          "--dry-run"], cwd=REPO, env=env, capture_output=True, text=True,
                         timeout=60)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "CALLED" not in out.stderr
    assert out.stdout.count("distributed worker") == 2
    lines = [ln for ln in out.stdout.splitlines() if "distributed worker" in ln]
    for ln in lines:   # review RC03 / RC05 / RC34
        for needle in ("--cache-dir", "--source-root", "--results-dir", "ssh -n", "< /dev/null", ".pid"):
            assert needle in ln, (needle, ln)
    stop = subprocess.run(["bash", str(REPO / "scripts/cluster_up.sh"), str(hosts), "r1", "--stop",
                           "--dry-run"], cwd=REPO, env=env, capture_output=True, text=True,
                          timeout=60)
    assert stop.returncode == 0, stop.stdout + stop.stderr
    assert "CALLED" not in stop.stderr and "pkill" not in stop.stdout
    assert stop.stdout.count("kill ") == 2


def test_cli_distributed_subcommands():
    from lunar_reg.cli import build_parser

    p = build_parser()
    for argv in (["distributed", "worker", "--redis-url", "redis://x", "--run-id", "r",
                  "--worker-id", "w", "--device", "cpu", "--results-dir", "d"],
                 ["distributed", "status", "--redis-url", "redis://x", "--run-id", "r", "--purge"],
                 ["distributed", "supervise", "--redis-url", "redis://x", "--run-id", "r",
                  "--stall-s", "0"],
                 ["distributed", "reduce", "--run-dir", "d", "--require-consistent"]):
        assert p.parse_args(argv)


def test_setup_verify_modules_from_extras():
    text = (REPO / "scripts/setup.sh").read_text()
    assert "EXTRAS" in text and "cluster" in text
