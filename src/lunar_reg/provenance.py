"""Shared provenance for every new number (CONTRACTS C01, DECISIONS G17).

Any numeric value this project adds from now on -- a constant, a measured
result, a threshold -- carries a :class:`ValueSource` saying where it came from:
measured by a run here, computed from such inputs, documented externally,
inferred, or unknown. The older per-module enums (``fieldmap.Provenance``,
``params.ParamSource``, ``pseudo_gt.TermSource``) stay as they are; this enum is
for new values, so provenance lives in code rather than in comments.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ValueSource(str, Enum):
    MEASURED = "measured"  # a run on this project's data or hardware produced it
    COMPUTED = "computed"  # derived deterministically from measured/documented inputs
    DOCUMENTED = "documented"  # read from a cited external document or archive metadata
    INFERRED = "inferred"  # a fit or reasoning step, not documented
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Sourced:
    value: float | int | str | None
    source: ValueSource
    note: str = ""

    def as_dict(self) -> dict:
        return {"value": self.value, "source": self.source.value, "note": self.note}
