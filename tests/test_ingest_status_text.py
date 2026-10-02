"""The ingest docstrings/comments state the verified status the code actually applies (A116)."""

from __future__ import annotations

from pathlib import Path

import lunar_reg.ingest.manifest as manifest_mod
from lunar_reg.ingest import fieldmap
from lunar_reg.ingest.fieldmap import FIELDS_BY_NAME, Provenance
from lunar_reg.ingest.lro import PDS3_GEOMETRY_KEYS_UNVERIFIED, LROProduct


def _lro(resolved: dict[str, str]) -> LROProduct:
    return LROProduct(label_path=Path("x.LBL"), image_path=None, fmt="pds3", resolved=resolved)


def test_lro_geometry_resolved_counts_emission_and_phase():
    """The manifest docstring says LRO rows count all five PDS3 keys, emission/phase included."""
    assert set(PDS3_GEOMETRY_KEYS_UNVERIFIED) >= {"emission_angle_deg", "phase_angle_deg"}
    for key in PDS3_GEOMETRY_KEYS_UNVERIFIED:
        assert _lro({key: "X"}).geometry_resolved, key
    assert not _lro({}).geometry_resolved


def test_manifest_docstring_separates_pds4_and_pds3_rows():
    doc = manifest_mod.__doc__ or ""
    assert "PDS3_GEOMETRY_KEYS_UNVERIFIED" in doc
    assert "LRO (PDS3) rows" in doc
    assert "Chandrayaan-2 (PDS4) rows" in doc


def test_fieldmap_comment_matches_incidence_status():
    """Incidence is VERIFIED in code; the geometry comment must not list it as UNVERIFIED."""
    assert FIELDS_BY_NAME["incidence_angle_deg"].provenance is Provenance.VERIFIED
    src = Path(fieldmap.__file__).read_text()
    assert "Three fields did NOT resolve and remain UNVERIFIED" not in src
    unverified_geometry = {
        f.name for f in fieldmap.GEOMETRY_FIELDS if f.provenance is not Provenance.VERIFIED
    }
    assert unverified_geometry == {"emission_angle_deg", "phase_angle_deg"}
    assert "Two fields\n# remain UNVERIFIED: emission and phase angle" in src
