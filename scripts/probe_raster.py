"""Bounded-memory probe of a large raster (G40; Phase_1/LLD/tmc2_iirs.md §1 step 2).

    python scripts/probe_raster.py PATH --out docs/probes/<product_id>_raster.json

Opens ``PATH`` with rasterio and reads band 1 only through one decimated read
(``out_shape=(ceil(h/f), ceil(w/f))``, ``Resampling.nearest``, with
``f = ceil(max(width, height) / 2048)``). It never calls ``read()`` without
``out_shape``, so a 15 GB orthoimage is probed in a few hundred MB.

The JSON records the raster's structure, the declared nodata, and the five most
common values on the outermost 2 % of rows and columns of the decimated read.
When one border value covers at least half of the border samples it is reported
as ``fill_candidate`` with ``fill_candidate_source = "inferred"``: it is a guess
from pixel statistics, not a documented fill, and nothing downstream may use it
until a human confirms it against the product's SIS document.

Outcome: exit 0 with ``status = "ok"`` (or ``"no_border_samples"`` for a raster
too small to have a border), exit 1 with ``status = "open_failed"`` or
``"read_failed"`` (the JSON is still written, with the error). One report line
is printed on every run.
"""

from __future__ import annotations

import argparse
import json
import math
import resource
import sys
from enum import Enum
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402

from lunar_reg.provenance import ValueSource  # noqa: E402

REPO = Path(__file__).resolve().parents[1]

#: Longest side of the decimated read, in pixels (LLD §1 step 2).
TARGET_SIDE = 2048
#: Share of rows and of columns, at each edge, that counts as "border".
BORDER_FRACTION = 0.02
#: How many of the most common border values are listed.
N_BORDER_VALUES = 5
#: A border value is a fill candidate when it covers at least this share.
FILL_MIN_SHARE = 0.5
#: GDAL block cache cap for the probe, in MB, so peak RSS stays bounded.
GDAL_CACHE_MB = 64


class ProbeStatus(str, Enum):
    OK = "ok"
    NO_BORDER_SAMPLES = "no_border_samples"
    OPEN_FAILED = "open_failed"
    READ_FAILED = "read_failed"


def _repo_relative(path: Path) -> str:
    resolved = path.resolve()
    if resolved.is_relative_to(REPO):
        return str(resolved.relative_to(REPO))
    return str(resolved)


def _json_value(value) -> float | int | str | None:
    """A numpy scalar as a JSON-safe value; NaN becomes the string ``"nan"``."""
    if value is None:
        return None
    item = value.item() if hasattr(value, "item") else value
    if isinstance(item, float) and math.isnan(item):
        return "nan"
    return item


def decimation_factor(width: int, height: int) -> int:
    return max(1, math.ceil(max(width, height) / TARGET_SIDE))


def border_mask(shape: tuple[int, int]) -> np.ndarray:
    """True on the outermost ``BORDER_FRACTION`` of rows and of columns."""
    h, w = shape
    br = max(1, math.ceil(BORDER_FRACTION * h))
    bc = max(1, math.ceil(BORDER_FRACTION * w))
    mask = np.zeros(shape, dtype=bool)
    mask[:br, :] = True
    mask[h - br :, :] = True
    mask[:, :bc] = True
    mask[:, w - bc :] = True
    return mask


def border_statistics(decimated: np.ndarray) -> dict:
    """Border value counts, fill candidate and its share of the decimated read."""
    samples = decimated[border_mask(decimated.shape)]
    out: dict = {
        "border_values": [],
        "n_border_samples": int(samples.size),
        "fill_candidate": None,
        "fill_fraction": None,
    }
    if samples.size == 0:
        return out
    values, counts = np.unique(samples, return_counts=True)
    order = np.argsort(counts, kind="stable")[::-1][:N_BORDER_VALUES]
    out["border_values"] = [
        {"value": _json_value(values[i]), "count": int(counts[i])} for i in order
    ]
    top = order[0]
    if counts[top] >= FILL_MIN_SHARE * samples.size:
        fill = values[top]
        out["fill_candidate"] = _json_value(fill)
        if isinstance(fill.item(), float) and math.isnan(fill.item()):
            share = np.isnan(decimated).mean()
        else:
            share = (decimated == fill).mean()
        out["fill_fraction"] = float(share)
    return out


def probe(path: Path) -> tuple[dict, ProbeStatus]:
    import rasterio
    from rasterio.enums import Resampling

    doc: dict = {
        "path": _repo_relative(path),
        "width": None,
        "height": None,
        "count": None,
        "dtype": None,
        "block_shapes": [],
        "compression": None,
        "nodata_declared": None,
        "crs_wkt": None,
        "res": None,
        "decimation": None,
        "out_shape": None,
        "band_read": 1,
        "border_values": [],
        "n_border_samples": 0,
        "fill_candidate": None,
        "fill_candidate_source": ValueSource.INFERRED.value,
        "fill_fraction": None,
        "value_sources": {
            "structure": ValueSource.DOCUMENTED.value,
            "nodata_declared": ValueSource.DOCUMENTED.value,
            "decimation": ValueSource.COMPUTED.value,
            "border_values": ValueSource.MEASURED.value,
            "fill_candidate": ValueSource.INFERRED.value,
            "fill_fraction": ValueSource.MEASURED.value,
            "peak_rss_bytes": ValueSource.MEASURED.value,
        },
        "error": None,
    }
    with rasterio.Env(GDAL_CACHEMAX=GDAL_CACHE_MB):
        try:
            ds = rasterio.open(path)
        except Exception as exc:  # noqa: BLE001 -- classified, reported, exit 1
            doc["error"] = f"{type(exc).__name__}: {exc}"
            return doc, ProbeStatus.OPEN_FAILED
        with ds:
            doc.update(
                width=ds.width,
                height=ds.height,
                count=ds.count,
                dtype=ds.dtypes[0],
                block_shapes=[list(b) for b in ds.block_shapes],
                compression=None if ds.compression is None else str(ds.compression.value),
                nodata_declared=_json_value(ds.nodata),
                crs_wkt=None if ds.crs is None else ds.crs.to_wkt(),
                res=[float(ds.res[0]), float(ds.res[1])],
            )
            f = decimation_factor(ds.width, ds.height)
            out_shape = (math.ceil(ds.height / f), math.ceil(ds.width / f))
            doc["decimation"] = f
            doc["out_shape"] = list(out_shape)
            try:
                decimated = ds.read(1, out_shape=out_shape, resampling=Resampling.nearest)
            except Exception as exc:  # noqa: BLE001 -- classified, reported, exit 1
                doc["error"] = f"{type(exc).__name__}: {exc}"
                return doc, ProbeStatus.READ_FAILED
    doc.update(border_statistics(decimated))
    status = ProbeStatus.OK if doc["n_border_samples"] else ProbeStatus.NO_BORDER_SAMPLES
    return doc, status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", type=Path, help="raster to probe (GeoTIFF or any GDAL raster)")
    parser.add_argument("--out", type=Path, required=True, help="JSON file to write")
    args = parser.parse_args(argv)

    doc, status = probe(args.path)
    doc["status"] = status.value
    doc["peak_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2) + "\n")
    print(
        f"probe_raster: {status.value} {doc['path']} {doc['width']}x{doc['height']}"
        f"x{doc['count']} f={doc['decimation']} nodata_declared={doc['nodata_declared']}"
        f" fill_candidate={doc['fill_candidate']} ({doc['fill_candidate_source']})"
        f" fill_fraction={doc['fill_fraction']} peak_rss_bytes={doc['peak_rss_bytes']}"
        f" -> {args.out}" + (f" error={doc['error']}" if doc["error"] else "")
    )
    return 0 if status in (ProbeStatus.OK, ProbeStatus.NO_BORDER_SAMPLES) else 1


if __name__ == "__main__":
    sys.exit(main())
