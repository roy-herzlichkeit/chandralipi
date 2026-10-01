"""Physical and mission constants.

Everything geodetic in this project is referenced to the Moon, never to WGS84.
``pygeodesy`` defaults to Earth ellipsoids, so any call that touches it must be
handed :data:`MOON_DATUM` explicitly -- silently using the default would put
footprint intersections off by roughly a factor of 3.7 in ground distance.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

# --- Lunar reference frame -------------------------------------------------
# IAU 2000/2009 mean radius. The Moon is treated as a sphere for PDS products;
# both axes are equal, so flattening is exactly 0.
MOON_RADIUS_M: float = 1_737_400.0
MOON_FLATTENING: float = 0.0

#: Name registered into pygeodesy's datum table by :func:`moon_datum`.
MOON_DATUM_NAME = "Moon2000"


@lru_cache(maxsize=1)
def moon_datum():
    """Return (and memoise) a pygeodesy datum for the IAU mean-radius lunar sphere.

    Registered once per process; pygeodesy raises on duplicate registration, so
    the cache is load-bearing rather than a micro-optimisation.
    """
    from pygeodesy.datums import Datum, Datums, Transform
    from pygeodesy.ellipsoids import Ellipsoid

    existing = getattr(Datums, MOON_DATUM_NAME, None)
    if existing is not None:
        return existing

    ellipsoid = Ellipsoid(
        MOON_RADIUS_M,
        MOON_RADIUS_M * (1.0 - MOON_FLATTENING),
        name=MOON_DATUM_NAME,
    )
    return Datum(ellipsoid, transform=Transform(), name=MOON_DATUM_NAME)


@dataclass(frozen=True)
class SensorSpec:
    """Nominal characteristics of a payload, used for scale-ratio planning.

    ``gsd_m`` is the nominal ground sample distance at the reference altitude;
    real products carry their own value in the PDS4 label and that always wins.
    """

    name: str
    gsd_m: float
    bands: int
    swath_km: float
    notes: str = ""


#: Nominal specs. Treat as planning defaults, not as ground truth for a given product.
SENSORS: dict[str, SensorSpec] = {
    "OHRC": SensorSpec(
        name="OHRC",
        gsd_m=0.25,
        bands=1,
        swath_km=3.0,
        notes="Strips are the memory problem: ~12k px across, tens of thousands of lines down.",
    ),
    "TMC2": SensorSpec(
        name="TMC-2",
        gsd_m=5.0,
        bands=1,
        swath_km=20.0,
        notes="Panchromatic; the natural bridge between OHRC and LRO NAC scales.",
    ),
    "IIRS": SensorSpec(
        name="IIRS",
        gsd_m=80.0,
        bands=256,
        swath_km=20.0,
        notes="Hyperspectral 0.8-5.0 um. Hardest modality; needs band reduction before matching.",
    ),
    "LRO_NAC": SensorSpec(
        name="LRO NAC",
        gsd_m=0.5,
        bands=1,
        swath_km=5.0,
        notes="Primary reference. Public, so it unblocks work before PRADAN/chmapbrowse access.",
    ),
    "SELENE_TC": SensorSpec(
        name="SELENE TC",
        gsd_m=10.0,
        bands=1,
        swath_km=35.0,
        notes="Independent third reference for cross-validation.",
    ),
}


#: Beyond this, resample the pair to a common intermediate grid (or route via TMC-2)
#: instead of asking a matcher to absorb the whole scale gap in one step.
MAX_SAFE_SCALE_RATIO: float = 8.0
