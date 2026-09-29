"""P1B.02 — azimuth conventions (Phase_1B/LLD/rendered_reference.md). Protected (G05)."""

from __future__ import annotations

import pytest


def test_conventions_and_to_grid():
    from lunar_reg.pairs import AZIMUTH_CONVENTIONS, AzimuthCalibration
    from lunar_reg.provenance import ValueSource

    assert AZIMUTH_CONVENTIONS == ("as_is", "plus_180", "mirror", "mirror_plus_180")
    cal = AzimuthCalibration("mirror_plus_180", 1.5, 121.5, 60.0, 1.5, 0.2, ValueSource.INFERRED)
    assert cal.to_grid(60.0) == pytest.approx(121.5)
    assert cal.to_grid(300.0) == pytest.approx((180 - 300 + 1.5) % 360)
    for conv, label, grid in (("as_is", 10.0, 10.0), ("plus_180", 10.0, 190.0),
                              ("mirror", 10.0, 350.0)):
        c = AzimuthCalibration(conv, 0.0, grid, label, 0.0, 0.1, ValueSource.INFERRED)
        assert c.to_grid(label) == pytest.approx(grid)


def test_functions_exist():
    from lunar_reg import pairs

    for name in ("dtm_on_reference_grid", "calibrate_label_azimuth", "prepare_rendered_pair"):
        assert callable(getattr(pairs, name))
