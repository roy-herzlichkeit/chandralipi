"""P1.07 — datum convention (Phase_1/LLD/datum.md). Protected (G05)."""

from __future__ import annotations

import numpy as np
from _h1 import REPO


def test_constants():
    from lunar_reg import constants as c
    from lunar_reg.provenance import ValueSource

    assert c.MOON_RADIUS_M == 1737400.0 and c.MOON_FLATTENING == 0.0
    assert c.LONGITUDE_DIRECTION == "east" and c.LONGITUDE_RANGE == "0_360"
    assert c.DATUM_SOURCE is ValueSource.INFERRED
    np.testing.assert_allclose(c.lon_to_360(np.array([-32.0, 32.0, 360.0, 721.0])),
                               [328.0, 32.0, 0.0, 1.0])
    np.testing.assert_allclose(c.lon_to_180(np.array([328.0, 32.0, 180.0, -181.0])),
                               [-32.0, 32.0, -180.0, 179.0])
    assert np.isnan(c.lon_to_360(np.array([np.nan]))[0])
    assert c.lon_to_360(-1.0) == 359.0


def test_doc():
    text = (REPO / "docs/DATUM.md").read_text()
    for term in ("planetocentric", "planetographic", "east", "1737400", "ValueSource",
                 "[INSERT RESULT]"):
        assert term.lower() in text.lower() or term in text, term


def test_datum_test_exists():
    text = (REPO / "tests/test_datum.py").read_text()
    assert "pytest.mark.data" in text and "MEASURED grid-vs-corner offset" in text
