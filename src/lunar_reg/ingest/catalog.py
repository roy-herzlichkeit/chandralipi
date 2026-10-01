"""What is on disk, per instrument (contract C09, Phase_1/LLD/catalog.md §2).

:func:`build_catalog` globs fixed search roots under ``raw_root`` for each
instrument, does a minimal read of every label it finds, and classifies the
instrument as a whole:

``ABSENT``
    no label matched and none of the instrument's search directories exists --
    a data gap, skipped downstream (G24), never an error.
``PARTIAL``
    a label without its data file next to it, a data file (``.img``/``.qub``/
    ``.dat`` matched by the label globs with the label suffix swapped) with no
    label of the same stem next to it -- C09's "or the reverse" -- or a search
    directory that exists with no label in it.
``PRESENT``
    every label read, every data file found, and no unlabelled data file.
``UNREADABLE``
    at least one label raised during the minimal read (the only status that
    makes ``lunar-reg catalog`` exit 1).

Per-label outcomes are counted in a :class:`ScanDiagnostics` (classified
outcomes): ``parsed`` for a data label, ``not_a_data_product`` for a label
whose :func:`product_type_of` is not ``"data"`` (still listed, with its type),
``parse_error`` for an unreadable label, ``root_missing`` when ``raw_root``
itself is not on disk.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from lunar_reg.ingest.manifest import ScanDiagnostics, ScanStatus, product_type_of
from lunar_reg.ingest.pds4 import _IMG_SUFFIXES, _find_image, read_label

logger = logging.getLogger(__name__)

INSTRUMENTS = ("OHRC", "TMC2", "IIRS", "LRO_NAC", "LRO_NAC_DTM", "SELENE_TC")


class InstrumentStatus(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"
    PARTIAL = "partial"
    UNREADABLE = "unreadable"

    @property
    def is_failure(self) -> bool:
        return self is InstrumentStatus.UNREADABLE


#: Label globs per instrument, relative to ``raw_root`` (LLD §2, fixed).
SEARCH_GLOBS: dict[str, tuple[str, ...]] = {
    "OHRC": (
        "ohrc_vikram/*/data/**/*_d_img_*.xml",
        "ch2/ohrc/*/data/**/*_d_img_*.xml",
    ),
    "TMC2": (
        "ch2/tmc2/*/data/**/*_d_img_*.xml",
        "ch2/tmc2/*/data/**/*_d_oth_*.xml",
        "ch2/tmc2/*/data/**/*_d_dtm_*.xml",
    ),
    "IIRS": ("ch2/iirs/*/data/**/*_d_*.xml",),
    "LRO_NAC": ("reference/lro_nac_vikram/NAC_DTM_VIKRAMSITE1_M*_100CM.xml",),
    "LRO_NAC_DTM": ("reference/lro_nac_vikram/NAC_DTM_VIKRAMSITE1.xml",),
    "SELENE_TC": ("reference/selene_tc_ortho/*.lbl", "reference/jaxa_selene_tc*/*/*.lbl"),
}

#: The directories (globs, relative to ``raw_root``) whose existence separates
#: ABSENT (none exists) from PARTIAL (one exists but holds no matching label).
SEARCH_DIRS: dict[str, tuple[str, ...]] = {
    "OHRC": ("ohrc_vikram", "ch2/ohrc"),
    "TMC2": ("ch2/tmc2",),
    "IIRS": ("ch2/iirs",),
    "LRO_NAC": ("reference/lro_nac_vikram",),
    "LRO_NAC_DTM": ("reference/lro_nac_vikram",),
    "SELENE_TC": ("reference/selene_tc_ortho", "reference/jaxa_selene_tc*"),
}

#: Where each instrument's ``level`` comes from. TMC-2/IIRS file-name tokens are
#: UNVERIFIED (the PRADAN FAQ gives examples only), so they are inferred.
LEVEL_SOURCE: dict[str, str] = {
    "OHRC": "lld_filename_rule",
    "TMC2": "inferred_from_filename",
    "IIRS": "inferred_from_filename",
    "LRO_NAC": "lld_fixed",
    "LRO_NAC_DTM": "lld_fixed",
    "SELENE_TC": "lld_filename_rule",
}

_CH2 = ("OHRC", "TMC2", "IIRS")
_TIMESTAMP = re.compile(r"\d{8}T\d{10}")
#: classified-outcomes skill: a sample is at most this many characters.
_SAMPLE_MAX = 200


@dataclass
class CatalogEntry:
    instrument: str
    product_id: str
    label_path: Path
    image_path: Path | None
    level: str  # "raw" | "calibrated" | "derived" | "unknown"
    product_type: str  # "data" | "browse" | "geometry" | "other"
    geometry_grid_path: Path | None

    @property
    def level_source(self) -> str:
        return LEVEL_SOURCE.get(self.instrument, "unknown")

    def as_dict(self) -> dict:
        """JSON-safe: paths as strings."""
        return {
            "instrument": self.instrument,
            "product_id": self.product_id,
            "label_path": str(self.label_path),
            "image_path": None if self.image_path is None else str(self.image_path),
            "level": self.level,
            "level_source": self.level_source,
            "product_type": self.product_type,
            "geometry_grid_path": (
                None if self.geometry_grid_path is None else str(self.geometry_grid_path)
            ),
        }


_STATUS_MEANING = {
    InstrumentStatus.PRESENT: "",
    InstrumentStatus.ABSENT: "no search directory on disk (data gap; skipped, G24)",
    InstrumentStatus.PARTIAL: "",
    InstrumentStatus.UNREADABLE: "a label failed to read (see parse_error below)",
}


@dataclass
class ProductCatalog:
    entries: list[CatalogEntry]
    status: dict[str, InstrumentStatus]  # one key per INSTRUMENTS member
    diagnostics: ScanDiagnostics  # counts per ScanStatus + first sample

    def __post_init__(self) -> None:
        # Data files with no same-stem label, per instrument (C09 "or the
        # reverse"); filled by build_catalog. A plain attribute, not a dataclass
        # field, so C09's frozen field list is unchanged.
        self.unlabelled_data: dict[str, list[Path]] = {}

    def products(self, instrument: str, product_type: str = "data") -> list[CatalogEntry]:
        return [
            e for e in self.entries if e.instrument == instrument and e.product_type == product_type
        ]

    def as_dict(self) -> dict:
        return {
            "status": {k: v.value for k, v in self.status.items()},
            "entries": [e.as_dict() for e in self.entries],
        }

    def report(self) -> str:
        lines = []
        for inst, status in self.status.items():
            mine = [e for e in self.entries if e.instrument == inst]
            line = f"{inst}: {status.value}, {len(mine)} product(s)"
            if mine:
                data = [e for e in mine if e.product_type == "data"] or mine
                line += f", e.g. {data[0].product_id}"
            detail = _STATUS_MEANING[status]
            if status is InstrumentStatus.PARTIAL:
                missing = [e for e in mine if e.image_path is None]
                orphans = self.unlabelled_data.get(inst, [])
                parts = []
                if missing:
                    parts.append(
                        f"data file missing next to {len(missing)} label(s), e.g. "
                        f"{missing[0].label_path.name}"
                    )
                if orphans:
                    parts.append(
                        f"label missing next to {len(orphans)} data file(s), e.g. {orphans[0].name}"
                    )
                detail = "; ".join(parts) or "search directory exists but no label matched"
            if detail:
                line += f"  ({detail})"
            lines.append(line)
        lines.append(self.diagnostics.report())
        return "\n".join(lines)


def _level(instrument: str, stem: str) -> str:
    """Processing level from the file name (LLD §2 table)."""
    name = stem.lower()
    tokens = name.split("_")
    token = tokens[2] if len(tokens) > 2 else ""
    if instrument == "OHRC":
        return {"nrp": "raw", "ncp": "calibrated"}.get(token, "unknown")
    if instrument in ("TMC2", "IIRS"):
        if "_d_oth_" in name or "_d_dtm_" in name:
            return "derived"
        second = token[1:2]
        return {"r": "raw", "c": "calibrated"}.get(second, "unknown")
    if instrument in ("LRO_NAC", "LRO_NAC_DTM"):
        return "derived"
    if instrument == "SELENE_TC":
        return "derived" if name.startswith("tco_map") else "raw"
    return "unknown"


def _product_dir(label_path: Path) -> Path | None:
    """The CH-2 product directory: parent of the ``data`` directory holding the label."""
    for parent in label_path.parents:
        if parent.name == "data":
            return parent.parent
    return None


def _geometry_grid(label_path: Path) -> Path | None:
    match = _TIMESTAMP.search(label_path.name)
    product_dir = _product_dir(label_path)
    if match is None or product_dir is None:
        return None
    for grid in sorted((product_dir / "geometry").glob("**/*_g_grd_*.csv")):
        if match.group(0) in grid.name:
            return grid
    return None


def _minimal_read(label_path: Path) -> Path | None:
    """Read the label just enough to know it is a label; return its data file.

    PDS4 ``.xml``: :func:`read_label`. PDS3 ``.lbl``: existence + first line.
    The data file is :func:`pds4._find_image`'s answer, or ``None`` when that
    path does not exist. Raises when the label cannot be read.
    """
    if label_path.suffix.lower() == ".lbl":
        # Binary: only line 1 is read, so a non-UTF-8 byte later in the label
        # (e.g. a Latin-1 degree sign) cannot make it UNREADABLE.
        with label_path.open("rb") as fh:
            first = fh.readline()
        if not first.strip():
            raise ValueError("empty first line")
        image = _find_image(label_path, None)
    else:
        image = read_label(label_path).image_path
    if image is None or not image.exists():
        return None
    return image


def _labels(raw_root: Path, instrument: str) -> list[Path]:
    found: set[Path] = set()
    for pattern in SEARCH_GLOBS[instrument]:
        found.update(p for p in raw_root.glob(pattern) if p.is_file())
    return sorted(found)


def _unlabelled_data(
    raw_root: Path, instrument: str, labels: list[Path], images: set[Path]
) -> list[Path]:
    """Data files under the instrument's label globs with no label of the same stem.

    The data globs are the label globs with the label suffix swapped for ``.*``,
    kept when the suffix is one of :data:`pds4._IMG_SUFFIXES`. A data file is
    labelled when a found label resolved to it or sits next to it with its stem.
    """
    stems = {(p.parent, p.stem.lower()) for p in labels}
    found: set[Path] = set()
    for pattern in SEARCH_GLOBS[instrument]:
        for p in raw_root.glob(pattern.rsplit(".", 1)[0] + ".*"):
            if p.suffix.lower() in _IMG_SUFFIXES and p.is_file():
                found.add(p)
    return sorted(p for p in found if p not in images and (p.parent, p.stem.lower()) not in stems)


def _fit_sample(head: str, path: str, error: str) -> str:
    """``"<head> <path>: <error>"`` within :data:`_SAMPLE_MAX` characters.

    The error is kept whole (up to 120 chars); the path is cut from the left so
    the file name survives (ScanDiagnostics would otherwise cut the error off).
    """
    error = error if len(error) <= 120 else error[:117] + "..."
    room = _SAMPLE_MAX - len(head) - len(error) - 3
    if len(path) > room:
        keep = room - 3
        path = "..." + (path[-keep:] if keep > 0 else "")
    return f"{head} {path}: {error}"[:_SAMPLE_MAX]


def _any_dir(raw_root: Path, instrument: str) -> bool:
    return any(p.is_dir() for pattern in SEARCH_DIRS[instrument] for p in raw_root.glob(pattern))


def build_catalog(raw_root="data/raw", instruments=INSTRUMENTS) -> ProductCatalog:
    """Catalog every instrument's labels under ``raw_root``. Never raises for missing data."""
    raw_root = Path(raw_root)
    diag = ScanDiagnostics()
    entries: list[CatalogEntry] = []
    status: dict[str, InstrumentStatus] = {}
    unlabelled: dict[str, list[Path]] = {}
    if not raw_root.is_dir():
        diag.record(ScanStatus.ROOT_MISSING, f"{raw_root}: no such directory")

    for inst in instruments:
        if inst not in SEARCH_GLOBS:
            raise ValueError(f"unknown instrument {inst!r}; expected one of {INSTRUMENTS}")
        labels = _labels(raw_root, inst) if raw_root.is_dir() else []
        if not labels:
            has_dir = raw_root.is_dir() and _any_dir(raw_root, inst)
            if has_dir:
                orphans = _unlabelled_data(raw_root, inst, [], set())
                if orphans:
                    unlabelled[inst] = orphans
            status[inst] = InstrumentStatus.PARTIAL if has_dir else InstrumentStatus.ABSENT
            continue

        unreadable = missing = 0
        images: set[Path] = set()
        for label in labels:
            try:
                image = _minimal_read(label)
            except Exception as exc:  # noqa: BLE001 - any label error is UNREADABLE, never a crash
                unreadable += 1
                rel = label.relative_to(raw_root).as_posix()
                diag.record(
                    ScanStatus.PARSE_ERROR, _fit_sample(inst, rel, f"{type(exc).__name__}: {exc}")
                )
                continue
            kind = product_type_of(label)
            diag.record(
                ScanStatus.PARSED if kind == "data" else ScanStatus.NOT_A_DATA_PRODUCT,
                f"{inst} {label}" + ("" if kind == "data" else f": product_type={kind}"),
            )
            missing += image is None
            if image is not None:
                images.add(image)
            entries.append(
                CatalogEntry(
                    instrument=inst,
                    product_id=label.stem,
                    label_path=label,
                    image_path=image,
                    level=_level(inst, label.stem),
                    product_type=kind,
                    geometry_grid_path=_geometry_grid(label) if inst in _CH2 else None,
                )
            )
        orphans = _unlabelled_data(raw_root, inst, labels, images)
        if orphans:
            unlabelled[inst] = orphans
        if unreadable:
            status[inst] = InstrumentStatus.UNREADABLE
        elif missing or orphans:
            status[inst] = InstrumentStatus.PARTIAL
        else:
            status[inst] = InstrumentStatus.PRESENT

    logger.info(
        "catalog of %s: %s; %s; unlabelled data files: %s",
        raw_root,
        {k: v.value for k, v in status.items()},
        diag.counts,
        {k: len(v) for k, v in unlabelled.items()},
    )
    catalog = ProductCatalog(entries=entries, status=status, diagnostics=diag)
    catalog.unlabelled_data = unlabelled
    return catalog
