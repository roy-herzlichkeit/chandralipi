"""Physical and mission constants.

Everything geodetic in this project is referenced to the Moon, never to WGS84.
``pygeodesy`` defaults to Earth ellipsoids, so any call that touches it must be
handed :data:`MOON_DATUM` explicitly -- silently using the default would put
footprint intersections off by roughly a factor of 3.7 in ground distance.
"""

from __future__ import annotations

from dataclasses import dataclass

# --- Lunar reference frame -------------------------------------------------
# IAU 2000/2009 mean radius. The Moon is treated as a sphere for PDS products;
# both axes are equal, so flattening is exactly 0.
MOON_RADIUS_M: float = 1_737_400.0
MOON_FLATTENING: float = 0.0

#: Name registered into pygeodesy's datum table by :func:`lunar_reg.ingest.footprint.moon_datum`.
MOON_DATUM_NAME = "Moon2000"


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


def scale_ratio(source: str, reference: str) -> float:
    """Return the GSD ratio between two sensors.

    A ratio far from 1.0 is what breaks naive matching: OHRC->TMC-2 is ~20x,
    OHRC->IIRS is ~320x. Anything above :data:`MAX_SAFE_SCALE_RATIO` should be
    bridged in two hops rather than matched directly.
    """
    return SENSORS[reference].gsd_m / SENSORS[source].gsd_m


#: Beyond this, resample the pair to a common intermediate grid (or route via TMC-2)
#: instead of asking a matcher to absorb the whole scale gap in one step.
MAX_SAFE_SCALE_RATIO: float = 8.0
