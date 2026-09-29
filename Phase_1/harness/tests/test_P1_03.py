"""P1.03 — catalog + scan diagnostics (Phase_1/LLD/catalog.md). Protected (G05)."""

from __future__ import annotations

import numpy as np
import pytest
from _h1 import pds4_label


@pytest.mark.parametrize("name,expected", [
    ("ch2_ohr_ncp_20240425T1406019344_d_img_d18.xml", "data"),
    ("ch2_ohr_ncp_20240425T1406019344_b_brw_d18.xml", "browse"),
    ("ch2_ohr_ncp_20240425T1406019344_g_grd_d18.xml", "geometry"),
    ("NAC_DTM_VIKRAMSITE1_M1442997156_100CM.xml", "data"),
    ("TCO_MAP_02_S66E030S69E033SC.lbl", "data"),
    ("readme.xml", "other"),
])
def test_product_type_of(name, expected, tmp_path):
    from lunar_reg.ingest.manifest import product_type_of

    assert product_type_of(tmp_path / name) == expected


def test_scan_with_diagnostics(tmp_path):
    from lunar_reg.ingest.manifest import COLUMNS, ScanStatus, scan_directory

    d = tmp_path / "p"
    d.mkdir()
    (d / "ch2_ohr_ncp_20240425T1406019344_d_img_d18.xml").write_text(
        pds4_label(file_name="x.img"))
    (d / "ch2_ohr_ncp_20240425T1406019344_b_brw_d18.xml").write_text(pds4_label())
    (d / "ch2_ohr_ncp_20240425T1406019344_d_img_n18.xml").write_text("<broken")
    frame, diag = scan_directory(d, with_diagnostics=True)
    assert len(frame) == 1 and "product_type" in COLUMNS and COLUMNS[-1] == "product_type"
    assert diag.counts == {"parsed": 1, "not_a_data_product": 1, "parse_error": 1}
    assert ScanStatus.PARSE_ERROR.is_failure and not ScanStatus.NOT_A_DATA_PRODUCT.is_failure
    _, missing = scan_directory(tmp_path / "nope", with_diagnostics=True)
    assert missing.counts == {"root_missing": 1}
    assert len(scan_directory(d)) == 1  # default return type unchanged


def _ohrc(root, level="nrp", image=True, broken=False):
    stem = f"ch2_ohr_{level}_20230823T1450475804_d_img_n18"
    base = root / ("ohrc_vikram" if level == "nrp" else "ch2/ohrc") / stem / "data/raw/20230823"
    base.mkdir(parents=True)
    (base / f"{stem}.xml").write_text("<broken" if broken else pds4_label(file_name=f"{stem}.img"))
    if image:
        (base / f"{stem}.img").write_bytes(np.zeros(120, np.uint8).tobytes())
    return base


def test_catalog_levels_partial_unreadable(tmp_path):
    from lunar_reg.ingest.catalog import InstrumentStatus, build_catalog

    _ohrc(tmp_path, "nrp")
    cat = build_catalog(tmp_path)
    assert cat.status["OHRC"] is InstrumentStatus.PRESENT
    assert cat.products("OHRC")[0].level == "raw"
    _ohrc(tmp_path, "ncp", image=False)
    assert build_catalog(tmp_path).status["OHRC"] is InstrumentStatus.PARTIAL
    other = tmp_path / "other"
    _ohrc(other, "nrp", broken=True)
    assert build_catalog(other).status["OHRC"] is InstrumentStatus.UNREADABLE


def test_geometry_grid_attached(tmp_path):
    from lunar_reg.ingest.catalog import build_catalog

    base = _ohrc(tmp_path, "ncp")
    grid = base.parents[2] / "geometry/calibrated/20230823"
    grid.mkdir(parents=True)
    (grid / "ch2_ohr_ncp_20230823T1450475804_g_grd_n18.csv").write_text("x")
    entry = build_catalog(tmp_path).products("OHRC")[0]
    assert entry.geometry_grid_path is not None
    assert entry.geometry_grid_path.name.endswith("_g_grd_n18.csv")


def test_cli_catalog(tmp_path, capsys):
    from lunar_reg.cli import main

    assert main(["catalog", "--raw-root", str(tmp_path)]) == 0
    assert "OHRC" in capsys.readouterr().out
