"""``run_record.json``: what ran, on what, from which commit (CONTRACTS C15).

Every RUN prompt writes one next to its outputs so a number in a doc can be
traced to the command, parameters, code version, host and device that produced
it, and to the artefact files the run wrote.

    record = start_run(sys.argv, {"matcher": "loftr"})
    ...
    record = finish_run(record, diagnostics.counts, [out_path])
    write_run_record(record, out_dir)
"""

from __future__ import annotations

import dataclasses
import importlib
import json
import logging
import os
import platform
import re
import socket
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

SCHEMA = 1
FILE_NAME = "run_record.json"

#: ``versions`` key -> module whose ``__version__`` is recorded (None: the interpreter).
_VERSION_MODULES = (
    ("python", None),
    ("numpy", "numpy"),
    ("cv2", "cv2"),
    ("torch", "torch"),
    ("kornia", "kornia"),
)

_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")


@dataclass
class RunRecord:
    schema: int = SCHEMA
    command: list[str] = field(default_factory=list)
    params: dict = field(default_factory=dict)
    started_utc: str = ""
    finished_utc: str = ""
    git_sha: str = ""
    git_dirty: bool = True
    host: str = ""
    device: str = ""
    versions: dict[str, str] = field(default_factory=dict)
    outcome_counts: dict[str, int] = field(default_factory=dict)
    artefacts: list[str] = field(default_factory=list)
    notes: str = ""


_KEYS = tuple(f.name for f in dataclasses.fields(RunRecord))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _repo_root() -> Path:
    import lunar_reg

    return Path(lunar_reg.__file__).resolve().parents[2]


def _git_state(repo: Path) -> tuple[str, bool, str]:
    """``(sha, dirty, note)``; on failure ``("", True, "git unavailable: ...")``."""
    try:
        head = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        status = subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        return "", True, f"git unavailable: {exc}"
    for proc in (head, status):
        if proc.returncode != 0:
            first = (proc.stderr.strip().splitlines() or [f"exit {proc.returncode}"])[0]
            return "", True, f"git unavailable: {first}"
    return head.stdout.strip(), bool(status.stdout.strip()), ""


def _device() -> str:
    try:
        import torch

        if torch.cuda.is_available():
            i = torch.cuda.current_device()
            return f"cuda:{i} {torch.cuda.get_device_name(i)}"
    except Exception:  # noqa: BLE001 - any torch import/CUDA query failure means "cpu"
        pass
    return "cpu"


def _versions() -> dict[str, str]:
    out: dict[str, str] = {}
    for key, module in _VERSION_MODULES:
        if module is None:
            out[key] = platform.python_version()
            continue
        try:
            out[key] = str(importlib.import_module(module).__version__)
        except Exception:  # noqa: BLE001 - a missing or broken package is recorded, not fatal
            out[key] = "absent"
    return out


def _artefact_path(path, repo: Path) -> str:
    """Repo-relative POSIX string when under the repo, else absolute POSIX."""
    resolved = Path(path).resolve()
    if resolved.is_relative_to(repo):
        return resolved.relative_to(repo).as_posix()
    return resolved.as_posix()


def start_run(command: list[str], params: dict | None = None) -> RunRecord:
    """Stamp the start of a run: command, params, time, git state, host, device, versions."""
    repo = _repo_root()
    sha, dirty, note = _git_state(repo)
    return RunRecord(
        schema=SCHEMA,
        command=[str(c) for c in command],
        params=dict(params or {}),
        started_utc=_utc_now(),
        finished_utc="",
        git_sha=sha,
        git_dirty=dirty,
        host=socket.gethostname(),
        device=_device(),
        versions=_versions(),
        outcome_counts={},
        artefacts=[],
        notes=note,
    )


def finish_run(record: RunRecord, outcome_counts: dict[str, int], artefacts: list) -> RunRecord:
    """A copy of ``record`` with the finish time, per-status counts and artefact paths."""
    repo = _repo_root()
    return dataclasses.replace(
        record,
        finished_utc=_utc_now(),
        outcome_counts={str(k): int(v) for k, v in outcome_counts.items()},
        artefacts=[_artefact_path(a, repo) for a in artefacts],
    )


def write_run_record(record: RunRecord, out_dir) -> Path:
    """Write ``<out_dir>/run_record.json`` atomically (temp file + ``os.replace``)."""
    path = Path(out_dir) / FILE_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(dataclasses.asdict(record), indent=2, sort_keys=True).encode()
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
        if not replaced:
            tmp.unlink(missing_ok=True)
    return path


def read_run_record(path) -> RunRecord:
    """Load a run record. Raises ``ValueError`` when a key is missing."""
    data = json.loads(Path(path).read_text())
    missing = [k for k in _KEYS if k not in data]
    if missing:
        raise ValueError(f"{path}: run record lacks {', '.join(missing)}")
    return RunRecord(**{k: data[k] for k in _KEYS})


def validate_run_record(path) -> list[str]:
    """Problems with a run record file, as readable strings; ``[]`` means valid. Never raises."""
    path = Path(path)
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        return [f"{path}: unreadable run record: {exc}"]
    if not isinstance(data, dict):
        return [f"{path}: run record is not a JSON object"]

    problems = [f"missing key: {k}" for k in _KEYS if k not in data]
    if data.get("schema", SCHEMA) != SCHEMA:
        problems.append(f"schema is {data.get('schema')!r}, expected {SCHEMA}")
    if "finished_utc" in data and not data["finished_utc"]:
        problems.append("finished_utc is not set (finish_run was not called)")
    sha = data.get("git_sha")
    if "git_sha" in data and not (isinstance(sha, str) and _GIT_SHA.fullmatch(sha)):
        problems.append(f"git_sha is not 40 hex characters: {sha!r}")
    counts = data.get("outcome_counts")
    if "outcome_counts" in data:
        if not isinstance(counts, dict):
            problems.append("outcome_counts is not an object")
        else:
            for status, n in counts.items():
                if isinstance(n, bool) or not isinstance(n, int) or n < 0:
                    problems.append(f"outcome_counts[{status!r}] is not an int >= 0: {n!r}")
    artefacts = data.get("artefacts")
    if "artefacts" in data:
        if not isinstance(artefacts, list):
            problems.append("artefacts is not a list")
        else:
            for artefact in artefacts:
                if not isinstance(artefact, str) or not Path(artefact).exists():
                    problems.append(f"artefact does not exist: {artefact}")
    return problems
