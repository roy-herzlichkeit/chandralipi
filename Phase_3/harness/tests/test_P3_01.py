"""P3.01 — job descriptor validation (Phase_3/LLD/job_outcome.md §P3.01). Protected (G05)."""

from __future__ import annotations

import subprocess
import sys

import pytest
from _h3 import REPO, job_kwargs


@pytest.mark.parametrize("field,value", [
    ("source_window", (0, 0, 0, 10)), ("reference_window", (-1, 0, 5, 5)),
    ("precision", "bf16"), ("reference_path", "../x.tif"), ("prior", (float("nan"),) * 9),
])
def test_validation(field, value):
    from lunar_reg.distributed.job import JobDescriptor

    with pytest.raises(ValueError, match=field):
        JobDescriptor(**job_kwargs("a.tif", "b.tif", **{field: value}))


def test_package_import_is_light():
    code = ("import sys; import lunar_reg.distributed, lunar_reg.distributed.job;"
            "print(sorted(m for m in ('torch', 'redis', 'lunar_reg.pipeline') if m in sys.modules))")
    out = subprocess.run([sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True,
                         timeout=60)
    assert out.stdout.strip() == "[]", out.stdout + out.stderr


def test_pipeline_does_not_import_distributed():
    text = (REPO / "src/lunar_reg/pipeline.py").read_text()
    assert "distributed" not in text
