"""Label parsing, manifest building, and the provenance machinery.

The PDS4/PDS3 fixtures here are hand-written to the *documented* schemas, and
those same schemas were confirmed readable by GDAL's independent PDS4 and PDS
drivers during development. So these tests validate the parser against the
standard.

They do NOT validate mission-specific geometry field names. No real
Chandrayaan-2 or LRO product has been inspected. The synthetic labels below use
the placeholder names from ``fieldmap.py``, so a passing geometry test proves
the resolution *mechanism* works -- not that the names are right.
"""

from __future__ import annotations

import numpy as np
import pytest

from lunar_reg.ingest.fieldmap import ALL_FIELDS, Provenance
from lunar_reg.ingest.lro import PDS3, PDS4, detect_format, parse_pds3_keywords, read_lro_label
from lunar_reg.ingest.manifest import build_manifest, scan_directory
from lunar_reg.ingest.pds4 import PDS4_DTYPES, guess_sensor, read_label
from lunar_reg.ingest.probe import probe_label, suggest_fieldmap

PDS4_NS = "http://pds.nasa.gov/pds4/pds/v1"


def _pds4_label(
    lid="urn:isro:isda:ch2_ohr:test_0001",
    file_name="test.img",
    axes=(("Line", 12), ("Sample", 10)),
    array_kind="Array_2D_Image",
    data_type="UnsignedLSB2",
    geometry: dict | None = None,
) -> str:
    """A PDS4 label built to the documented Product_Observational schema."""
    axis_xml = "\n".join(
        f"      <Axis_Array><axis_name>{n}</axis_name>"
        f"<elements>{e}</elements><sequence_number>{i + 1}</sequence_number></Axis_Array>"
        for i, (n, e) in enumerate(axes)
    )
    geom_xml = ""
    if geometry:
        inner = "\n".join(f"      <{k}>{v}</{k}>" for k, v in geometry.items())
        geom_xml = f"    <Discipline_Area>\n{inner}\n    </Discipline_Area>"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Product_Observational xmlns="{PDS4_NS}">
  <Identification_Area>
    <logical_identifier>{lid}</logical_identifier>
    <version_id>1.0</version_id>
    <title>Test product</title>
    <information_model_version>1.11.0.0</information_model_version>
    <product_class>Product_Observational</product_class>
  </Identification_Area>
  <Observation_Area>
    <Time_Coordinates>
      <start_date_time>2021-03-31T04:12:33.123Z</start_date_time>
      <stop_date_time>2021-03-31T04:12:44.456Z</stop_date_time>
    </Time_Coordinates>
    <Target_Identification><name>Moon</name><type>Satellite</type></Target_Identification>
    <Observing_System>
      <Observing_System_Component><name>OHRC</name><type>Instrument</type></Observing_System_Component>
    </Observing_System>
{geom_xml}
  </Observation_Area>
  <File_Area_Observational>
    <File><file_name>{file_name}</file_name></File>
    <{array_kind}>
      <offset unit="byte">0</offset>
      <axes>{len(axes)}</axes>
      <axis_index_order>Last Index Fastest</axis_index_order>
      <Element_Array><data_type>{data_type}</data_type></Element_Array>
{axis_xml}
    </{array_kind}>
  </File_Area_Observational>
</Product_Observational>
"""


@pytest.fixture
def ohrc_label(tmp_path):
    path = tmp_path / "ch2_ohr_test.xml"
    path.write_text(_pds4_label())
    (tmp_path / "test.img").write_bytes(np.zeros(12 * 10, dtype="<u2").tobytes())
    return path


@pytest.fixture
def iirs_label(tmp_path):
    """A 3D cube label. Axis order is what defines interleave."""
    path = tmp_path / "ch2_iir_test.xml"
    path.write_text(
        _pds4_label(
            lid="urn:isro:isda:ch2_iir:test_0002",
            file_name="cube.img",
            axes=(("Band", 256), ("Line", 100), ("Sample", 250)),
            array_kind="Array_3D_Spectrum",
            data_type="IEEE754LSBSingle",
        )
    )
    return path


# --- structural parsing (validated against the documented schema) ----------


def test_reads_identification_and_structure(ohrc_label):
    p = read_label(ohrc_label)
    assert p.product_id == "urn:isro:isda:ch2_ohr:test_0001"
    assert (p.lines, p.samples, p.bands) == (12, 10, 1)
    assert p.array_kind == "Array_2D_Image"
    assert p.numpy_dtype == "<u2"


def test_resolves_the_data_file_from_the_label(ohrc_label):
    assert read_label(ohrc_label).image_path.name == "test.img"


def test_reads_acquisition_time_as_datetime(ohrc_label):
    start = read_label(ohrc_label)["start_time"]
    assert start is not None
    assert (start.year, start.month, start.day) == (2021, 3, 31)
    assert start.tzinfo is not None, "PDS4 times are UTC; tz must be preserved"


def test_hyperspectral_cube_reports_bands_and_axis_order(iirs_label):
    p = read_label(iirs_label)
    assert p.bands == 256
    assert p.is_hyperspectral
    assert (p.lines, p.samples) == (100, 250)
    assert p.axis_order == "Band,Line,Sample"


def test_axis_order_is_reported_not_assumed(tmp_path):
    """Interleave must come from the label.

    A band-sequential cube read as band-interleaved returns wrong pixels with
    no error -- demonstrated against GDAL during development. The loader
    therefore surfaces axis_order rather than defaulting to one.
    """
    path = tmp_path / "bip.xml"
    path.write_text(
        _pds4_label(
            file_name="c.img",
            axes=(("Line", 4), ("Sample", 5), ("Band", 6)),
            array_kind="Array_3D_Spectrum",
        )
    )
    p = read_label(path)
    assert p.axis_order == "Line,Sample,Band"
    assert p.bands == 6


@pytest.mark.parametrize("pds4_type,expected", list(PDS4_DTYPES.items()))
def test_documented_dtype_enumerations_map_to_numpy(pds4_type, expected, tmp_path):
    path = tmp_path / "d.xml"
    path.write_text(_pds4_label(data_type=pds4_type))
    assert read_label(path).numpy_dtype == expected
    np.dtype(expected)  # the mapping must be a dtype numpy accepts


def test_unknown_dtype_returns_none_rather_than_guessing(tmp_path):
    path = tmp_path / "u.xml"
    path.write_text(_pds4_label(data_type="SomeFutureType"))
    assert read_label(path).numpy_dtype is None


# --- provenance: the honesty machinery -------------------------------------


def test_geometry_is_unresolved_without_real_metadata(ohrc_label):
    """The expected state today: no illumination fields resolve."""
    p = read_label(ohrc_label)
    assert p.geometry_resolved is False
    assert p["sun_azimuth_deg"] is None
    assert "sun_azimuth_deg" in p.unresolved


def test_resolution_mechanism_works_when_a_path_matches(tmp_path):
    """Proves the resolver works -- NOT that these element names are correct.

    The names come from fieldmap's UNVERIFIED placeholders. A real label may
    use entirely different ones; that is what probe-label is for.
    """
    path = tmp_path / "g.xml"
    path.write_text(
        _pds4_label(geometry={"sub_solar_azimuth": "134.5", "incidence_angle": "62.1"})
    )
    p = read_label(path)
    assert p["sun_azimuth_deg"] == pytest.approx(134.5)
    assert p["incidence_angle_deg"] == pytest.approx(62.1)
    assert p.geometry_resolved is True
    assert p.resolved["sun_azimuth_deg"] == "sub_solar_azimuth"


def test_every_field_records_whether_it_resolved(ohrc_label):
    p = read_label(ohrc_label)
    assert set(p.resolved) | set(p.unresolved) == {f.name for f in ALL_FIELDS}
    assert not (set(p.resolved) & set(p.unresolved)), "a field cannot be both"


#: The geometry fields that are still guesses. Everything else in the geometry
#: block was confirmed on 2026-09-05 against a real Chandrayaan-2 OHRC label.
STILL_UNVERIFIED = {"emission_angle_deg", "phase_angle_deg"}


def test_only_the_genuinely_unconfirmed_geometry_fields_stay_unverified():
    """Guard: nobody may quietly promote a guess, in either direction.

    The original form of this test asserted that *every* geometry field was
    UNVERIFIED, which was right while no real product had been seen. A real OHRC
    label has now been probed and eleven of thirteen resolved, so the guard
    inverts: it pins exactly which two are still unconfirmed, so promoting them
    without evidence fails, and demoting a confirmed one also fails.
    """
    checked = 0
    for f in ALL_FIELDS:
        if not ("sun_" in f.name or "angle" in f.name or "corner" in f.name):
            continue
        checked += 1
        if f.name in STILL_UNVERIFIED:
            assert f.provenance is Provenance.UNVERIFIED, (
                f"{f.name} was not present in the reference OHRC label; only "
                f"probe-label output against a product that has it justifies "
                f"promoting it"
            )
        else:
            assert f.provenance is Provenance.VERIFIED, (
                f"{f.name} was confirmed against a real label and must stay "
                f"VERIFIED; if it was demoted, say why in the field note"
            )
    assert checked == 13, f"expected 13 geometry fields, found {checked}"


def test_isro_element_names_are_the_ones_the_real_label_uses():
    """Pins the element names observed in a real Chandrayaan-2 label.

    These are the names ISRO actually uses, recorded so a future edit cannot
    quietly revert to the plausible-but-wrong guesses they replaced. The most
    load-bearing one is `solar_incidence`: the original guess was
    `incidence_angle`, which silently resolved to None.
    """
    by_name = {f.name: f for f in ALL_FIELDS}
    assert "sun_azimuth" in by_name["sun_azimuth_deg"].paths
    assert "sun_elevation" in by_name["sun_elevation_deg"].paths
    assert "solar_incidence" in by_name["incidence_angle_deg"].paths
    assert "upper_left_latitude" in by_name["corner1_lat"].paths
    assert "lower_right_longitude" in by_name["corner4_lon"].paths


def test_corner_numbering_is_not_ring_order():
    """The real corner order is UL, UR, LL, LR -- traversing it makes a bow-tie.

    Measured on the reference OHRC label: numeric order gives 0.07 km^2, the
    correct traversal 78.89 km^2 for the same footprint, a factor of 1201. The
    physically expected area for a 3 km x 25 km OHRC strip is ~75 km^2, so the
    larger figure is the right one.

    `footprint_from_row` handles this by traversing 1, 2, 4, 3. This test exists
    so that reordering is never "simplified" back to 1, 2, 3, 4.
    """
    from lunar_reg.ingest.overlap import footprint_from_row

    row = {
        "product_id": "ref", "sensor": "OHRC", "label_path": "x", "image_path": "x",
        "lines": 101074, "samples": 12000,
        "corner1_lat": -85.323534, "corner1_lon": 27.723846,
        "corner2_lat": -85.365795, "corner2_lon": 26.571730,
        "corner3_lat": -84.552455, "corner3_lon": 24.029151,
        "corner4_lat": -84.588687, "corner4_lon": 23.016449,
    }
    area_km2 = footprint_from_row(row).area_m2() / 1e6
    assert 40.0 < area_km2 < 150.0, (
        f"footprint area {area_km2:.2f} km^2 is not physical for an OHRC strip; "
        f"the corner traversal has probably been reordered to 1,2,3,4"
    )


def test_malformed_axis_array_is_skipped_not_fatal(tmp_path):
    path = tmp_path / "bad.xml"
    path.write_text(
        _pds4_label().replace("<elements>10</elements>", "<elements>not-a-number</elements>")
    )
    p = read_label(path)
    assert p.lines == 12
    assert p.samples is None


@pytest.mark.parametrize(
    "text,expected",
    [("urn:isro:isda:ch2_ohr:x", "OHRC"), ("ch2_iir_nci", "IIRS"),
     ("ch2_tmc_ndn", "TMC2"), ("M1234_NAC_L", "LRO_NAC"), ("mystery", None)],
)
def test_sensor_inference_is_a_documented_heuristic(text, expected):
    assert guess_sensor(text) == expected


# --- PDS3 / LRO ------------------------------------------------------------

PDS3_LABEL = """PDS_VERSION_ID               = PDS3
RECORD_TYPE                  = FIXED_LENGTH
RECORD_BYTES                 = 10
^IMAGE                       = ("nac.img",1)
PRODUCT_ID                   = "M123456789LE"
INSTRUMENT_ID                = "NACL"
TARGET_NAME                  = "MOON"
START_TIME                   = 2011-05-04T12:33:21.123
OBJECT                       = IMAGE
  LINES                      = 52224
  LINE_SAMPLES               = 5064
  SAMPLE_TYPE                = LSB_UNSIGNED_INTEGER
  SAMPLE_BITS                = 16
END_OBJECT                   = IMAGE
END
"""


def test_detects_pds3_and_pds4_by_content_not_extension(tmp_path):
    (tmp_path / "a.lbl").write_text(PDS3_LABEL)
    (tmp_path / "b.xml").write_text(_pds4_label())
    # A PDS4 label deliberately given a PDS3-looking extension.
    (tmp_path / "c.lbl").write_text(_pds4_label())
    assert detect_format(tmp_path / "a.lbl") == PDS3
    assert detect_format(tmp_path / "b.xml") == PDS4
    assert detect_format(tmp_path / "c.lbl") == PDS4


def test_unrecognised_label_returns_none(tmp_path):
    (tmp_path / "x.lbl").write_text("this is not a planetary label\n")
    assert detect_format(tmp_path / "x.lbl") is None


def test_pds3_keyword_parsing_captures_everything(tmp_path):
    path = tmp_path / "n.lbl"
    path.write_text(PDS3_LABEL)
    kw = parse_pds3_keywords(path)
    assert kw["PRODUCT_ID"] == "M123456789LE"
    assert kw["LINES"] == "52224"
    assert kw["^IMAGE"] == '("nac.img",1)'


def test_pds3_parsing_stops_at_END_not_the_image_data(tmp_path):
    path = tmp_path / "attached.lbl"
    path.write_text(PDS3_LABEL + "\x00" * 100_000)
    assert "LINES" in parse_pds3_keywords(path)


def test_reads_lro_pds3_label(tmp_path):
    path = tmp_path / "nac.lbl"
    path.write_text(PDS3_LABEL)
    p = read_lro_label(path)
    assert p.fmt == PDS3
    assert p["product_id"] == "M123456789LE"
    assert (p["lines"], p["samples"]) == (52224, 5064)
    assert p.image_path.name == "nac.img"
    assert p["start_time"].year == 2011


def test_lro_geometry_also_starts_unresolved(tmp_path):
    path = tmp_path / "nac.lbl"
    path.write_text(PDS3_LABEL)
    p = read_lro_label(path)
    assert p.geometry_resolved is False
    assert p["sun_azimuth_deg"] is None


def test_lro_reader_accepts_a_pds4_label_too(tmp_path):
    path = tmp_path / "nac.xml"
    path.write_text(_pds4_label(lid="urn:nasa:pds:lro_nac:m123"))
    p = read_lro_label(path)
    assert p.fmt == PDS4
    assert p.sensor == "LRO_NAC"


def test_unreadable_format_raises_with_a_useful_message(tmp_path):
    path = tmp_path / "junk.lbl"
    path.write_text("nope\n")
    with pytest.raises(ValueError, match="unrecognised label format"):
        read_lro_label(path)


# --- manifest --------------------------------------------------------------


def test_manifest_round_trips_through_parquet(tmp_path, ohrc_label):
    from lunar_reg.ingest.manifest import read_manifest, write_manifest

    frame = build_manifest([read_label(ohrc_label)])
    out = write_manifest(frame, tmp_path / "m" / "manifest.parquet")
    back = read_manifest(out)
    assert len(back) == 1
    assert back.iloc[0]["product_id"] == "urn:isro:isda:ch2_ohr:test_0001"
    assert back.iloc[0]["lines"] == 12


def test_manifest_flags_unresolved_geometry(ohrc_label):
    frame = build_manifest([read_label(ohrc_label)])
    assert not frame.iloc[0]["geometry_resolved"]
    assert not frame.iloc[0]["footprint_resolved"]
    assert "sun_azimuth_deg" in frame.iloc[0]["unresolved_fields"]


def test_scan_directory_finds_labels_and_skips_bad_ones(tmp_path):
    # P1.03: only labels whose product_type_of is "data" are parsed
    (tmp_path / "good_d_img_d18.xml").write_text(_pds4_label())
    (tmp_path / "broken_d_img_d18.xml").write_text("<not-valid-xml")
    frame = scan_directory(tmp_path)
    assert len(frame) == 1


def test_scan_directory_strict_reraises(tmp_path):
    from xml.etree.ElementTree import ParseError

    (tmp_path / "broken_d_img_d18.xml").write_text("<not-valid-xml")
    with pytest.raises(ParseError):
        scan_directory(tmp_path, strict=True)


def test_empty_directory_yields_an_empty_but_typed_manifest(tmp_path):
    from lunar_reg.ingest.manifest import COLUMNS

    frame = scan_directory(tmp_path)
    assert len(frame) == 0
    assert list(frame.columns) == list(COLUMNS)


def test_ch2_and_lro_manifests_share_a_schema(tmp_path):
    from lunar_reg.ingest.lro import scan_lro_directory

    (tmp_path / "ch2").mkdir()
    (tmp_path / "ch2" / "a_d_img_d18.xml").write_text(_pds4_label())
    (tmp_path / "lro").mkdir()
    (tmp_path / "lro" / "n.lbl").write_text(PDS3_LABEL)

    ch2 = scan_directory(tmp_path / "ch2")
    lro = scan_lro_directory(tmp_path / "lro")
    assert list(ch2.columns) == list(lro.columns), "manifests must concatenate cleanly"

    import pandas as pd

    combined = pd.concat([ch2, lro], ignore_index=True)
    assert len(combined) == 2
    assert set(combined["archive"]) == {"chandrayaan2", "lro"}


# --- probe -----------------------------------------------------------------


def test_probe_finds_leaf_elements_with_full_paths(ohrc_label):
    elements = probe_label(ohrc_label)
    paths = {e.path for e in elements}
    assert any(p.endswith("Identification_Area/logical_identifier") for p in paths)
    assert any(p.endswith("File/file_name") for p in paths)


def test_probe_categorises_illumination_and_time(tmp_path):
    path = tmp_path / "g.xml"
    path.write_text(_pds4_label(geometry={"sub_solar_azimuth": "134.5"}))
    cats = {e.localname: e.category for e in probe_label(path)}
    assert cats["sub_solar_azimuth"] == "illumination"
    assert cats["start_date_time"] == "time"


def test_probe_suggests_a_fieldmap_block_from_real_paths(tmp_path):
    path = tmp_path / "g.xml"
    path.write_text(
        _pds4_label(geometry={"sub_solar_azimuth": "134.5", "incidence_angle": "62.1"})
    )
    block = suggest_fieldmap(path)
    assert "GEOMETRY_FIELDS" in block
    assert "sub_solar_azimuth" in block
    assert "Provenance.VERIFIED" in block
    # Fields genuinely absent must be flagged, not fabricated.
    assert "phase_angle_deg: NOT FOUND" in block
