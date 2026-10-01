"""scripts/untar_data.py: a data bundle cannot write outside data/ or overwrite results."""

from __future__ import annotations

import io
import subprocess
import sys
import tarfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "untar_data.py"


def _make_tar(path: Path, members: list[tuple[str, bytes, str]]) -> Path:
    """Write a tar with ``(name, payload, kind)`` members; kind is "file" or "symlink"."""
    with tarfile.open(path, "w") as tar:
        for name, payload, kind in members:
            info = tarfile.TarInfo(name)
            if kind == "file":
                info.size = len(payload)
                tar.addfile(info, io.BytesIO(payload))
            elif kind == "symlink":
                info.type = tarfile.SYMTYPE
                info.linkname = payload.decode()
                tar.addfile(info)
            else:
                raise ValueError(kind)
    return path


def _run(archive: Path, dest: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(archive), "--dest", str(dest), *extra],
        capture_output=True,
        text=True,
        timeout=60,
    )


def _dest(tmp_path: Path) -> Path:
    dest = tmp_path / "dest"
    dest.mkdir()
    return dest


def test_good_archive_extracts(tmp_path: Path) -> None:
    arc = _make_tar(tmp_path / "good.tar", [("data/a.txt", b"hello", "file")])
    dest = _dest(tmp_path)
    out = _run(arc, dest)
    assert out.returncode == 0, out.stdout + out.stderr
    assert (dest / "data" / "a.txt").read_bytes() == b"hello"
    assert "extracted: 1" in out.stdout


def test_parent_traversal_refused_and_nothing_written(tmp_path: Path) -> None:
    arc = _make_tar(
        tmp_path / "trav.tar",
        [("data/ok.txt", b"1", "file"), ("../evil", b"x", "file")],
    )
    dest = _dest(tmp_path)
    out = _run(arc, dest)
    assert out.returncode == 2, out.stdout + out.stderr
    assert "refused_unsafe: 1" in out.stdout
    assert not any(dest.rglob("*"))
    assert not (tmp_path / "evil").exists()


def test_member_outside_data_refused(tmp_path: Path) -> None:
    arc = _make_tar(
        tmp_path / "outside.tar",
        [("data/ok.txt", b"1", "file"), ("src/x.py", b"x", "file")],
    )
    dest = _dest(tmp_path)
    out = _run(arc, dest)
    assert out.returncode == 2, out.stdout + out.stderr
    assert "refused_outside_data: 1" in out.stdout
    assert not any(dest.rglob("*"))


def test_symlink_member_refused(tmp_path: Path) -> None:
    arc = _make_tar(
        tmp_path / "link.tar",
        [("data/ok.txt", b"1", "file"), ("data/l", b"/etc/passwd", "symlink")],
    )
    dest = _dest(tmp_path)
    out = _run(arc, dest)
    assert out.returncode == 2, out.stdout + out.stderr
    assert "refused_unsafe: 1" in out.stdout
    assert not any(dest.rglob("*"))


def test_existing_file_not_overwritten(tmp_path: Path) -> None:
    arc = _make_tar(tmp_path / "a.tar", [("data/r/index.parquet", b"new", "file")])
    dest = _dest(tmp_path)
    (dest / "data" / "r").mkdir(parents=True)
    (dest / "data" / "r" / "index.parquet").write_bytes(b"old")
    out = _run(arc, dest)
    assert out.returncode == 0, out.stdout + out.stderr
    assert (dest / "data" / "r" / "index.parquet").read_bytes() == b"old"
    assert "skipped_exists: 1" in out.stdout


def test_force_overwrites_existing_file(tmp_path: Path) -> None:
    arc = _make_tar(tmp_path / "a.tar", [("data/r/index.parquet", b"new", "file")])
    dest = _dest(tmp_path)
    (dest / "data" / "r").mkdir(parents=True)
    (dest / "data" / "r" / "index.parquet").write_bytes(b"old")
    out = _run(arc, dest, "--force")
    assert out.returncode == 0, out.stdout + out.stderr
    assert (dest / "data" / "r" / "index.parquet").read_bytes() == b"new"
    assert "extracted: 1" in out.stdout
