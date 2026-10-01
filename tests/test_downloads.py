"""P1.01 — download manifest + verifier (src/lunar_reg/ingest/downloads.py, C08)."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from lunar_reg.ingest.downloads import (
    DownloadManifest,
    DownloadStatus,
    record_failure,
    record_file,
    verify_downloads,
)

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts/verify_downloads.py"
MAN = "data/raw/DOWNLOADS.json"


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A fake repo root (cwd) with an empty ``data/raw``."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data/raw").mkdir(parents=True)
    return tmp_path


def _write(root: Path, rel: str, data: bytes = b"abcdef") -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return p


def _rec(path, **kw):
    kw.setdefault("source", "LOCAL")
    kw.setdefault("product_id", Path(path).stem)
    kw.setdefault("instrument", "DOC")
    kw.setdefault("role", "data")
    kw.setdefault("manifest", MAN)
    return record_file(path, **kw)


# ----------------------------------------------------------------- manifest round trip


def test_missing_manifest_is_empty(repo):
    man = DownloadManifest.load(repo / MAN)
    assert man.files == [] and man.failures == [] and man.schema == 1
    diag = verify_downloads(manifest=repo / MAN, raw_root=repo / "data/raw")
    assert diag.counts == {} and not diag.has_failure
    assert "absent" in diag.report()


def test_roundtrip_fields_and_replace(repo):
    f = _write(repo, "data/raw/ch2/ohrc/p/a.img", b"hello")
    e1 = _rec(f, url="https://example.invalid/a", recorded_by="fetch_public")
    assert e1.path == "data/raw/ch2/ohrc/p/a.img"
    assert e1.bytes == 5 and e1.sha256 == hashlib.sha256(b"hello").hexdigest()
    assert e1.downloaded_utc.endswith("Z") and len(e1.downloaded_utc) == 20
    # relative path input gives the same repo-relative key; re-recording replaces
    f.write_bytes(b"hello world")
    e2 = _rec("data/raw/ch2/ohrc/p/a.img")
    man = DownloadManifest.load(MAN)
    assert len(man.files) == 1 and man.files[0] == e2 and e2.bytes == 11
    record_failure("https://example.invalid/b", 503, "Service Unavailable", manifest=MAN)
    record_failure("https://example.invalid/c", 0, "timed out", manifest=MAN)
    doc = json.loads((repo / MAN).read_text())
    assert doc["schema"] == 1
    assert [x["http_status"] for x in doc["failures"]] == [503, 0]
    assert set(doc["failures"][0]) == {"url", "http_status", "error", "utc"}
    # saved with indent=2, sort_keys=True; no temp file left behind
    text = (repo / MAN).read_text()
    assert text == json.dumps(doc, indent=2, sort_keys=True)
    assert not list((repo / "data/raw").glob(".*.tmp"))
    # load -> save is lossless
    DownloadManifest.load(MAN).save(repo / "copy.json")
    assert json.loads((repo / "copy.json").read_text()) == doc


def test_record_rejects_bad_values_and_outside_paths(repo, tmp_path_factory):
    f = _write(repo, "data/raw/x.bin")
    with pytest.raises(ValueError):
        _rec(f, source="NASA")
    with pytest.raises(ValueError):
        _rec(f, instrument="CAMERA")
    with pytest.raises(ValueError):
        _rec(f, role="stuff")
    with pytest.raises(ValueError):
        _rec(f, recorded_by="someone")
    outside = tmp_path_factory.mktemp("elsewhere") / "o.bin"
    outside.write_bytes(b"x")
    with pytest.raises(ValueError):
        _rec(outside)
    assert not (repo / MAN).exists()


# ----------------------------------------------------------------- each status


def test_ok(repo):
    _rec(_write(repo, "data/raw/ch2/a.img"))
    diag = verify_downloads(manifest=MAN, raw_root="data/raw")
    assert diag.counts == {"ok": 1} and not diag.has_failure


def test_missing_file(repo):
    f = _write(repo, "data/raw/ch2/a.img")
    _rec(f)
    f.unlink()
    diag = verify_downloads(manifest=MAN, raw_root="data/raw")
    assert diag.counts == {"missing": 1} and diag.has_failure
    assert "data/raw/ch2/a.img" in diag.samples["missing"]


@pytest.fixture
def unreadable(repo):
    """``data/raw/ch2/a.img`` recorded then chmod 000, plus a readable ``b.img``."""
    f = _write(repo, "data/raw/ch2/a.img")
    _rec(f)
    _rec(_write(repo, "data/raw/ch2/b.img", b"xyz"))
    f.chmod(0)
    try:
        with open(f, "rb"):
            pytest.skip("running with privileges that ignore file permissions")
    except PermissionError:
        pass
    yield f
    f.chmod(0o644)


def test_unreadable_file_is_classified_not_raised(unreadable):
    diag = verify_downloads(manifest=MAN, raw_root="data/raw", scan_unrecorded=False)
    # The unreadable entry is classified, and the next entry is still checked.
    assert diag.counts == {"missing": 1, "ok": 1} and diag.has_failure
    assert diag.samples["missing"].startswith("data/raw/ch2/a.img: unreadable:")
    assert "unreadable" in diag.report()
    # Sizes-only mode stats but does not open the file: chmod 000 still stats.
    diag = verify_downloads(
        manifest=MAN, raw_root="data/raw", check_hash=False, scan_unrecorded=False
    )
    assert diag.counts == {"ok": 2}


def test_cli_unreadable_prints_report_exit_1(repo, unreadable):
    out = _cli(repo, "--manifest", MAN, "--no-scan")
    assert out.returncode == 1, out.stdout + out.stderr
    assert "Traceback" not in out.stderr
    assert "missing" in out.stdout and "unreadable" in out.stdout


def test_wrong_size(repo):
    f = _write(repo, "data/raw/ch2/a.img")
    _rec(f)
    f.write_bytes(b"abc")
    diag = verify_downloads(manifest=MAN, raw_root="data/raw")
    assert diag.counts == {"size_mismatch": 1} and diag.has_failure


def test_wrong_hash_and_no_hash(repo):
    f = _write(repo, "data/raw/ch2/a.img")
    _rec(f)
    f.write_bytes(b"abcdeX")
    diag = verify_downloads(manifest=MAN, raw_root="data/raw")
    assert diag.counts == {"hash_mismatch": 1} and diag.has_failure
    diag = verify_downloads(manifest=MAN, raw_root="data/raw", check_hash=False)
    assert diag.counts == {"ok": 1} and "NOT checked" in diag.report()


def test_unrecorded_is_suspicious_not_failure(repo):
    _rec(_write(repo, "data/raw/ch2/a.img"))
    _write(repo, "data/raw/ch2/_pradan/payload.xhtml")
    diag = verify_downloads(manifest=MAN, raw_root="data/raw")
    assert diag.counts == {"ok": 1, "unrecorded": 1} and not diag.has_failure
    assert "ch2/_pradan/payload.xhtml" in diag.samples["unrecorded"]
    assert "SUSPICIOUS" in diag.report()
    diag = verify_downloads(manifest=MAN, raw_root="data/raw", scan_unrecorded=False)
    assert diag.counts == {"ok": 1}


def test_recorded_failure_is_http_error(repo):
    record_failure("https://data.darts.isas.jaxa.jp/x.img", 503, "rejected", manifest=MAN)
    diag = verify_downloads(manifest=MAN, raw_root="data/raw")
    assert diag.counts == {"http_error": 1} and diag.has_failure
    assert "503" in diag.samples["http_error"]


def test_status_flags():
    failing = {s for s in DownloadStatus if s.is_failure}
    assert failing == {
        DownloadStatus.MISSING,
        DownloadStatus.SIZE_MISMATCH,
        DownloadStatus.HASH_MISMATCH,
        DownloadStatus.HTTP_ERROR,
    }
    assert {s for s in DownloadStatus if s.is_suspicious} == {DownloadStatus.UNRECORDED}


def test_report_lists_every_seen_status(repo):
    for name in ("ok", "gone", "size", "hash"):
        _rec(_write(repo, f"data/raw/ch2/{name}.img"))
    (repo / "data/raw/ch2/gone.img").unlink()
    (repo / "data/raw/ch2/size.img").write_bytes(b"a")
    (repo / "data/raw/ch2/hash.img").write_bytes(b"abcdeX")
    _write(repo, "data/raw/ch2/stray.img")
    record_failure("https://example.invalid/y", 404, "not found", manifest=MAN)
    diag = verify_downloads(manifest=MAN, raw_root="data/raw")
    assert diag.counts == {
        "ok": 1,
        "missing": 1,
        "size_mismatch": 1,
        "hash_mismatch": 1,
        "unrecorded": 1,
        "http_error": 1,
    }
    report = diag.report()
    for s in DownloadStatus:
        assert s.value in report


# ----------------------------------------------------------------- pre-plan exclusions

PRE_PLAN = (
    "data/raw/.gitkeep",
    "data/raw/.tools/record_download.py",
    "data/raw/ohrc_vikram/strip/a.img",
    "data/raw/catalogue/shapefiles/TMC2_ShapeFiles/x.shp",
    "data/raw/reference/jaxa_selene_tc/a.img",
    "data/raw/reference/jaxa_selene_tc_pair2/b.img",
    "data/raw/reference/lro_wac/w.tif",
    "data/raw/reference/lro_nac_vikram/NAC_DTM_X.IMG",
    "data/raw/reference/lro_nac_vikram/NAC_DTM_X.xml",
    "data/raw/reference/lro_nac_vikram/NAC_DTM_X.TIF",
    "data/raw/reference/lro_nac_vikram/PROVENANCE.json",
)

NOT_PRE_PLAN = (
    # subdirectories of lro_nac_vikram are recorded downloads, not pre-plan files
    "data/raw/reference/lro_nac_vikram/edr/M1.xml",
    "data/raw/reference/lro_nac_vikram/ode/box.json",
    # other files directly in lro_nac_vikram are not excluded
    "data/raw/reference/lro_nac_vikram/notes.txt",
    "data/raw/reference/selene_tc_ortho/t.img",
    "data/raw/ch2/_zips/p.zip",
)


def test_pre_plan_files_excluded(repo):
    for rel in PRE_PLAN:
        _write(repo, rel)
    record_failure("https://example.invalid/z", 500, "x", manifest=MAN)  # creates the manifest
    diag = verify_downloads(manifest=MAN, raw_root="data/raw")
    assert diag.counts == {"http_error": 1}


def test_non_pre_plan_files_reported(repo):
    for rel in NOT_PRE_PLAN:
        _write(repo, rel)
    diag = verify_downloads(manifest=MAN, raw_root="data/raw")
    assert diag.counts == {"unrecorded": len(NOT_PRE_PLAN)}


def test_verifier_never_modifies_files(repo):
    f = _write(repo, "data/raw/ch2/a.img")
    _rec(f)
    f.write_bytes(b"changed!")
    _write(repo, "data/raw/ch2/stray.img")
    before = {p: p.read_bytes() for p in (repo / "data/raw").rglob("*") if p.is_file()}
    verify_downloads(manifest=MAN, raw_root="data/raw")
    after = {p: p.read_bytes() for p in (repo / "data/raw").rglob("*") if p.is_file()}
    assert before == after


# ----------------------------------------------------------------- CLI exit codes


def _cli(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], cwd=cwd, capture_output=True, text=True, timeout=60
    )


def test_cli_empty_manifest_exit_0(repo):
    out = _cli(repo)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "absent" in out.stdout


def test_cli_ok_and_unrecorded_exit_0(repo):
    _rec(_write(repo, "data/raw/ch2/a.img"))
    _write(repo, "data/raw/ch2/stray.img")
    out = _cli(repo)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "ok" in out.stdout and "unrecorded" in out.stdout


@pytest.mark.parametrize("damage", ["missing", "size_mismatch", "hash_mismatch", "http_error"])
def test_cli_failure_exit_1(repo, damage):
    f = _write(repo, "data/raw/ch2/a.img")
    _rec(f)
    if damage == "missing":
        f.unlink()
    elif damage == "size_mismatch":
        f.write_bytes(b"a")
    elif damage == "hash_mismatch":
        f.write_bytes(b"abcdeX")
    else:
        record_failure("https://example.invalid/a", 503, "rejected", manifest=MAN)
    out = _cli(repo, "--manifest", MAN, "--no-scan")
    assert out.returncode == 1, out.stdout + out.stderr
    assert damage in out.stdout


def test_cli_no_hash_hides_hash_mismatch(repo):
    f = _write(repo, "data/raw/ch2/a.img")
    _rec(f)
    f.write_bytes(b"abcdeX")
    assert _cli(repo, "--no-hash").returncode == 0
    assert _cli(repo).returncode == 1
