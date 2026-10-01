"""Fetch the public NASA/JAXA/NAIF reference files into ``data/raw/reference/``.

The URL table ``SOURCES`` is exactly ``Phase_1/LLD/downloads.md`` §2.2 (one row
per file; the ``.img`` and ``.lbl`` of one SELENE tile share a key). Rules
(LLD §5):

* paced: consecutive requests to ``data.darts.isas.jaxa.jp`` are >= 30 s apart
  (DARTS rate-limits bursts with HTTP 503), to any other host >= 3 s;
* one attempt per URL per run, never retried (a DARTS 503 must not be retried
  in the same session); no range requests (DARTS serves none);
* resumable at file level: a destination already recorded in
  ``data/raw/DOWNLOADS.json`` with a matching size is SKIPPED_PRESENT;
* a destination on disk that the manifest does not confirm is never
  overwritten (PRESENT_UNRECORDED);
* each file streams to ``<dest>.part`` and is renamed with ``os.replace`` only
  when the byte count matches ``Content-Length``;
* every downloaded file is recorded with ``downloads.record_file(...,
  recorded_by="fetch_public")``; every HTTP / network / size failure with
  ``downloads.record_failure(...)``.

    python scripts/fetch_public.py --dry-run                     # print the plan, no request
    python scripts/fetch_public.py --only spice_lsk,spice_pck    # fetch these keys only
    python scripts/fetch_public.py --manifest PATH               # another manifest

Run from the repo root (destinations and manifest paths are repo-relative).
Without ``--only`` only the VALIDATED rows are selected. DOCUMENTED rows
(never fetched successfully when the plan was written) are fetched only when
their key is named in ``--only``, which the plan does only when the human asks
(a failed attempt stays in DOWNLOADS.json ``failures``). The report is printed
on every run.
Exit 1 when any failure (http_error, network_error, size_mismatch,
present_unrecorded) occurred on a VALIDATED row, 2 on a usage error, else 0.
"""

from __future__ import annotations

import argparse
import http.client
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from enum import Enum
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lunar_reg.ingest import downloads  # noqa: E402

logger = logging.getLogger("fetch_public")

USER_AGENT = "lunar-reg-fetch/1 (SIH26166)"
TIMEOUT_S = 120
DARTS_HOST = "data.darts.isas.jaxa.jp"
DARTS_GAP_S = 30.0
DEFAULT_GAP_S = 3.0
RAW_PREFIX = "data/raw/"
_CHUNK = 1 << 20

_ODE = "oderest.rsl.wustl.edu"
_LROC = "pds.lroc.im-ldi.com"
_NAIF = "naif.jpl.nasa.gov"
_ODE_URL = (
    "https://oderest.rsl.wustl.edu/live2/?query=product&results=m&output=JSON&odemetadb=moon"
    "&ihid=LRO&iid=LROC&pt=EDRNAC4&minlat=-69.9&maxlat=-68.7&westernlon=31.9&easternlon=32.8"
    "&limit=1000"
)
_EDR_DIR = (
    "https://pds.lroc.im-ldi.com/data/LRO-L-LROC-2-EDR-V1.0/LROLRC_0056A/DATA/ESM5/2023184/NAC"
)
_DARTS = "https://data.darts.isas.jaxa.jp/pub/pds3"
_ORTHO = f"{_DARTS}/sln-l-tc-5-ortho-map-v2.0/lon030/data"
_DTM = f"{_DARTS}/sln-l-tc-5-dtm-map-v2.0/lon030/data"
_MORNING = f"{_DARTS}/sln-l-tc-5-morning-map-v4.0/lon030/data"
_EVENING = f"{_DARTS}/sln-l-tc-5-evening-map-v4.0/lon030/data"
_NAIF_DIR = "https://naif.jpl.nasa.gov/pub/naif/generic_kernels"
_LRO_REF = "data/raw/reference/lro_nac_vikram"
_REF = "data/raw/reference"


def _tile(key: str, url_dir: str, dest_dir: str, name: str, status: str):
    return tuple(
        (key, f"{url_dir}/{name}{ext}", f"{_REF}/{dest_dir}/{name}{ext}", status, DARTS_HOST)
        for ext in (".img", ".lbl")
    )


#: ``(key, url, dest, status, host)``: exactly the rows of LLD §2.2, one per file.
SOURCES: tuple[tuple[str, str, str, str, str], ...] = (
    ("ode_edrnac4_box", _ODE_URL, f"{_LRO_REF}/ode/edrnac4_vikram_box.json", "VALIDATED", _ODE),
    (
        "edr_le_label",
        f"{_EDR_DIR}/M1442997156LE.xml",
        f"{_LRO_REF}/edr/M1442997156LE.xml",
        "VALIDATED",
        _LROC,
    ),
    (
        "edr_re_label",
        f"{_EDR_DIR}/M1442997156RE.xml",
        f"{_LRO_REF}/edr/M1442997156RE.xml",
        "VALIDATED",
        _LROC,
    ),
    *_tile("tc_ortho_n", _ORTHO, "selene_tc_ortho", "TCO_MAP_02_S66E030S69E033SC", "VALIDATED"),
    *_tile("tc_ortho_s", _ORTHO, "selene_tc_ortho", "TCO_MAP_02_S69E030S72E033SC", "VALIDATED"),
    *_tile("tc_dtm_s", _DTM, "selene_tc_dtm", "DTM_MAP_02_S69E030S72E033SC", "DOCUMENTED"),
    *_tile("tc_dtm_n", _DTM, "selene_tc_dtm", "DTM_MAP_02_S66E030S69E033SC", "DOCUMENTED"),
    *_tile(
        "tc_morning_s", _MORNING, "selene_tc_morning", "TCO_MAPm04_S69E030S72E033SC", "DOCUMENTED"
    ),
    (
        "spice_lsk",
        f"{_NAIF_DIR}/lsk/naif0012.tls",
        f"{_REF}/spice/naif0012.tls",
        "VALIDATED",
        _NAIF,
    ),
    (
        "spice_pck",
        f"{_NAIF_DIR}/pck/pck00011.tpc",
        f"{_REF}/spice/pck00011.tpc",
        "VALIDATED",
        _NAIF,
    ),
    (
        "spice_de440s",
        f"{_NAIF_DIR}/spk/planets/de440s.bsp",
        f"{_REF}/spice/de440s.bsp",
        "VALIDATED",
        _NAIF,
    ),
    *_tile(
        "tc_evening_s", _EVENING, "selene_tc_evening", "TCO_MAPe04_S69E030S72E033SC", "DOCUMENTED"
    ),
)

#: C08 ``source`` / ``instrument`` per key prefix. SPICE kernels have no C08
#: value of their own (no NAIF source, no SPICE instrument): they are recorded
#: as PDS_IMG / DOC with role ``misc`` and the NAIF URL (Phase_1/QUESTIONS.md
#: Q-P1.02-1).
_RECORD_AS = {
    "ode_": ("ODE", "ODE_METADATA"),
    "edr_": ("PDS_LROC", "LRO_NAC_EDR"),
    "tc_dtm_": ("DARTS", "SELENE_DTM"),
    "tc_": ("DARTS", "SELENE_TC"),
    "spice_": ("PDS_IMG", "DOC"),
}


def _record_as(key: str, dest: str) -> tuple[str, str, str, str]:
    """``(source, instrument, role, product_id)`` for the manifest entry of ``dest``."""
    source, instrument = next(v for p, v in _RECORD_AS.items() if key.startswith(p))
    ext = Path(dest).suffix.lower()
    role = {".img": "data", ".lbl": "label", ".xml": "label", ".json": "metadata"}.get(ext, "misc")
    return source, instrument, role, Path(dest).stem


class FetchStatus(str, Enum):
    """Outcome of one ``SOURCES`` row in one run."""

    DOWNLOADED = "downloaded"
    #: ``dest`` exists and DOWNLOADS.json records it with the same size: no request.
    SKIPPED_PRESENT = "skipped_present"
    #: The server answered with an HTTP error status (e.g. a DARTS 503).
    HTTP_ERROR = "http_error"
    #: No HTTP reply, or the transfer broke (DNS, refused, timeout, reset).
    NETWORK_ERROR = "network_error"
    #: Bytes written differ from ``Content-Length``; the ``.part`` is discarded.
    SIZE_MISMATCH = "size_mismatch"
    #: ``dest`` exists but DOWNLOADS.json does not confirm it (no entry, or a
    #: different size). Never overwritten; needs the human (record or move it).
    PRESENT_UNRECORDED = "present_unrecorded"
    #: ``--dry-run``: planned only, no request.
    DRY_RUN = "dry_run"

    @property
    def is_failure(self) -> bool:
        return self in (
            FetchStatus.HTTP_ERROR,
            FetchStatus.NETWORK_ERROR,
            FetchStatus.SIZE_MISMATCH,
            FetchStatus.PRESENT_UNRECORDED,
        )


_DESCRIPTIONS = {
    FetchStatus.DOWNLOADED: "fetched, renamed from .part and recorded",
    FetchStatus.SKIPPED_PRESENT: "already on disk and recorded with the same size (no request)",
    FetchStatus.HTTP_ERROR: "server answered an HTTP error (recorded in failures)",
    FetchStatus.NETWORK_ERROR: "no HTTP reply or broken transfer (recorded in failures)",
    FetchStatus.SIZE_MISMATCH: "bytes written != Content-Length (recorded in failures)",
    FetchStatus.PRESENT_UNRECORDED: "on disk but not confirmed by the manifest; NOT overwritten",
    FetchStatus.DRY_RUN: "planned only (--dry-run), no request",
}


class FetchDiagnostics:
    """Counts per :class:`FetchStatus` value plus the first sample of each.

    A plain class, not a dataclass: the harness loads this script with
    ``spec_from_file_location`` without registering it in ``sys.modules``,
    which ``@dataclass`` needs to resolve string annotations.
    """

    def __init__(self, n_rows: int = 0, dry_run: bool = False) -> None:
        self.counts: dict[str, int] = {}
        self.samples: dict[str, str] = {}
        self.n_rows = n_rows
        self.n_bytes = 0
        self.validated_failure = False
        self.dry_run = dry_run

    def record(self, status: FetchStatus, sample: str, row_status: str = "VALIDATED") -> None:
        self.counts[status.value] = self.counts.get(status.value, 0) + 1
        self.samples.setdefault(status.value, sample[:200])
        if status.is_failure and row_status == "VALIDATED":
            self.validated_failure = True

    def report(self) -> str:
        mode = "dry run" if self.dry_run else "fetch"
        lines = [
            f"fetch_public ({mode}): {self.n_rows} files selected, "
            f"{self.n_bytes} B downloaded this run"
        ]
        if not self.counts:
            lines.append("  (nothing selected)")
        for status in FetchStatus:
            n = self.counts.get(status.value, 0)
            if not n:
                continue
            flag = "  <-- FAILURE" if status.is_failure else ""
            lines.append(
                f"  {status.value:<18} {n:>4}  {_DESCRIPTIONS[status]}{flag}"
                f"  e.g. {self.samples[status.value]}"
            )
        if self.validated_failure:
            lines.append("  a VALIDATED row failed -> exit 1")
        return "\n".join(lines)


class _TransferError(Exception):
    """No HTTP reply, or the response body could not be read to the end."""


def _gap_s(host: str) -> float:
    return DARTS_GAP_S if host == DARTS_HOST else DEFAULT_GAP_S


def _pace(host: str, last_request: dict[str, float]) -> None:
    """Sleep so this request starts >= the host gap after the previous one ended."""
    if host in last_request:
        wait = _gap_s(host) - (time.monotonic() - last_request[host])
        if wait > 0:
            time.sleep(wait)


def _present_state(dest: Path, manifest: Path) -> FetchStatus | None:
    """SKIPPED_PRESENT, PRESENT_UNRECORDED, or None when ``dest`` is absent."""
    if not dest.exists():
        return None
    man = downloads.DownloadManifest.load(manifest)
    entry = next((e for e in man.files if e.path == dest.as_posix()), None)
    if entry is not None and dest.is_file() and dest.stat().st_size == entry.bytes:
        return FetchStatus.SKIPPED_PRESENT
    return FetchStatus.PRESENT_UNRECORDED


def _download(url: str, part: Path) -> tuple[int, int | None, int]:
    """Stream ``url`` into ``part``; return ``(bytes_written, content_length, http_status)``.

    An HTTP error status raises ``urllib.error.HTTPError``; no reply or a broken
    transfer raises :class:`_TransferError`. Local write errors (disk full)
    propagate unchanged: they are not a property of the download.
    """
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        resp = urllib.request.urlopen(req, timeout=TIMEOUT_S)
    except urllib.error.HTTPError:
        raise
    except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
        raise _TransferError(f"{type(exc).__name__}: {exc}") from exc
    with resp:
        length = resp.headers.get("Content-Length")
        status = int(getattr(resp, "status", 200) or 200)
        written = 0
        with open(part, "wb") as fh:
            while True:
                try:
                    chunk = resp.read(_CHUNK)
                except (OSError, http.client.HTTPException) as exc:
                    raise _TransferError(f"{type(exc).__name__}: {exc}") from exc
                if not chunk:
                    break
                fh.write(chunk)
                written += len(chunk)
            fh.flush()
            os.fsync(fh.fileno())
    return written, (int(length) if length is not None else None), status


def _fetch_row(
    row: tuple[str, str, str, str, str],
    manifest: Path,
    last_request: dict[str, float],
    diag: FetchDiagnostics,
) -> FetchStatus:
    key, url, dest_s, row_status, host = row
    dest = Path(dest_s)
    present = _present_state(dest, manifest)
    if present is not None:
        detail = (
            "recorded, same size"
            if present is FetchStatus.SKIPPED_PRESENT
            else "on disk, manifest has no entry with this size; not overwritten"
        )
        diag.record(present, f"{key} {dest_s}: {detail}", row_status)
        return present

    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    _pace(host, last_request)
    replaced = False
    try:
        try:
            written, length, http_status = _download(url, part)
        except urllib.error.HTTPError as exc:
            downloads.record_failure(url, exc.code, f"HTTPError: {exc.reason}", manifest)
            diag.record(FetchStatus.HTTP_ERROR, f"{key} {url}: HTTP {exc.code}", row_status)
            return FetchStatus.HTTP_ERROR
        except _TransferError as exc:
            text = str(exc)
            downloads.record_failure(url, 0, text, manifest)
            diag.record(FetchStatus.NETWORK_ERROR, f"{key} {url}: {text}", row_status)
            return FetchStatus.NETWORK_ERROR
        finally:
            last_request[host] = time.monotonic()
        if length is not None and written != length:
            text = f"size_mismatch: {written} B written, Content-Length {length}"
            downloads.record_failure(url, http_status, text, manifest)
            diag.record(FetchStatus.SIZE_MISMATCH, f"{key} {dest_s}: {text}", row_status)
            return FetchStatus.SIZE_MISMATCH
        os.replace(part, dest)
        replaced = True
    finally:
        if not replaced and part.exists():
            part.unlink()
    source, instrument, role, product_id = _record_as(key, dest_s)
    downloads.record_file(
        dest,
        source=source,
        product_id=product_id,
        instrument=instrument,
        role=role,
        url=url,
        recorded_by="fetch_public",
        manifest=manifest,
    )
    diag.n_bytes += written
    diag.record(FetchStatus.DOWNLOADED, f"{key} {dest_s}: {written} B", row_status)
    return FetchStatus.DOWNLOADED


def _select(only: str | None) -> list[tuple[str, str, str, str, str]]:
    if not only:  # DOCUMENTED rows only when named (LLD §5: when the human asks)
        return [row for row in SOURCES if row[3] == "VALIDATED"]
    wanted = [k.strip() for k in only.split(",") if k.strip()]
    known = {row[0] for row in SOURCES}
    unknown = [k for k in wanted if k not in known]
    if unknown:
        raise ValueError(f"unknown key(s) {unknown}; known: {sorted(known)}")
    return [row for row in SOURCES if row[0] in wanted]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", help="comma-separated keys of SOURCES (default: every VALIDATED row)")
    ap.add_argument("--dry-run", action="store_true", help="print the plan, make no request")
    ap.add_argument(
        "--manifest",
        type=Path,
        default=downloads.DEFAULT_MANIFEST,
        help=f"manifest path (default {downloads.DEFAULT_MANIFEST})",
    )
    args = ap.parse_args(argv)
    try:
        rows = _select(args.only)
    except ValueError as exc:
        print(f"fetch_public: {exc}", file=sys.stderr)
        return 2
    for row in rows:
        if not row[2].startswith(RAW_PREFIX):  # SOURCES is fixed; guard the data rule
            raise AssertionError(f"{row[0]}: destination {row[2]} is outside {RAW_PREFIX}")

    diag = FetchDiagnostics(n_rows=len(rows), dry_run=args.dry_run)
    last_request: dict[str, float] = {}
    try:
        for row in rows:
            key, url, dest, row_status, host = row
            if args.dry_run:
                print(f"plan {key} [{row_status}] {url} -> {dest} (>= {_gap_s(host):.0f} s/{host})")
                diag.record(FetchStatus.DRY_RUN, f"{key} {dest}", row_status)
                continue
            status = _fetch_row(row, args.manifest, last_request, diag)
            print(f"{status.value:<18} {key} {dest}", flush=True)
    finally:
        print(diag.report())
        logger.info("fetch_public summary: %s", diag.counts)
    return 1 if diag.validated_failure else 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    sys.exit(main())
