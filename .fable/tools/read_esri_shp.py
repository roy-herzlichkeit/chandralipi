"""ESRI shapefile (polygon) and dBASE III reader.

Follows the published ESRI Shapefile Technical Description (1998).
"""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np


def read_dbf(path) -> list[dict[str, str]]:
    """All records of a dBASE III table as dicts of stripped strings."""
    data = Path(path).read_bytes()
    n_records, header_len, record_len = struct.unpack("<IHH", data[4:12])
    fields = []
    offset = 32
    while data[offset] != 0x0D:
        name = data[offset : offset + 11].split(b"\0")[0].decode()
        fields.append((name, data[offset + 16]))
        offset += 32
    rows = []
    for r in range(n_records):
        record = data[header_len + r * record_len : header_len + (r + 1) * record_len]
        pos = 1  # byte 0 is the deletion flag
        values = {}
        for name, length in fields:
            values[name] = record[pos : pos + length].decode("latin1").strip()
            pos += length
        rows.append(values)
    return rows


def read_shp(path) -> list[np.ndarray | None]:
    """First ring of each polygon record as an (n, 2) array; None for null shapes."""
    data = Path(path).read_bytes()
    offset = 100
    polys: list[np.ndarray | None] = []
    while offset < len(data):
        _num, content_len = struct.unpack(">ii", data[offset : offset + 8])
        content = data[offset + 8 : offset + 8 + 2 * content_len]
        offset += 8 + 2 * content_len
        shape_type = struct.unpack("<i", content[:4])[0]
        if shape_type == 0:
            polys.append(None)
            continue
        assert shape_type in (5, 15, 25), shape_type
        n_parts, n_points = struct.unpack("<ii", content[36:44])
        parts = struct.unpack(f"<{n_parts}i", content[44 : 44 + 4 * n_parts])
        start = 44 + 4 * n_parts
        pts = np.frombuffer(content[start : start + 16 * n_points], dtype="<f8")
        pts = pts.reshape(n_points, 2)
        polys.append(pts[parts[0] : (parts[1] if n_parts > 1 else n_points)])
    return polys
