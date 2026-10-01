"""Unpack a data bundle made by ``scripts/pack_data.sh`` without trusting it.

Why this exists
---------------
``tar -xf`` writes wherever the archive's member names point and overwrites
whatever is there. A bundle is supposed to hold only ``data/...``; this script
enforces that. It reads the archive twice:

1. classify every member; if any member is refused (outside ``data/``, an
   absolute path, a ``..`` component, a link, a device or a fifo), print the
   report and exit 2 **before writing anything**;
2. reopen the archive and extract each file whose target does not exist yet
   (or every file with ``--force``), through ``tarfile``'s ``data`` filter.

The report is printed on every run.

    python scripts/untar_data.py bundle.tar.zst                # into the repo root
    python scripts/untar_data.py bundle.tar.gz --dest /tmp/x   # somewhere else
    python scripts/untar_data.py bundle.tar --force            # overwrite existing files

Exit codes: 0 unpacked (some files may be skipped as existing), 2 refused,
3 unreadable archive, unknown extension or ``zstd`` missing.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tarfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path, PurePosixPath

EXIT_OK = 0
EXIT_REFUSED = 2
EXIT_UNREADABLE = 3


class MemberStatus(str, Enum):
    EXTRACTED = "extracted"
    SKIPPED_EXISTS = "skipped_exists"  # target file exists and --force not given
    REFUSED_OUTSIDE_DATA = "refused_outside_data"  # normalised name does not start with "data/"
    # absolute path, ".." component, symlink, hardlink, device, fifo
    REFUSED_UNSAFE = "refused_unsafe"

    @property
    def is_refusal(self) -> bool:
        return self in (MemberStatus.REFUSED_OUTSIDE_DATA, MemberStatus.REFUSED_UNSAFE)


@dataclass
class UntarDiagnostics:
    """Per-status member counts with the first member name as sample."""

    archive: str
    counts: dict[str, int] = field(default_factory=dict)
    samples: dict[str, str] = field(default_factory=dict)
    directories: int = 0

    def record(self, status: MemberStatus, sample: str) -> None:
        self.counts[status.value] = self.counts.get(status.value, 0) + 1
        self.samples.setdefault(status.value, sample[:200])

    @property
    def refused(self) -> bool:
        return any(self.counts.get(s.value, 0) for s in MemberStatus if s.is_refusal)

    def report(self) -> str:
        total = sum(self.counts.values())
        lines = [
            f"untar_data: {self.archive}: {total} members classified; "
            f"{self.directories} directory members created as needed (not counted below)"
        ]
        for status in sorted(self.counts):
            lines.append(f"  {status}: {self.counts[status]}  e.g. {self.samples[status]}")
        if self.refused:
            lines.append("  refused: nothing was extracted from this archive")
        return "\n".join(lines)


class ArchiveError(Exception):
    """The archive cannot be read at all (exit 3)."""


def normalise(name: str) -> str:
    """Strip one leading ``./`` (pack_data.sh archives store ``data/...``)."""
    return name[2:] if name.startswith("./") else name


def classify(member: tarfile.TarInfo) -> MemberStatus | None:
    """Refusal status for ``member``, or None when it may be extracted."""
    name = normalise(member.name)
    path = PurePosixPath(name)
    if name.startswith("/") or path.is_absolute() or ".." in path.parts:
        return MemberStatus.REFUSED_UNSAFE
    # Symlinks, hardlinks, character/block devices and fifos.
    if not (member.isfile() or member.isdir()):
        return MemberStatus.REFUSED_UNSAFE
    is_data_dir = member.isdir() and name.rstrip("/") == "data"
    if not (is_data_dir or name.startswith("data/")):
        return MemberStatus.REFUSED_OUTSIDE_DATA
    return None


@contextmanager
def open_archive(archive: Path) -> Iterator[tarfile.TarFile]:
    """Open ``archive`` for sequential member iteration."""
    name = archive.name
    if name.endswith((".tar.zst", ".tzst")):
        zstd = shutil.which("zstd")
        if zstd is None:
            raise ArchiveError("zstd not found on PATH; install zstd to read .tar.zst bundles")
        proc = subprocess.Popen([zstd, "-dc", str(archive)], stdout=subprocess.PIPE)
        try:
            assert proc.stdout is not None
            with tarfile.open(fileobj=proc.stdout, mode="r|") as tar:
                yield tar
                # Drain so zstd is not killed by SIGPIPE before reporting its own errors.
                shutil.copyfileobj(proc.stdout, _Discard())
        finally:
            if proc.stdout is not None:
                proc.stdout.close()
            rc = proc.wait()
        if rc != 0:
            raise ArchiveError(f"zstd -dc {archive} exited {rc}")
    elif name.endswith((".tar", ".tar.gz", ".tgz")):
        with tarfile.open(archive, "r:*") as tar:
            yield tar
    else:
        raise ArchiveError(
            f"unrecognised archive: {archive} (expected .tar, .tar.gz, .tgz, .tar.zst, .tzst)"
        )


class _Discard:
    def write(self, data: bytes) -> int:
        return len(data)


def untar(archive: Path, dest: Path, force: bool) -> tuple[int, UntarDiagnostics]:
    diag = UntarDiagnostics(archive=str(archive))

    # Pass 1: classify only; refuse the whole archive on any bad member.
    with open_archive(archive) as tar:
        for member in tar:
            status = classify(member)
            if status is not None:
                diag.record(status, member.name)
    if diag.refused:
        return EXIT_REFUSED, diag

    # Pass 2: extract. Re-classify, because the archive was reopened.
    diag = UntarDiagnostics(archive=str(archive))
    with open_archive(archive) as tar:
        for member in tar:
            status = classify(member)
            if status is not None:
                diag.record(status, member.name)
                continue
            if member.isdir():
                diag.directories += 1
                continue
            target = dest / normalise(member.name)
            if target.exists() and not force:
                diag.record(MemberStatus.SKIPPED_EXISTS, member.name)
                continue
            try:
                tar.extract(member, dest, filter="data")
            except tarfile.FilterError as exc:
                # e.g. an existing symlink under dest that resolves outside it.
                diag.record(MemberStatus.REFUSED_UNSAFE, f"{member.name}: {exc}")
                continue
            diag.record(MemberStatus.EXTRACTED, member.name)
    return (EXIT_REFUSED if diag.refused else EXIT_OK), diag


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("archive", type=Path)
    parser.add_argument("--dest", type=Path, default=Path("."), help="directory to unpack into")
    parser.add_argument("--force", action="store_true", help="overwrite files that already exist")
    args = parser.parse_args(argv)

    if not args.archive.is_file():
        print(f"untar_data: archive not found: {args.archive}", file=sys.stderr)
        return EXIT_UNREADABLE
    try:
        code, diag = untar(args.archive, args.dest, args.force)
    except (ArchiveError, tarfile.ReadError, OSError) as exc:
        print(f"untar_data: cannot read {args.archive}: {exc}", file=sys.stderr)
        return EXIT_UNREADABLE
    print(diag.report())
    return code


if __name__ == "__main__":
    sys.exit(main())
