"""scripts/fetch_public.py: paced, resumable, classified public downloads (no network).

``urllib.request.urlopen`` and ``time.sleep`` are monkeypatched; ``time.monotonic``
is replaced by a fake clock that only the fake ``sleep`` advances, so the
pacing assertions are exact.
"""

from __future__ import annotations

import importlib.util
import io
import json
import urllib.error
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "fetch_public.py"
DARTS = "data.darts.isas.jaxa.jp"


def _load():
    spec = importlib.util.spec_from_file_location("_fetch_public_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fp():
    return _load()


class _Resp(io.BytesIO):
    def __init__(self, data: bytes, content_length: int | None):
        super().__init__(data)
        self.headers = {} if content_length is None else {"Content-Length": str(content_length)}
        self.status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()
        return False


class _Net:
    """Fake network + clock. ``events`` holds ("request", url, t) and ("sleep", s, t)."""

    def __init__(self, fp, monkeypatch, tmp_path, payload=b"payload"):
        self.fp = fp
        self.tmp = tmp_path
        self.payload = payload
        self.now = 1000.0
        self.events: list[tuple] = []
        self.requests: list = []
        self.http_fail: dict[str, int] = {}
        self.net_fail: set[str] = set()
        self.short: set[str] = set()  # Content-Length larger than the body
        self.seen_part_before_replace: list[bool] = []
        monkeypatch.setattr(fp.urllib.request, "urlopen", self.urlopen)
        monkeypatch.setattr(fp.time, "sleep", self.sleep)
        monkeypatch.setattr(fp.time, "monotonic", lambda: self.now)
        monkeypatch.chdir(tmp_path)
        real_replace = fp.os.replace

        def spy_replace(src, dst):  # os.replace is global: the manifest save uses it too
            if str(src).endswith(".part"):
                self.seen_part_before_replace.append(
                    Path(src).exists() and not Path(dst).exists() and Path(dst).name in str(src)
                )
            real_replace(src, dst)

        monkeypatch.setattr(fp.os, "replace", spy_replace)

    @property
    def manifest(self) -> Path:
        return self.tmp / "data/raw/DOWNLOADS.json"

    def urlopen(self, req, timeout=None):
        url = req.full_url
        self.requests.append(req)
        self.events.append(("request", url, self.now))
        self.now += 1.0  # each transfer takes 1 s of fake time
        assert timeout == 120
        if url in self.http_fail:
            raise urllib.error.HTTPError(url, self.http_fail[url], "rejected", {}, None)
        if url in self.net_fail:
            raise urllib.error.URLError("connection refused")
        length = len(self.payload) + 5 if url in self.short else len(self.payload)
        return _Resp(self.payload, length)

    def sleep(self, s):
        self.events.append(("sleep", s, self.now))
        self.now += s

    def run(self, *argv) -> int:
        return self.fp.main([*argv, "--manifest", str(self.manifest)])

    def doc(self) -> dict:
        return json.loads(self.manifest.read_text())


def _rows(fp, key):
    return [r for r in fp.SOURCES if r[0] == key]


def _request_gaps(events, host):
    times = [t for kind, url, t in events if kind == "request" and f"//{host}/" in url]
    return [b - a for a, b in zip(times, times[1:], strict=False)]


# --- SOURCES table ------------------------------------------------------------


def test_sources_match_lld_table(fp):
    keys = [r[0] for r in fp.SOURCES]
    assert set(keys) == {
        "ode_edrnac4_box", "edr_le_label", "edr_re_label", "tc_ortho_n", "tc_ortho_s",
        "tc_dtm_s", "tc_dtm_n", "tc_morning_s", "spice_lsk", "spice_pck", "spice_de440s",
        "tc_evening_s",
    }  # fmt: skip
    assert len(fp.SOURCES) == 18  # 6 SELENE tiles x (.img + .lbl) + 6 single files
    for key, url, dest, status, host in fp.SOURCES:
        assert url.startswith(f"https://{host}/")
        assert dest.startswith("data/raw/reference/")
        assert Path(dest).name == url.rsplit("/", 1)[-1] or key == "ode_edrnac4_box"
        expected = (
            "DOCUMENTED"
            if key.startswith(("tc_dtm", "tc_morning", "tc_evening"))
            else ("VALIDATED")
        )
        assert status == expected, key
    assert {Path(r[2]).suffix for r in _rows(fp, "tc_ortho_n")} == {".img", ".lbl"}


def test_record_as_uses_c08_values(fp):
    from lunar_reg.ingest import downloads

    for key, _url, dest, _status, _host in fp.SOURCES:
        source, instrument, role, product_id = fp._record_as(key, dest)
        assert source in downloads.SOURCES and instrument in downloads.INSTRUMENTS
        assert role in downloads.ROLES and product_id
    assert fp._record_as("tc_dtm_s", "x/DTM_MAP_02_S69E030S72E033SC.img")[:3] == (
        "DARTS", "SELENE_DTM", "data",
    )  # fmt: skip
    assert fp._record_as("edr_le_label", "x/M1442997156LE.xml")[:3] == (
        "PDS_LROC", "LRO_NAC_EDR", "label",
    )  # fmt: skip


# --- dry run, usage -------------------------------------------------------------


def test_dry_run_makes_no_request_and_writes_nothing(fp, monkeypatch, tmp_path, capsys):
    net = _Net(fp, monkeypatch, tmp_path)
    assert net.run("--dry-run") == 0
    assert net.requests == [] and not net.manifest.exists()
    assert not (tmp_path / "data").exists()
    out = capsys.readouterr().out
    assert out.count("plan ") == sum(r[3] == "VALIDATED" for r in fp.SOURCES)
    assert "[DOCUMENTED]" not in out
    assert f">= 30 s/{DARTS}" in out and "dry_run" in out


def test_no_only_never_requests_documented_rows(fp, monkeypatch, tmp_path):
    net = _Net(fp, monkeypatch, tmp_path)
    documented = {r[1] for r in fp.SOURCES if r[3] == "DOCUMENTED"}
    validated = {r[1] for r in fp.SOURCES if r[3] == "VALIDATED"}
    for url in documented:
        net.http_fail[url] = 404
    assert net.run() == 0
    requested = {req.full_url for req in net.requests}
    assert requested == validated and not requested & documented
    assert net.doc()["failures"] == []


def test_documented_row_fetched_when_named(fp, monkeypatch, tmp_path):
    net = _Net(fp, monkeypatch, tmp_path)
    assert net.run("--only", "tc_dtm_s") == 0
    assert {req.full_url for req in net.requests} == {r[1] for r in _rows(fp, "tc_dtm_s")}


def test_unknown_key_is_usage_error(fp, monkeypatch, tmp_path):
    net = _Net(fp, monkeypatch, tmp_path)
    assert net.run("--only", "nope") == 2
    assert net.requests == []


# --- download, .part, recording, pacing -------------------------------------------


def test_download_part_then_rename_and_record(fp, monkeypatch, tmp_path, capsys):
    net = _Net(fp, monkeypatch, tmp_path)
    assert net.run("--only", "tc_ortho_n,spice_lsk") == 0
    assert len(net.requests) == 3
    assert net.seen_part_before_replace == [True, True, True]
    assert not list(tmp_path.rglob("*.part"))
    for _key, _url, dest, _s, _h in _rows(fp, "tc_ortho_n") + _rows(fp, "spice_lsk"):
        assert (tmp_path / dest).read_bytes() == b"payload"
    files = {f["path"]: f for f in net.doc()["files"]}
    assert set(files) == {r[2] for r in _rows(fp, "tc_ortho_n") + _rows(fp, "spice_lsk")}
    assert all(f["recorded_by"] == "fetch_public" and f["bytes"] == 7 for f in files.values())
    img = files["data/raw/reference/selene_tc_ortho/TCO_MAP_02_S66E030S69E033SC.img"]
    assert (img["source"], img["instrument"], img["role"]) == ("DARTS", "SELENE_TC", "data")
    assert img["product_id"] == "TCO_MAP_02_S66E030S69E033SC" and img["url"].startswith("https://")
    for req in net.requests:
        assert req.get_header("User-agent") == "lunar-reg-fetch/1 (SIH26166)"
    assert "downloaded" in capsys.readouterr().out


def test_pacing_per_host(fp, monkeypatch, tmp_path):
    net = _Net(fp, monkeypatch, tmp_path)
    keys = "tc_ortho_n,tc_ortho_s,spice_lsk,spice_pck,spice_de440s,edr_le_label,edr_re_label"
    assert net.run("--only", keys) == 0
    darts_gaps = _request_gaps(net.events, DARTS)
    assert len(darts_gaps) == 3 and all(g >= 30.0 for g in darts_gaps), darts_gaps
    naif_gaps = _request_gaps(net.events, "naif.jpl.nasa.gov")
    assert len(naif_gaps) == 2 and all(g >= 3.0 for g in naif_gaps), naif_gaps
    lroc_gaps = _request_gaps(net.events, "pds.lroc.im-ldi.com")
    assert len(lroc_gaps) == 1 and lroc_gaps[0] >= 3.0
    # the first request to a host never waits; non-DARTS waits are < 30 s
    sleeps = [s for kind, s, _t in net.events if kind == "sleep"]
    assert sleeps and max(sleeps) <= 30.0
    assert sum(1 for s in sleeps if s > 3.0) == 3  # only the three DARTS follow-ups


# --- resume / never overwrite -------------------------------------------------------


def test_skipped_present_makes_no_request(fp, monkeypatch, tmp_path, capsys):
    net = _Net(fp, monkeypatch, tmp_path)
    assert net.run("--only", "spice_lsk") == 0
    capsys.readouterr()
    net.requests.clear()
    assert net.run("--only", "spice_lsk") == 0
    assert net.requests == []
    assert "skipped_present" in capsys.readouterr().out


def test_unrecorded_existing_file_is_not_overwritten(fp, monkeypatch, tmp_path, capsys):
    net = _Net(fp, monkeypatch, tmp_path)
    dest = tmp_path / _rows(fp, "spice_pck")[0][2]
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"precious")
    assert net.run("--only", "spice_pck") == 1  # VALIDATED row not confirmed -> exit 1
    assert net.requests == [] and dest.read_bytes() == b"precious"
    assert "present_unrecorded" in capsys.readouterr().out


def test_recorded_but_size_changed_is_not_overwritten(fp, monkeypatch, tmp_path):
    net = _Net(fp, monkeypatch, tmp_path)
    assert net.run("--only", "spice_pck") == 0
    dest = tmp_path / _rows(fp, "spice_pck")[0][2]
    dest.write_bytes(b"changed on disk")
    net.requests.clear()
    assert net.run("--only", "spice_pck") == 1
    assert net.requests == [] and dest.read_bytes() == b"changed on disk"


# --- failures ------------------------------------------------------------------------


def test_http_error_recorded_and_not_retried(fp, monkeypatch, tmp_path, capsys):
    net = _Net(fp, monkeypatch, tmp_path)
    img_url = _rows(fp, "tc_ortho_s")[0][1]
    net.http_fail[img_url] = 503
    assert net.run("--only", "tc_ortho_s") == 1
    urls = [r.full_url for r in net.requests]
    assert urls.count(img_url) == 1  # one attempt per URL per run
    failures = net.doc()["failures"]
    assert [(f["url"], f["http_status"]) for f in failures] == [(img_url, 503)]
    assert not (tmp_path / _rows(fp, "tc_ortho_s")[0][2]).exists()
    assert not list(tmp_path.rglob("*.part"))
    out = capsys.readouterr().out
    assert "http_error" in out and "HTTP 503" in out and "FAILURE" in out


def test_network_error_recorded_with_status_zero(fp, monkeypatch, tmp_path):
    net = _Net(fp, monkeypatch, tmp_path)
    url = _rows(fp, "ode_edrnac4_box")[0][1]
    net.net_fail.add(url)
    assert net.run("--only", "ode_edrnac4_box") == 1
    (failure,) = net.doc()["failures"]
    assert failure["url"] == url and failure["http_status"] == 0
    assert "URLError" in failure["error"]


def test_size_mismatch_discards_part(fp, monkeypatch, tmp_path, capsys):
    net = _Net(fp, monkeypatch, tmp_path)
    row = _rows(fp, "edr_le_label")[0]
    net.short.add(row[1])
    assert net.run("--only", "edr_le_label") == 1
    assert not (tmp_path / row[2]).exists()
    assert not list(tmp_path.rglob("*.part"))
    doc = net.doc()
    assert doc["files"] == [] and "size_mismatch" in doc["failures"][0]["error"]
    assert "size_mismatch" in capsys.readouterr().out


def test_documented_row_failure_does_not_fail_exit(fp, monkeypatch, tmp_path):
    net = _Net(fp, monkeypatch, tmp_path)
    for _key, url, *_ in _rows(fp, "tc_dtm_s"):
        net.http_fail[url] = 404
    assert net.run("--only", "tc_dtm_s") == 0
    assert len(net.doc()["failures"]) == 2


def test_failure_does_not_stop_later_rows(fp, monkeypatch, tmp_path):
    net = _Net(fp, monkeypatch, tmp_path)
    net.http_fail[_rows(fp, "spice_lsk")[0][1]] = 500
    assert net.run("--only", "spice_lsk,spice_pck") == 1
    assert (tmp_path / _rows(fp, "spice_pck")[0][2]).exists()
    assert [f["path"] for f in net.doc()["files"]] == [_rows(fp, "spice_pck")[0][2]]
