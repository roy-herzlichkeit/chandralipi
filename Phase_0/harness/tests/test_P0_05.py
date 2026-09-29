"""P0.05 — PDS4 resolver document order (Phase_0/LLD/pds4_resolver.md). Protected (G05)."""

from __future__ import annotations

import pytest
from _h0 import ohrc_labels

LABEL = """<?xml version="1.0" encoding="UTF-8"?>
<Product_Observational xmlns="http://pds.nasa.gov/pds4/pds/v1">
  <Observation_Area>
    <Observing_System>
      <Observing_System_Component><name>Craft</name><type>Spacecraft</type></Observing_System_Component>
      <Observing_System_Component><name>Camera</name><type>Instrument</type></Observing_System_Component>
    </Observing_System>
    <Block><x>1</x></Block>
    <Block><x>2</x></Block>
    <Numbers><y>abc</y></Numbers>
  </Observation_Area>
  <File_Area_Observational><File><file_name>{file_name}</file_name></File></File_Area_Observational>
</Product_Observational>
"""


def _label(tmp_path, file_name="img.img"):
    path = tmp_path / "product" / "p.xml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(LABEL.format(file_name=file_name))
    (path.parent / "img.img").write_bytes(b"\0")
    return path


def _fields(*extra):
    from lunar_reg.ingest.fieldmap import Field, Provenance

    return (
        Field("x", ("Block/x",), Provenance.VERIFIED, dtype="int"),
        Field("g", ("Numbers/y",), Provenance.VERIFIED, dtype="float"),
        Field("instrument", ("Observing_System_Component[type=Instrument]/name",
                             "Observing_System_Component/name"), Provenance.DOCUMENTED),
        Field("plain", ("Observing_System_Component/name",), Provenance.DOCUMENTED),
        Field("file_name", ("File/file_name",), Provenance.VERIFIED),
        *extra,
    )


def test_first_match_in_document_order(tmp_path):
    from lunar_reg.ingest.pds4 import read_label

    p = read_label(_label(tmp_path), fields=_fields())
    assert p["x"] == 1
    assert p["plain"] == "Craft"


def test_predicate_segment(tmp_path):
    from lunar_reg.ingest.pds4 import read_label

    p = read_label(_label(tmp_path), fields=_fields())
    assert p["instrument"] == "Camera"
    assert p.resolved["instrument"] == "Observing_System_Component[type=Instrument]/name"


def test_malformed_predicate_rejected():
    from lunar_reg.ingest.fieldmap import Field, Provenance

    with pytest.raises(ValueError):
        Field("bad", ("A[b/c",), Provenance.VERIFIED)
    with pytest.raises(ValueError):
        Field("bad", ("A[b]/c",), Provenance.VERIFIED)


def test_coerce_failure_recorded(tmp_path):
    from lunar_reg.ingest.pds4 import read_label

    p = read_label(_label(tmp_path), fields=_fields())
    assert p.coerce_failed == {"g": "abc"}
    assert "g" not in p.resolved and "g" not in p.unresolved
    assert p["g"] is None


@pytest.mark.parametrize("name", ["../evil.img", "/etc/passwd", "sub/../../evil.img"])
def test_image_path_contained(tmp_path, name):
    from lunar_reg.ingest.pds4 import read_label, resolve_contained

    p = read_label(_label(tmp_path, name), fields=_fields())
    assert p.image_path is None
    assert p.image_path_rejected == name
    assert resolve_contained(tmp_path / "product" / "p.xml", name) is None


def test_image_path_normal(tmp_path):
    from lunar_reg.ingest.pds4 import read_label, resolve_contained

    label = _label(tmp_path)
    p = read_label(label, fields=_fields())
    assert p.image_path == label.parent / "img.img"
    assert p.image_path_rejected is None
    assert resolve_contained(label, "img.img") == label.parent / "img.img"


def test_fieldmap_paths():
    from lunar_reg.ingest.fieldmap import FIELDS_BY_NAME

    assert FIELDS_BY_NAME["instrument"].paths[0] == \
        "Observing_System_Component[type=Instrument]/name"
    assert FIELDS_BY_NAME["corner1_lat"].paths[0] == \
        "System_Level_Coordinates/upper_left_latitude"
    assert FIELDS_BY_NAME["corner4_lon"].paths[0] == \
        "System_Level_Coordinates/lower_right_longitude"


@pytest.mark.data
def test_real_ohrc_label():
    labels = ohrc_labels()
    if not labels:
        pytest.skip("no OHRC labels under data/raw/ohrc_vikram")
    from lunar_reg.ingest.pds4 import read_label

    p = read_label(labels[0])
    assert p["instrument"] == "orbiter high resolution camera"
    assert p.resolved["corner1_lat"].startswith("System_Level_Coordinates/")
    assert p.image_path is not None and p.image_path.exists()
