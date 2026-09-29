"""P1B.01 — renderer + scenes shadow steps (Phase_1B/LLD/render.md). Protected (G05)."""

from __future__ import annotations

import numpy as np
import pytest


@pytest.mark.parametrize("az,axis_sign", [(90.0, "west"), (180.0, "north")])
def test_pillar_shadow_length(az, axis_sign):
    from lunar_reg.eval.render import render_shaded_relief

    d = np.zeros((201, 201))
    d[100, 100] = 30.0                       # 30 m pillar, 1 m posting, elevation 45 deg -> 30 px
    img = render_shaded_relief(d, 1.0, az, 45.0, ambient=0.0)
    lit = img[0, 0]
    if axis_sign == "west":                  # sun in the east -> shadow extends west
        line = img[100, :100][::-1]
    else:                                    # sun in the south -> shadow extends north
        line = img[:100, 100][::-1]
    shadowed = np.flatnonzero(line < lit)
    assert len(shadowed) and abs(int(shadowed.max()) + 1 - 30) <= 2


def test_nodata():
    from lunar_reg.eval.render import render_shaded_relief

    d = np.ones((50, 50))
    d[:5] = -9999.0
    img = render_shaded_relief(d, 1.0, 45.0, 30.0, nodata=-9999.0)
    assert (img[:5] == 0).all()


def test_scenes_steps_auto():
    from lunar_reg.eval.scenes import _cast_shadow_mask, add_craters, fractal_terrain

    h = add_craters(fractal_terrain((256, 256), seed=4), seed=4)
    auto = _cast_shadow_mask(h, 315.0, 5.0, 40.0)
    many = _cast_shadow_mask(h, 315.0, 5.0, 40.0, steps=2000)
    assert abs(auto.mean() - many.mean()) <= 0.005
