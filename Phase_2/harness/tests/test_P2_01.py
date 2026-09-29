"""P2.01 — CUDA setup (Phase_2/LLD/device.md §P2.01). Protected (G05)."""

from __future__ import annotations

from _h2 import REPO


def test_setup_cuda_index_flag():
    text = (REPO / "scripts/setup.sh").read_text()
    assert "--cuda-index" in text and "cu130" in text
    assert "cu124" not in text
    assert "torch.version.cuda" in text


def test_docs_no_cu124():
    for rel in ("README.md", "scripts/README.md"):
        assert "cu124" not in (REPO / rel).read_text(), rel


def test_no_nameplate_fallback():
    import inspect

    from lunar_reg import device

    src = inspect.getsource(device.free_vram_bytes) + inspect.getsource(device.free_memory_bytes)
    assert "ASSUMED_TOTAL_VRAM_BYTES" not in src
