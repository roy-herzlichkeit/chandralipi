"""P1.02 — public fetch script (Phase_1/LLD/downloads.md §2.2, §5). Protected (G05)."""

from __future__ import annotations

import io
import urllib.error

import pytest
from _h1 import load_script

VALIDATED_KEYS = {"ode_edrnac4_box", "edr_le_label", "edr_re_label", "tc_ortho_n", "tc_ortho_s"}


def test_sources_table():
    fp = load_script("fetch_public")
    keys = {row[0] for row in fp.SOURCES}
    assert VALIDATED_KEYS <= keys
    for key, url, dest, status, host in fp.SOURCES:
        assert url.startswith("https://") and status in ("VALIDATED", "DOCUMENTED")
        assert host in url
        if "darts" in url:
            assert host == "data.darts.isas.jaxa.jp"
        assert str(dest).startswith("data/raw/reference/")
    darts_validated = [r for r in fp.SOURCES if r[4] == "data.darts.isas.jaxa.jp"
                       and r[3] == "VALIDATED"]
    assert {r[1].rsplit("/", 1)[-1] for r in darts_validated} >= {
        "TCO_MAP_02_S66E030S69E033SC.img", "TCO_MAP_02_S69E030S72E033SC.img"}
    assert {m.value for m in fp.FetchStatus} >= {
        "downloaded", "skipped_present", "http_error", "network_error", "size_mismatch", "dry_run"}


class _Resp(io.BytesIO):
    def __init__(self, data):
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data))}
        self.status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _run(fp, monkeypatch, tmp_path, argv, fail_urls=()):
    requests, sleeps = [], []

    def fake_urlopen(req, timeout=None):
        url = getattr(req, "full_url", req)
        requests.append(url)
        if url in fail_urls:
            raise urllib.error.HTTPError(url, 503, "rejected", {}, None)
        return _Resp(b"payload")

    monkeypatch.setattr(fp.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(fp.time, "sleep", lambda s: sleeps.append(s))
    monkeypatch.chdir(tmp_path)
    code = fp.main([*argv, "--manifest", str(tmp_path / "data/raw/DOWNLOADS.json")])
    return code, requests, sleeps


def test_dry_run_makes_no_request(monkeypatch, tmp_path):
    fp = load_script("fetch_public")
    code, requests, _ = _run(fp, monkeypatch, tmp_path, ["--dry-run", "--only", "tc_ortho_n"])
    assert code == 0 and requests == []


def test_download_records_and_paces(monkeypatch, tmp_path):
    import json

    fp = load_script("fetch_public")
    code, requests, sleeps = _run(fp, monkeypatch, tmp_path, ["--only", "tc_ortho_n,tc_ortho_s"])
    assert code == 0 and len(requests) >= 2
    assert any(s >= 29 for s in sleeps), f"DARTS pacing not applied: {sleeps}"
    doc = json.loads((tmp_path / "data/raw/DOWNLOADS.json").read_text())
    assert all(f["recorded_by"] == "fetch_public" for f in doc["files"])
    assert not list(tmp_path.rglob("*.part"))


def test_http_error_recorded(monkeypatch, tmp_path):
    import json

    fp = load_script("fetch_public")
    row = next(r for r in fp.SOURCES if r[0] == "ode_edrnac4_box")
    code, _, _ = _run(fp, monkeypatch, tmp_path, ["--only", "ode_edrnac4_box"], fail_urls={row[1]})
    assert code == 1
    doc = json.loads((tmp_path / "data/raw/DOWNLOADS.json").read_text())
    assert doc["failures"] and doc["failures"][0]["http_status"] == 503


@pytest.mark.data
def test_run_step_fetched_ode_box():
    from _h1 import REPO

    path = REPO / "data/raw/reference/lro_nac_vikram/ode/edrnac4_vikram_box.json"
    if not path.exists():
        pytest.skip("P1.02 run step not executed yet (network)")
    assert path.stat().st_size > 100_000
