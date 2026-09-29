"""P1.01 — downloads manifest + verifier (Phase_1/LLD/downloads.md §4). Protected (G05)."""

from __future__ import annotations

import subprocess
import sys

import pytest
from _h1 import REPO


def test_pre_plan_files_not_unrecorded(tmp_path, monkeypatch):
    from lunar_reg.ingest.downloads import verify_downloads

    monkeypatch.chdir(tmp_path)
    for rel in ("data/raw/ohrc_vikram/x/a.img", "data/raw/catalogue/c.geojson",
                "data/raw/reference/lro_wac/w.tif", "data/raw/.tools/record_download.py",
                "data/raw/.gitkeep"):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")
    diag = verify_downloads(manifest=tmp_path / "data/raw/DOWNLOADS.json",
                            raw_root=tmp_path / "data/raw")
    assert diag.counts.get("unrecorded", 0) == 0


def test_path_outside_cwd_rejected(tmp_path, monkeypatch):
    from lunar_reg.ingest.downloads import record_file

    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"x")
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    with pytest.raises(ValueError):
        record_file(outside, source="LOCAL", product_id="x", instrument="DOC", role="doc",
                    manifest=work / "data/raw/DOWNLOADS.json")


def test_cli_exit_codes(tmp_path):
    raw = tmp_path / "data/raw"
    raw.mkdir(parents=True)
    script = REPO / "scripts/verify_downloads.py"
    out = subprocess.run([sys.executable, str(script), "--manifest", str(raw / "DOWNLOADS.json")],
                         cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stdout + out.stderr
    code = ("import sys; sys.path.insert(0, %r);"
            "from lunar_reg.ingest.downloads import record_file;"
            "open('data/raw/f.bin','wb').write(b'abc');"
            "record_file('data/raw/f.bin', source='LOCAL', product_id='f', instrument='DOC',"
            " role='doc', manifest='data/raw/DOWNLOADS.json')") % str(REPO / "src")
    subprocess.run([sys.executable, "-c", code], cwd=tmp_path, check=True, timeout=60)
    (raw / "f.bin").unlink()
    out = subprocess.run([sys.executable, str(script), "--manifest", "data/raw/DOWNLOADS.json",
                          "--no-scan"], cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert out.returncode == 1 and "missing" in out.stdout
