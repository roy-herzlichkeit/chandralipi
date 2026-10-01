"""`lunar-reg inspect` on synthetic labels (review P0-03)."""

from __future__ import annotations

from pathlib import Path

from lunar_reg.cli import main

LABEL = """<?xml version="1.0" encoding="UTF-8"?>
<Product_Observational xmlns="http://pds.nasa.gov/pds4/pds/v1">
  <Identification_Area><logical_identifier>urn:test:ch2_ohr_x</logical_identifier></Identification_Area>
  <File_Area_Observational><File><file_name>{file_name}</file_name></File></File_Area_Observational>
</Product_Observational>
"""


def _label(tmp_path: Path, file_name: str) -> Path:
    path = tmp_path / "product" / "p.xml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(LABEL.format(file_name=file_name))
    (path.parent / "p.img").write_bytes(b"\0")
    return path


def test_inspect_reads_label_values_without_attribute_errors(tmp_path, capsys):
    assert main(["inspect", str(_label(tmp_path, "p.img"))]) == 0
    out = capsys.readouterr().out
    assert "image:      p.img" in out
    assert "sun azim" not in out  # absent from this label, so not printed


def test_inspect_reports_a_rejected_image_path(tmp_path, capsys):
    assert main(["inspect", str(_label(tmp_path, "../../etc/passwd"))]) == 0
    out = capsys.readouterr().out
    assert "REJECTED" in out and "../../etc/passwd" in out
