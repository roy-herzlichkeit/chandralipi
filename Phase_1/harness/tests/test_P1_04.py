"""P1.04 — NAC georeference + LRO rows (Phase_1/LLD/lro_georeference.md §5). Protected (G05)."""

from __future__ import annotations

import pytest
from _h1 import NAC_LABEL, cart_label, raster_bounds


def test_lro_row_has_size_and_bounds(tmp_path):
    from lunar_reg.ingest.lro import lro_to_row, read_lro_label

    x0, y0, w, h, px = -11043.5, 638258.5, 230, 476, 100.0
    path = tmp_path / "nac.xml"
    path.write_text(cart_label(11043.5, y0, w, h, px, raster_bounds(x0, y0, w, h, px)))
    product = read_lro_label(path)
    assert product.georef is not None and product.georef.x0_m == pytest.approx(-11043.5)
    row = lro_to_row(product)
    assert (row["lines"], row["samples"]) == (476, 230)
    for key in ("min_lat", "max_lat", "min_lon", "max_lon"):
        assert row[key] is not None
    assert row["footprint_resolved"] is True


def test_open_lro_docstring_warns():
    from lunar_reg.ingest import lro

    assert "georef" in (lro.open_lro_product.__doc__ or "").lower()


@pytest.mark.data
def test_real_nac_row():
    if not NAC_LABEL.exists():
        pytest.skip(f"missing {NAC_LABEL}")
    from lunar_reg.ingest.lro import lro_to_row, read_lro_label

    row = lro_to_row(read_lro_label(NAC_LABEL))
    assert (row["lines"], row["samples"]) == (47683, 23003)
    assert row["min_lat"] == pytest.approx(-70.07416629)
    assert row["max_lon"] == pytest.approx(33.37349926)
