"""Product catalog + classified label scans (P1.03, Phase_1/LLD/catalog.md §4)."""

from __future__ import annotations

import json

import numpy as np
import pytest

from lunar_reg.ingest.catalog import INSTRUMENTS, InstrumentStatus, build_catalog
from lunar_reg.ingest.manifest import ScanStatus, product_type_of, scan_directory

PDS4_NS = "http://pds.nasa.gov/pds4/pds/v1"


def _label(file_name: str = "test.img") -> str:
    """Minimal documented PDS4 Product_Observational layout (as in test_ingest_labels.py)."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Product_Observational xmlns="{PDS4_NS}">
  <Identification_Area>
    <logical_identifier>urn:isro:isda:ch2_ohr:test_0001</logical_identifier>
    <version_id>1.0</version_id>
  </Identification_Area>
  <Observation_Area>
    <Time_Coordinates>
      <start_date_time>2024-04-25T14:06:01.000Z</start_date_time>
      <stop_date_time>2024-04-25T14:06:18.000Z</stop_date_time>
    </Time_Coordinates>
  </Observation_Area>
  <File_Area_Observational>
    <File><file_name>{file_name}</file_name></File>
    <Array_2D_Image>
      <offset unit="byte">0</offset>
      <axes>2</axes>
      <axis_index_order>Last Index Fastest</axis_index_order>
      <Element_Array><data_type>UnsignedByte</data_type></Element_Array>
      <Axis_Array><axis_name>Line</axis_name><elements>12</elements>
        <sequence_number>1</sequence_number></Axis_Array>
      <Axis_Array><axis_name>Sample</axis_name><elements>10</elements>
        <sequence_number>2</sequence_number></Axis_Array>
    </Array_2D_Image>
  </File_Area_Observational>
</Product_Observational>
"""


def _ohrc(root, level="nrp", tag="20240425T1406019344", image=True, broken=False):
    stem = f"ch2_ohr_{level}_{tag}_d_img_d18"
    parent = "ohrc_vikram" if level == "nrp" else "ch2/ohrc"
    sub = "raw" if level == "nrp" else "calibrated"
    d = root / parent / stem / "data" / sub / tag[:8]
    d.mkdir(parents=True)
    label = d / f"{stem}.xml"
    label.write_text("<broken" if broken else _label(f"{stem}.img"))
    if image:
        (d / f"{stem}.img").write_bytes(np.zeros(120, np.uint8).tobytes())
    return label


# ------------------------------------------------------------ product_type_of


@pytest.mark.parametrize(
    "name,expected",
    [
        ("ch2_ohr_ncp_20240425T1406019344_d_img_d18.xml", "data"),
        ("CH2_OHR_NCP_20240425T1406019344_D_IMG_D18.XML", "data"),
        ("ch2_iir_nci_20230125T1944138897_d_cub_d32.xml", "data"),
        ("ch2_ohr_ncp_20240425T1406019344_b_brw_d18.xml", "browse"),
        ("ch2_ohr_ncp_20240425T1406019344_g_grd_d18.xml", "geometry"),
        ("ch2_tmc_ndn_20231027T1315134884_d_dtm_d18.xml", "other"),
        ("NAC_DTM_VIKRAMSITE1_M1442997156_100CM.xml", "data"),
        ("NAC_DTM_VIKRAMSITE1.xml", "other"),
        ("TCO_MAP_02_S66E030S69E033SC.lbl", "data"),
        ("readme.xml", "other"),
        # first match wins: browse before data
        ("x_b_brw_d_img_.xml", "browse"),
    ],
)
def test_product_type_of(name, expected, tmp_path):
    assert product_type_of(tmp_path / name) == expected


# ------------------------------------------------------------ scan diagnostics


def test_scan_counts_browse_as_not_a_data_product(tmp_path):
    (tmp_path / "ch2_ohr_ncp_20240425T1406019344_d_img_d18.xml").write_text(_label())
    (tmp_path / "ch2_ohr_ncp_20240425T1406019344_b_brw_d18.xml").write_text(_label())
    frame, diag = scan_directory(tmp_path, with_diagnostics=True)
    assert len(frame) == 1
    assert list(frame["product_type"]) == ["data"]
    assert diag.counts == {"parsed": 1, "not_a_data_product": 1}
    assert "not_a_data_product" in diag.report()
    assert not ScanStatus.NOT_A_DATA_PRODUCT.is_failure
    assert ScanStatus.ROOT_MISSING.is_failure


def test_scan_root_missing_is_classified(tmp_path):
    frame, diag = scan_directory(tmp_path / "nope", with_diagnostics=True)
    assert len(frame) == 0
    assert diag.counts == {"root_missing": 1}
    assert "root_missing" in diag.report()


def test_lro_scan_with_diagnostics(tmp_path):
    from lunar_reg.ingest.lro import scan_lro_directory

    (tmp_path / "readme.xml").write_text("<x/>")
    frame, diag = scan_lro_directory(tmp_path, with_diagnostics=True)
    assert len(frame) == 0 and diag.counts == {"not_a_data_product": 1}
    _, missing = scan_lro_directory(tmp_path / "nope", with_diagnostics=True)
    assert missing.counts == {"root_missing": 1}


# ------------------------------------------------------------ catalog


def test_empty_root_every_instrument_absent(tmp_path, capsys):
    from lunar_reg.cli import main

    cat = build_catalog(tmp_path)
    assert set(cat.status) == set(INSTRUMENTS)
    assert all(s is InstrumentStatus.ABSENT for s in cat.status.values())
    assert cat.entries == []
    assert main(["catalog", "--raw-root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert all(f"{inst}: absent" in out for inst in INSTRUMENTS)


def test_missing_root_is_absent_and_counted(tmp_path):
    cat = build_catalog(tmp_path / "nope")
    assert all(s is InstrumentStatus.ABSENT for s in cat.status.values())
    assert cat.diagnostics.counts == {"root_missing": 1}


@pytest.mark.parametrize("level,expected", [("nrp", "raw"), ("ncp", "calibrated")])
def test_ohrc_present_with_level(tmp_path, level, expected):
    _ohrc(tmp_path, level)
    cat = build_catalog(tmp_path)
    assert cat.status["OHRC"] is InstrumentStatus.PRESENT
    (entry,) = cat.products("OHRC")
    assert entry.level == expected and entry.product_type == "data"
    assert entry.image_path is not None and entry.image_path.exists()
    assert cat.diagnostics.counts == {"parsed": 1}
    assert cat.status["TMC2"] is InstrumentStatus.ABSENT


def test_label_without_image_is_partial(tmp_path):
    _ohrc(tmp_path, "nrp", image=False)
    cat = build_catalog(tmp_path)
    assert cat.status["OHRC"] is InstrumentStatus.PARTIAL
    assert cat.products("OHRC")[0].image_path is None
    assert "data file missing" in cat.report()


def test_directory_without_labels_is_partial(tmp_path):
    (tmp_path / "ch2/tmc2").mkdir(parents=True)
    assert build_catalog(tmp_path).status["TMC2"] is InstrumentStatus.PARTIAL


def test_malformed_label_is_unreadable_and_cli_exits_1(tmp_path, capsys):
    from lunar_reg.cli import main

    _ohrc(tmp_path, "nrp", broken=True)
    cat = build_catalog(tmp_path)
    assert cat.status["OHRC"] is InstrumentStatus.UNREADABLE
    assert cat.diagnostics.counts == {"parse_error": 1}
    assert "ch2_ohr_nrp" in cat.diagnostics.samples["parse_error"]
    assert main(["catalog", "--raw-root", str(tmp_path)]) == 1
    assert "parse_error" in capsys.readouterr().out


def test_tmc2_levels_and_non_data_types(tmp_path):
    base = tmp_path / "ch2/tmc2"
    for stem, ext in [
        ("ch2_tmc_ncn_20230521T0857294318_d_img_d32", "img"),
        ("ch2_tmc_nrn_20230521T0857294318_d_img_d32", "img"),
        ("ch2_tmc_ndn_20231027T1315134884_d_dtm_d18", "tif"),
    ]:
        d = base / stem / "data/x/20230521"
        d.mkdir(parents=True)
        (d / f"{stem}.xml").write_text(_label(f"{stem}.{ext}"))
        (d / f"{stem}.{ext}").write_bytes(b"\0" * 120)
    cat = build_catalog(tmp_path)
    assert cat.status["TMC2"] is InstrumentStatus.PRESENT
    levels = {e.product_id.split("_")[2]: e.level for e in cat.products("TMC2")}
    assert levels == {"ncn": "calibrated", "nrn": "raw"}
    (dtm,) = cat.products("TMC2", product_type="other")
    assert dtm.level == "derived"
    assert dtm.level_source == "inferred_from_filename"
    assert cat.diagnostics.counts == {"parsed": 2, "not_a_data_product": 1}


def test_selene_pds3_label(tmp_path):
    d = tmp_path / "reference/selene_tc_ortho"
    d.mkdir(parents=True)
    (d / "TCO_MAP_02_S66E030S69E033SC.lbl").write_text('PDS_VERSION_ID = "PDS3"\n')
    (d / "TCO_MAP_02_S66E030S69E033SC.img").write_bytes(b"\0" * 16)
    cat = build_catalog(tmp_path)
    assert cat.status["SELENE_TC"] is InstrumentStatus.PRESENT
    (entry,) = cat.products("SELENE_TC")
    assert entry.level == "derived" and entry.geometry_grid_path is None
    (d / "TCO_MAP_02_S66E030S69E033SC.lbl").write_text("")
    assert build_catalog(tmp_path).status["SELENE_TC"] is InstrumentStatus.UNREADABLE


def test_geometry_grid_matched_by_timestamp(tmp_path):
    label = _ohrc(tmp_path, "ncp")
    grid_dir = label.parents[3] / "geometry/calibrated/20240425"
    grid_dir.mkdir(parents=True)
    (grid_dir / "ch2_ohr_ncp_20990101T0000000000_g_grd_d18.csv").write_text("x")
    assert build_catalog(tmp_path).products("OHRC")[0].geometry_grid_path is None
    (grid_dir / "ch2_ohr_ncp_20240425T1406019344_g_grd_d18.csv").write_text("x")
    grid = build_catalog(tmp_path).products("OHRC")[0].geometry_grid_path
    assert grid is not None and "20240425T1406019344" in grid.name


def test_cli_json(tmp_path, capsys):
    from lunar_reg.cli import main

    _ohrc(tmp_path, "nrp")
    out = tmp_path / "out/catalog.json"
    assert main(["catalog", "--raw-root", str(tmp_path), "--json", str(out)]) == 0
    doc = json.loads(out.read_text())
    assert set(doc) == {"status", "entries"}
    assert doc["status"]["OHRC"] == "present" and doc["status"]["IIRS"] == "absent"
    (entry,) = doc["entries"]
    assert isinstance(entry["label_path"], str) and entry["level"] == "raw"
    assert "OHRC: present, 1 product(s)" in capsys.readouterr().out


# ------------------------------------------------------------ review fixes


def test_data_file_without_label_is_partial(tmp_path):
    # C09: PARTIAL = labels without their data file "(or the reverse)" -- one
    # complete product plus an unlabelled data file must not read PRESENT.
    _ohrc(tmp_path, "nrp")
    stem = "ch2_ohr_nrp_20240426T0000000000_d_img_d18"
    d = tmp_path / "ohrc_vikram" / stem / "data/raw/20240426"
    d.mkdir(parents=True)
    (d / f"{stem}.img").write_bytes(b"\0" * 16)
    cat = build_catalog(tmp_path)
    assert cat.status["OHRC"] is InstrumentStatus.PARTIAL
    assert [p.name for p in cat.unlabelled_data["OHRC"]] == [f"{stem}.img"]
    assert "label missing next to 1 data file(s)" in cat.report()
    assert cat.status["TMC2"] is InstrumentStatus.ABSENT


def test_unlabelled_data_file_alone_is_partial_with_detail(tmp_path):
    d = tmp_path / "reference/selene_tc_ortho"
    d.mkdir(parents=True)
    (d / "TCO_MAP_02_S66E030S69E033SC.img").write_bytes(b"\0" * 16)
    cat = build_catalog(tmp_path)
    assert cat.status["SELENE_TC"] is InstrumentStatus.PARTIAL
    assert "TCO_MAP_02_S66E030S69E033SC.img" in cat.report()


def test_labelled_data_files_are_not_unlabelled(tmp_path):
    _ohrc(tmp_path, "nrp")
    _ohrc(tmp_path, "ncp")
    cat = build_catalog(tmp_path)
    assert cat.status["OHRC"] is InstrumentStatus.PRESENT
    assert cat.unlabelled_data == {}


def test_pds3_non_utf8_after_first_line_is_readable(tmp_path):
    # LLD §2: the PDS3 minimal read is existence + first line only.
    d = tmp_path / "reference/selene_tc_ortho"
    d.mkdir(parents=True)
    (d / "TCO_MAP_02_X.lbl").write_bytes(
        b'PDS_VERSION_ID = PDS3\r\nNOTE = "sun at 30\xb0 elevation"\r\nEND\r\n'
    )
    (d / "TCO_MAP_02_X.img").write_bytes(b"\0" * 16)
    cat = build_catalog(tmp_path)
    assert cat.status["SELENE_TC"] is InstrumentStatus.PRESENT
    assert cat.diagnostics.counts == {"parsed": 1}


def test_parse_error_sample_keeps_error_and_file_name(tmp_path):
    # A long absolute raw root used to push the error past the 200-char cut.
    root = tmp_path / ("deep_" * 30) / "raw"
    _ohrc(root, "ncp", broken=True)
    cat = build_catalog(root)
    sample = cat.diagnostics.samples["parse_error"]
    assert len(sample) <= 200
    assert sample.startswith("OHRC ")
    assert "ParseError" in sample
    assert "ch2_ohr_ncp_20240425T1406019344_d_img_d18.xml" in sample
    assert str(root) not in sample  # path is relative to raw_root
