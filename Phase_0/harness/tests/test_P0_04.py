"""P0.04 — remove footprint.py, default.yaml, PyYAML (Phase_0/LLD/dedupe_and_removals.md). Protected (G05)."""

from __future__ import annotations

import importlib.util
import subprocess
import tomllib

from _h0 import REPO


def test_files_deleted():
    for rel in ("src/lunar_reg/ingest/footprint.py", "tests/test_footprint.py",
                "configs/default.yaml"):
        assert not (REPO / rel).exists(), rel
    assert importlib.util.find_spec("lunar_reg.ingest.footprint") is None


def test_moon_datum_moved():
    import lunar_reg.ingest as ingest
    from lunar_reg.constants import MOON_RADIUS_M, moon_datum

    d1, d2 = moon_datum(), moon_datum()
    assert d1 is d2
    assert abs(d1.ellipsoid.a - MOON_RADIUS_M) < 1e-6
    assert ingest.moon_datum is moon_datum
    assert not hasattr(ingest, "Footprint")


def test_no_yaml_dependency():
    deps = tomllib.loads((REPO / "pyproject.toml").read_text())["project"]["dependencies"]
    assert not any(d.lower().startswith("pyyaml") for d in deps)


def test_no_references_left():
    out = subprocess.run(
        ["grep", "-rnE", r"ingest\.footprint|footprint import|default\.yaml|^\s*import yaml",
         "src", "scripts", "dashboard", "tests", "README.md"],
        cwd=REPO, capture_output=True, text=True,
    )
    assert out.stdout.strip() == "", out.stdout
