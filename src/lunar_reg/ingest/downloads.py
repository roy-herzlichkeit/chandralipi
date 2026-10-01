"""Download manifest (``data/raw/DOWNLOADS.json``) and its verifier.

Why this exists
---------------
Everything under ``data/raw/`` that a Phase 1 session fetched is recorded once,
with its byte count and SHA-256, so that a later run can tell four different
situations apart instead of discovering them as a confusing read error deep in
the pipeline:

* the file is there and unchanged (``OK``);
* the file was recorded but is gone or unreadable (``MISSING``) or changed
  (``SIZE_MISMATCH`` / ``HASH_MISMATCH``);
* a download attempt failed and was recorded as such (``HTTP_ERROR``);
* a file sits under ``data/raw/`` that nobody recorded (``UNRECORDED``) --
  suspicious, not a failure: it may be a legitimate leftover such as PRADAN's
  keep-alive page, but it is reported so it is never invisible.

The file format is frozen by CONTRACTS.md C08; the behaviour by
``Phase_1/LLD/downloads.md`` §4. ``bytes`` and ``sha256`` are measured from the
file on disk by :func:`record_file` (never copied from a server header); the
frozen C08 keys leave no room for a separate provenance field, and none is
needed: every entry is a measurement by construction.

Nothing here ever deletes, moves or rewrites a data file. The only file this
module writes is the manifest itself, atomically.
"""

from __future__ import annotations

import datetime
import fnmatch
import hashlib
import json
import logging
import os
import stat
from dataclasses import asdict, dataclass, field, fields
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_MANIFEST = Path("data/raw/DOWNLOADS.json")
SCHEMA = 1

#: Allowed values of the C08 enum-like string fields.
SOURCES = ("PRADAN", "ODE", "PDS_LROC", "PDS_IMG", "DARTS", "LOCAL")
INSTRUMENTS = (
    "OHRC",
    "TMC2",
    "IIRS",
    "LRO_NAC",
    "LRO_NAC_DTM",
    "LRO_NAC_EDR",
    "SELENE_TC",
    "SELENE_DTM",
    "ODE_METADATA",
    "DOC",
)
ROLES = ("data", "label", "geometry", "browse", "metadata", "misc", "doc")
RECORDERS = ("P1.DL", "fetch_public", "manual")

_CHUNK = 1 << 20  # 1 MiB streaming hash chunks
_UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

#: Files directly under ``raw_root`` (relative POSIX paths, or bare names
#: anywhere) that are never manifest data.
_EXCLUDED_NAMES = (".gitkeep",)
_EXCLUDED_ROOT_FILES = ("DOWNLOADS.json",)
#: Pre-plan trees (relative to ``raw_root``): on disk before Phase 1, never
#: recorded, so never UNRECORDED. ``jaxa_selene_tc`` is a prefix and matches
#: ``jaxa_selene_tc_pair2`` etc.
_EXCLUDED_PREFIXES = (
    ".tools/",
    "ohrc_vikram/",
    "reference/jaxa_selene_tc",
    "reference/lro_wac/",
    "catalogue/",
)
#: Pre-plan files directly inside ``reference/lro_nac_vikram/`` (not its
#: ``ode/`` and ``edr/`` subdirectories, which P1.DL recorded).
_LRO_NAC_DIR = "reference/lro_nac_vikram"
_LRO_NAC_PATTERNS = ("*.IMG", "*.xml", "*.TIF", "PROVENANCE.json")


class DownloadStatus(str, Enum):
    """Outcome of verifying one manifest record or one scanned file."""

    OK = "ok"
    #: Recorded in the manifest, absent from disk, no longer a regular file, or
    #: unreadable (stat or read raised ``OSError``; the sample says "unreadable").
    MISSING = "missing"
    #: On disk with a different byte count than recorded.
    SIZE_MISMATCH = "size_mismatch"
    #: Same size, different SHA-256 (only checked when ``check_hash``).
    HASH_MISMATCH = "hash_mismatch"
    #: A regular file under ``raw_root`` that no entry names and that is not
    #: a pre-plan file. Suspicious, not a failure.
    UNRECORDED = "unrecorded"
    #: A recorded download attempt that failed (one per ``failures`` entry).
    HTTP_ERROR = "http_error"

    @property
    def is_failure(self) -> bool:
        return self in (
            DownloadStatus.MISSING,
            DownloadStatus.SIZE_MISMATCH,
            DownloadStatus.HASH_MISMATCH,
            DownloadStatus.HTTP_ERROR,
        )

    @property
    def is_suspicious(self) -> bool:
        return self is DownloadStatus.UNRECORDED


_DESCRIPTIONS = {
    DownloadStatus.OK: "recorded and unchanged on disk",
    DownloadStatus.MISSING: "recorded but not on disk or unreadable (see sample)",
    DownloadStatus.SIZE_MISMATCH: "on disk with a different size than recorded",
    DownloadStatus.HASH_MISMATCH: "same size, different sha256 than recorded",
    DownloadStatus.UNRECORDED: "on disk under raw_root but in no manifest entry",
    DownloadStatus.HTTP_ERROR: "a recorded failed download attempt",
}


@dataclass
class DownloadEntry:
    """One C08 ``files`` record. Field names are frozen (CONTRACTS.md C08)."""

    path: str  # repo-relative POSIX
    bytes: int
    sha256: str
    source: str
    url: str | None
    product_id: str
    instrument: str
    role: str
    downloaded_utc: str
    recorded_by: str

    def as_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> DownloadEntry:
        names = {f.name for f in fields(cls)}
        if set(d) != names:
            raise ValueError(
                f"manifest entry keys {sorted(d)} differ from C08 keys {sorted(names)}"
            )
        return cls(**d)


@dataclass
class DownloadManifest:
    """The whole ``DOWNLOADS.json`` document."""

    files: list[DownloadEntry] = field(default_factory=list)
    failures: list[dict] = field(default_factory=list)
    schema: int = SCHEMA

    @classmethod
    def load(cls, path: str | os.PathLike = DEFAULT_MANIFEST) -> DownloadManifest:
        """Read a manifest; a missing file is an empty manifest."""
        p = Path(path)
        if not p.exists():
            return cls()
        doc = json.loads(p.read_text())
        if doc.get("schema") != SCHEMA:
            raise ValueError(f"{p}: schema {doc.get('schema')!r}, expected {SCHEMA}")
        return cls(
            files=[DownloadEntry.from_dict(f) for f in doc.get("files", [])],
            failures=list(doc.get("failures", [])),
            schema=SCHEMA,
        )

    def save(self, path: str | os.PathLike = DEFAULT_MANIFEST) -> None:
        """Write atomically (temp file in the same directory, then ``os.replace``)."""
        doc = {
            "schema": self.schema,
            "files": [e.as_dict() for e in self.files],
            "failures": self.failures,
        }
        _atomic_write_bytes(Path(path), json.dumps(doc, indent=2, sort_keys=True).encode())

    def put(self, entry: DownloadEntry) -> None:
        """Add ``entry``, replacing any existing entry with the same path."""
        self.files = [e for e in self.files if e.path != entry.path] + [entry]


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    replaced = False
    try:
        with open(tmp, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
        replaced = True
    finally:
        if not replaced and tmp.exists():
            tmp.unlink()


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime(_UTC_FORMAT)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def _abs(path: str | os.PathLike) -> Path:
    """Absolute path without resolving symlinks (keeps the recorded name)."""
    return Path(os.path.abspath(os.fspath(path)))


def _check_choice(name: str, value: str, allowed: tuple[str, ...]) -> None:
    if value not in allowed:
        raise ValueError(f"{name}={value!r} is not one of {allowed} (CONTRACTS.md C08)")


def record_file(
    path: str | os.PathLike,
    *,
    source: str,
    product_id: str,
    instrument: str,
    role: str,
    url: str | None = None,
    recorded_by: str = "manual",
    manifest: str | os.PathLike = DEFAULT_MANIFEST,
) -> DownloadEntry:
    """Measure ``path`` (size + streaming sha256) and record it in ``manifest``.

    ``path`` is stored relative to the current working directory (the repo root
    in normal use) as POSIX; a path outside the cwd raises ``ValueError``. An
    existing entry with the same path is replaced.
    """
    _check_choice("source", source, SOURCES)
    _check_choice("instrument", instrument, INSTRUMENTS)
    _check_choice("role", role, ROLES)
    _check_choice("recorded_by", recorded_by, RECORDERS)
    absolute = _abs(path)
    cwd = _abs(os.getcwd())
    try:
        rel = absolute.relative_to(cwd)
    except ValueError:
        raise ValueError(f"{absolute} is outside the working directory {cwd}") from None
    if not absolute.is_file():
        raise FileNotFoundError(f"{absolute} is not a regular file")
    entry = DownloadEntry(
        path=rel.as_posix(),
        bytes=absolute.stat().st_size,
        sha256=_sha256(absolute),
        source=source,
        url=url,
        product_id=product_id,
        instrument=instrument,
        role=role,
        downloaded_utc=_utc_now(),
        recorded_by=recorded_by,
    )
    man = DownloadManifest.load(manifest)
    man.put(entry)
    man.save(manifest)
    logger.info("recorded %s (%d B) in %s", entry.path, entry.bytes, manifest)
    return entry


def record_failure(
    url: str,
    http_status: int,
    error: str,
    manifest: str | os.PathLike = DEFAULT_MANIFEST,
) -> None:
    """Append one failed download attempt to ``failures`` (``http_status`` 0 = no HTTP reply)."""
    man = DownloadManifest.load(manifest)
    man.failures.append(
        {"url": url, "http_status": int(http_status), "error": str(error), "utc": _utc_now()}
    )
    man.save(manifest)
    logger.warning("recorded failed download %s (HTTP %s) in %s", url, http_status, manifest)


@dataclass
class DownloadDiagnostics:
    """Counts per :class:`DownloadStatus` value plus the first sample of each."""

    counts: dict[str, int] = field(default_factory=dict)
    samples: dict[str, str] = field(default_factory=dict)
    manifest: str = ""
    manifest_exists: bool = False
    n_entries: int = 0
    n_failures: int = 0
    check_hash: bool = True
    scan_unrecorded: bool = True

    def record(self, status: DownloadStatus, sample: str) -> None:
        self.counts[status.value] = self.counts.get(status.value, 0) + 1
        self.samples.setdefault(status.value, sample[:200])

    @property
    def has_failure(self) -> bool:
        return any(DownloadStatus(k).is_failure for k, n in self.counts.items() if n)

    def report(self) -> str:
        state = "present" if self.manifest_exists else "absent (empty manifest)"
        hashed = "checked" if self.check_hash else "NOT checked"
        scan = "on" if self.scan_unrecorded else "off"
        lines = [
            f"downloads: manifest {self.manifest} {state}; {self.n_entries} file entries, "
            f"{self.n_failures} recorded failures; hash {hashed}; unrecorded scan {scan}"
        ]
        if not self.counts:
            lines.append("  (nothing to verify)")
        for status in DownloadStatus:
            n = self.counts.get(status.value, 0)
            if not n:
                continue
            flag = ""
            if status.is_failure:
                flag = "  <-- FAILURE"
            elif status.is_suspicious:
                flag = "  <-- SUSPICIOUS"
            line = f"  {status.value:<14} {n:>6}  {_DESCRIPTIONS[status]}{flag}"
            if status is not DownloadStatus.OK and status.value in self.samples:
                line += f"  e.g. {self.samples[status.value]}"
            lines.append(line)
        return "\n".join(lines)


def _is_pre_plan(rel: str) -> bool:
    """``rel`` is relative to ``raw_root`` (POSIX)."""
    if rel in _EXCLUDED_ROOT_FILES or rel.rsplit("/", 1)[-1] in _EXCLUDED_NAMES:
        return True
    if rel.startswith(_EXCLUDED_PREFIXES):
        return True
    head, _, name = rel.rpartition("/")
    if head == _LRO_NAC_DIR:
        return any(fnmatch.fnmatchcase(name, pat) for pat in _LRO_NAC_PATTERNS)
    return False


def _iter_regular_files(root: Path):
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            p = Path(dirpath) / name
            try:
                mode = p.lstat().st_mode
            except OSError:
                continue
            if stat.S_ISREG(mode):
                yield p


def verify_downloads(
    manifest: str | os.PathLike = DEFAULT_MANIFEST,
    raw_root: str | os.PathLike = "data/raw",
    check_hash: bool = True,
    scan_unrecorded: bool = True,
) -> DownloadDiagnostics:
    """Classify every manifest entry, every recorded failure and (optionally) every unrecorded file.

    Entry paths are resolved against the current working directory. Never
    deletes or moves anything.
    """
    man_path = Path(manifest)
    man = DownloadManifest.load(man_path)
    diag = DownloadDiagnostics(
        manifest=str(man_path),
        manifest_exists=man_path.exists(),
        n_entries=len(man.files),
        n_failures=len(man.failures),
        check_hash=check_hash,
        scan_unrecorded=scan_unrecorded,
    )
    cwd = _abs(os.getcwd())
    recorded: set[Path] = set()
    for e in man.files:
        p = cwd / e.path
        recorded.add(_abs(p))
        if not p.is_file():
            diag.record(DownloadStatus.MISSING, f"{e.path}: not on disk")
            continue
        try:
            size = p.stat().st_size
            digest = _sha256(p) if check_hash and size == e.bytes else None
        except OSError as exc:
            # Unreadable (permission, I/O error, vanished mid-run): the recorded
            # file cannot be confirmed, so it counts as MISSING (the closest
            # frozen C08 member; see Phase_1/QUESTIONS.md Q-P1.01-1), never a crash.
            diag.record(DownloadStatus.MISSING, f"{e.path}: unreadable: {exc}")
            continue
        if size != e.bytes:
            diag.record(
                DownloadStatus.SIZE_MISMATCH, f"{e.path}: {size} B on disk, {e.bytes} B recorded"
            )
            continue
        if digest is not None and digest != e.sha256:
            diag.record(
                DownloadStatus.HASH_MISMATCH,
                f"{e.path}: sha256 {digest[:12]}... on disk, {e.sha256[:12]}... recorded",
            )
            continue
        diag.record(DownloadStatus.OK, e.path)
    for f in man.failures:
        diag.record(
            DownloadStatus.HTTP_ERROR,
            f"{f.get('url')}: HTTP {f.get('http_status')} {f.get('error')} at {f.get('utc')}",
        )
    if scan_unrecorded:
        root = _abs(raw_root)
        manifest_abs = _abs(man_path)
        if root.is_dir():
            for p in _iter_regular_files(root):
                ap = _abs(p)
                if ap in recorded or ap == manifest_abs:
                    continue
                rel = ap.relative_to(root).as_posix()
                if _is_pre_plan(rel):
                    continue
                diag.record(DownloadStatus.UNRECORDED, f"{rel}: under {raw_root}, in no entry")
    summary = ", ".join(f"{k}={v}" for k, v in sorted(diag.counts.items())) or "nothing to verify"
    log = logger.warning if diag.has_failure else logger.info
    log("verify_downloads %s: %s", man_path, summary)
    return diag
