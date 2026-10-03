"""scripts/setup.sh --cuda: the torch requirement carries the index's local tag.

A bare ``torch==X.Y.Z`` is satisfied by any installed ``X.Y.Z+<tag>`` (PEP 440),
so pip would keep a ``+cpu`` or other-CUDA build and ignore ``--index-url``.
These tests run the real dependency and verify sections of setup.sh against a
stub interpreter (no network, nothing installed).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SETUP = REPO / "scripts" / "setup.sh"


def _section(start: str, end: str) -> str:
    text = SETUP.read_text()
    i = text.index(start)
    j = text.index(end, i)
    return text[i:j]


def _run_dependency_section(tmp_path: Path, installed: str | None, cuda_index: str):
    """Run setup.sh's CUDA install block with a stub $VPY; return the pip argv."""
    log = tmp_path / "pip_args.txt"
    site = tmp_path / "site"
    site.mkdir()
    if installed:  # a fake torch distribution seen by importlib.metadata
        dist = site / f"torch-{installed}.dist-info"
        dist.mkdir()
        (dist / "METADATA").write_text(
            f"Metadata-Version: 2.1\nName: torch\nVersion: {installed}\n"
        )
    stub = tmp_path / "vpy"
    # "$VPY -" runs setup.sh's real version-reading heredoc with only the fake
    # site dir importable (-S: no site-packages); "$VPY -m pip ..." records argv.
    stub.write_text(
        "#!/usr/bin/env bash\n"
        'if [ "$1" = "-" ]; then '
        f'PYTHONPATH="{site}" exec {sys.executable} -S -; fi\n'
        f'printf "%s\\n" "$@" > "{log}"\n'
    )
    stub.chmod(0o755)
    block = _section("# --- 3. dependencies", 'info "installing lunar-reg')
    script = (
        "set -euo pipefail\n"
        'die() { echo "die: $*" >&2; exit 1; }\n'
        "info() { :; }\n"
        f'VPY="{stub}"\nWANT_CUDA=1\nCUDA_INDEX={cuda_index}\n' + block
    )
    subprocess.run(["bash", "-c", script], check=True, cwd=tmp_path)
    return log.read_text().split("\n")


@pytest.mark.parametrize(
    ("installed", "index", "want"),
    [
        ("2.14.0+cpu", "cu130", "torch==2.14.0+cu130"),
        ("2.14.0+cu130", "cu126", "torch==2.14.0+cu126"),
        (None, "cu130", "torch==2.14.0+cu130"),
    ],
)
def test_cuda_requirement_pins_local_tag(tmp_path, installed, index, want):
    argv = _run_dependency_section(tmp_path, installed, index)
    assert want in argv
    assert f"https://download.pytorch.org/whl/{index}" in argv


def test_bare_pin_would_not_switch_variant():
    """Why the local tag is needed: PEP 440 ignores it when the specifier has none."""
    from packaging.specifiers import SpecifierSet

    assert SpecifierSet("==2.14.0").contains("2.14.0+cpu")
    assert not SpecifierSet("==2.14.0+cu130").contains("2.14.0+cpu")
    assert not SpecifierSet("==2.14.0+cu126").contains("2.14.0+cu130")


def _verify_snippet() -> str:
    block = _section("# --- 5. verify", ".venv/bin/lunar-reg env")
    m = re.search(r"<<'PY'\n(.*?)\nPY\n", block, re.S)
    assert m, "verify heredoc not found in setup.sh"
    return m.group(1)


def _run_verify(cuda_index: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, WANT_CUDA="1", CUDA_INDEX=cuda_index)
    return subprocess.run(
        [sys.executable, "-"], input=_verify_snippet(), text=True, capture_output=True, env=env
    )


def test_verify_rejects_wrong_cuda_variant():
    torch = pytest.importorskip("torch")
    if torch.version.cuda is None or "+" not in torch.__version__:
        pytest.skip("needs a CUDA torch build with a local tag in the venv")
    tag = torch.__version__.split("+", 1)[1]
    other = "cu126" if tag != "cu126" else "cu130"
    bad = _run_verify(other)
    assert bad.returncode != 0
    assert f"+{other}" in bad.stderr
    good = _run_verify(tag)
    assert good.returncode == 0, good.stderr
