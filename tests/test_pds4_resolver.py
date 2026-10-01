"""PDS4 label resolver: document order, predicate segments, coercion failures, path containment."""

from __future__ import annotations

from pathlib import Path

import pytest

from lunar_reg.ingest.fieldmap import Field, Provenance
from lunar_reg.ingest.pds4 import read_label, resolve_contained

REPO = Path(__file__).resolve().parents[1]

LABEL = """<?xml version="1.0" encoding="UTF-8"?>
<Product_Observational xmlns="http://pds.nasa.gov/pds4/pds/v1">
  <Observation_Area>
    <Observing_System>
      <Observing_System_Component>
        <name>Chandrayaan-2 Orbiter</name><type>Spacecraft</type>
      </Observing_System_Component>
      <Observing_System_Component>
        <name>Test Camera</name><type>Instrument</type>
      </Observing_System_Component>
    </Observing_System>
    <Block><x>1</x></Block>
    <Block><x>2</x></Block>
    <Numbers><g>abc</g></Numbers>
  </Observation_Area>
  <File_Area_Observational><File><file_name>{file_name}</file_name></File></File_Area_Observational>
</Product_Observational>
"""

FIELDS = (
    Field("x", ("Block/x",), Provenance.VERIFIED, dtype="int"),
    Field("g", ("Numbers/g",), Provenance.VERIFIED, dtype="float"),
    Field(
        "instrument",
        ("Observing_System_Component[type=Instrument]/name", "Observing_System_Component/name"),
        Provenance.DOCUMENTED,
    ),
    Field("first_component", ("Observing_System_Component/name",), Provenance.DOCUMENTED),
    Field("file_name", ("File/file_name",), Provenance.VERIFIED),
    Field("absent", ("Nowhere/nothing",), Provenance.UNVERIFIED),
)


def _write_label(tmp_path: Path, file_name: str = "img.img") -> Path:
    label = tmp_path / "product" / "p.xml"
    label.parent.mkdir(parents=True, exist_ok=True)
    label.write_text(LABEL.format(file_name=file_name))
    (label.parent / "img.img").write_bytes(b"\0")
    return label


def test_first_match_in_document_order(tmp_path):
    p = read_label(_write_label(tmp_path), fields=FIELDS)
    assert p["x"] == 1
    assert p["first_component"] == "Chandrayaan-2 Orbiter"


def test_predicate_selects_the_instrument_component(tmp_path):
    p = read_label(_write_label(tmp_path), fields=FIELDS)
    assert p["instrument"] == "Test Camera"
    assert p.resolved["instrument"] == "Observing_System_Component[type=Instrument]/name"


def test_predicate_falls_back_to_next_path_when_nothing_matches(tmp_path):
    fields = (
        Field(
            "instrument",
            ("Observing_System_Component[type=Rover]/name", "Observing_System_Component/name"),
            Provenance.DOCUMENTED,
        ),
    )
    p = read_label(_write_label(tmp_path), fields=fields)
    assert p["instrument"] == "Chandrayaan-2 Orbiter"
    assert p.resolved["instrument"] == "Observing_System_Component/name"


@pytest.mark.parametrize("path", ["A[b/c", "A[b]/c", "A[=v]/c", "A//c", "A]/c"])
def test_malformed_predicate_rejected_at_field_construction(path):
    with pytest.raises(ValueError):
        Field("bad", (path,), Provenance.VERIFIED)


def test_coercion_failure_recorded_separately(tmp_path):
    p = read_label(_write_label(tmp_path), fields=FIELDS)
    assert p.coerce_failed == {"g": "abc"}
    assert "g" not in p.resolved
    assert "g" not in p.unresolved
    assert p["g"] is None
    assert p.unresolved == ["absent"]


def test_manifest_row_lists_coercion_failures_after_unresolved(tmp_path):
    from lunar_reg.ingest.manifest import product_to_row

    p = read_label(_write_label(tmp_path), fields=FIELDS)
    assert product_to_row(p)["unresolved_fields"] == "absent,g(coerce_failed)"


@pytest.mark.parametrize("name", ["../x.img", "/etc/passwd", "sub/../../evil.img"])
def test_data_file_outside_product_directory_rejected(tmp_path, name):
    label = _write_label(tmp_path, name)
    p = read_label(label, fields=FIELDS)
    assert p.image_path is None
    assert p.image_path_rejected == name
    assert resolve_contained(label, name) is None


def test_data_file_inside_product_directory_accepted(tmp_path):
    label = _write_label(tmp_path)
    p = read_label(label, fields=FIELDS)
    assert p.image_path == label.parent / "img.img"
    assert p.image_path_rejected is None


def test_pds3_pointer_outside_directory_rejected(tmp_path):
    from lunar_reg.ingest.lro import _pds3_image_path

    label = tmp_path / "nac.lbl"
    assert _pds3_image_path(label, {"^IMAGE": '("../../evil.img", 1)'}) is None
    assert _pds3_image_path(label, {"^IMAGE": '("nac.img", 1)'}) == tmp_path / "nac.img"


@pytest.mark.data
def test_real_ohrc_label_resolves_camera_and_system_level_corners():
    labels = sorted(REPO.glob("data/raw/ohrc_vikram/*/data/raw/*/*_d_img_*.xml"))
    if not labels:
        pytest.skip("no OHRC labels under data/raw/ohrc_vikram")
    p = read_label(labels[0])
    assert p["instrument"] == "orbiter high resolution camera"
    assert p.resolved["corner1_lat"].startswith("System_Level_Coordinates/")
    assert p.image_path is not None and p.image_path.exists()
    assert p.coerce_failed == {}
