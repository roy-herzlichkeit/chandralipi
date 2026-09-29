"""P0.01 — test runner, CI, safe data unpack (Phase_0/LLD/test_ci.md). Protected (G05)."""

from __future__ import annotations

import io
import os
import stat
import subprocess
import sys
import tarfile
import tomllib

from _h0 import REPO


def _pyproject():
    return tomllib.loads((REPO / "pyproject.toml").read_text())


def test_pytest_config():
    cfg = _pyproject()["tool"]["pytest"]["ini_options"]
    opts = cfg["addopts"].split()
    assert "--strict-markers" in opts and "-ra" in opts and "-q" not in opts
    assert "." in cfg.get("pythonpath", [])
    names = sorted(m.split(":")[0].strip() for m in cfg["markers"])
    assert names == ["data", "gpu", "weights"]


def test_mypy_config():
    mypy = _pyproject()["tool"]["mypy"]
    assert mypy["python_version"] == "3.12"
    assert "packages" not in mypy
    assert mypy["files"] == ["src/lunar_reg"]


def test_ci_script():
    path = REPO / "scripts" / "ci.sh"
    assert path.exists()
    assert path.stat().st_mode & stat.S_IXUSR
    text = path.read_text()
    assert "ruff check src tests scripts dashboard" in text
    assert '-m "not gpu and not data and not weights"' in text


def test_workflow():
    text = (REPO / ".github" / "workflows" / "ci.yml").read_text()
    assert "scripts/ci.sh" in text and "3.12" in text and "download.pytorch.org/whl/cpu" in text


def test_bare_pytest_overlap_crop_tests():
    """S10: bare `pytest` (not `python -m pytest`) must import tests.test_ingest_labels."""
    out = subprocess.run(
        [str(REPO / ".venv" / "bin" / "pytest"), "tests/test_overlap.py", "-q",
         "-p", "no:cacheprovider", "-k", "crop"],
        cwd=REPO, capture_output=True, text=True, timeout=120,
    )
    assert out.returncode == 0, out.stdout[-2000:] + out.stderr[-2000:]


def _tar(path, members):
    with tarfile.open(path, "w") as tar:
        for name, data, kind in members:
            info = tarfile.TarInfo(name)
            if kind == "file":
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
            elif kind == "symlink":
                info.type = tarfile.SYMTYPE
                info.linkname = data.decode()
                tar.addfile(info)


def _run(archive, dest, *extra):
    return subprocess.run(
        [sys.executable, str(REPO / "scripts" / "untar_data.py"), str(archive), "--dest",
         str(dest), *extra], capture_output=True, text=True, timeout=60,
    )


def test_untar_good(tmp_path):
    arc = tmp_path / "good.tar"
    _tar(arc, [("data/processed/a.txt", b"hello", "file")])
    dest = tmp_path / "dest"
    dest.mkdir()
    out = _run(arc, dest)
    assert out.returncode == 0, out.stdout + out.stderr
    assert (dest / "data/processed/a.txt").read_bytes() == b"hello"
    assert "extracted" in out.stdout


def test_untar_refuses_traversal_and_outside(tmp_path):
    for name, members in {
        "trav.tar": [("data/ok.txt", b"1", "file"), ("../evil.txt", b"x", "file")],
        "outside.tar": [("data/ok.txt", b"1", "file"), ("src/x.py", b"x", "file")],
        "link.tar": [("data/ok.txt", b"1", "file"), ("data/l", b"/etc/passwd", "symlink")],
    }.items():
        arc = tmp_path / name
        _tar(arc, members)
        dest = tmp_path / f"dest_{name}"
        dest.mkdir()
        out = _run(arc, dest)
        assert out.returncode == 2, (name, out.stdout, out.stderr)
        assert not any(dest.rglob("*")), f"{name}: something was extracted"
        assert not (tmp_path / "evil.txt").exists()


def test_untar_skips_existing_unless_force(tmp_path):
    arc = tmp_path / "a.tar"
    _tar(arc, [("data/r/index.parquet", b"new", "file")])
    dest = tmp_path / "d"
    (dest / "data/r").mkdir(parents=True)
    (dest / "data/r/index.parquet").write_bytes(b"old")
    out = _run(arc, dest)
    assert out.returncode == 0
    assert (dest / "data/r/index.parquet").read_bytes() == b"old"
    assert "skipped_exists: 1" in out.stdout
    out = _run(arc, dest, "--force")
    assert out.returncode == 0
    assert (dest / "data/r/index.parquet").read_bytes() == b"new"


def test_setup_uses_untar():
    text = (REPO / "scripts" / "setup.sh").read_text()
    assert "scripts/untar_data.py" in text
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        assert not ("tar " in stripped and "-xf" in stripped), f"raw tar extraction left: {line}"
    assert "--ignore-existing" in text
    assert "reindex_results.py" in text
    assert os.access(REPO / "scripts" / "setup.sh", os.R_OK)
