"""P2.11 docs keep their provenance tags and cite one run (Q-P2.11-1 answer (a))."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _flat(rel: str) -> str:
    return " ".join((REPO / rel).read_text().split())


def test_loftr_runtime_tile_limit_is_not_tagged_measured():
    """The 896 px limit is the analytic (INFERRED) planner's output, not a measurement."""
    text = _flat("docs/VRAM_CONSTRAINTS.md")
    assert "limited LoFTR to 896 px (MEASURED" not in text
    assert "limited LoFTR to 896 px (COMPUTED at run time by the INFERRED analytic" in text


def test_gpu_run_doc_cites_one_run_and_the_archive():
    text = _flat("docs/GPU_RUN.md")
    assert "--native-matcher lightglue" in text and "answer (a) to Q-P2.11-1" in text
    assert "This run record and the live store rows come from the same run" in text
    assert "data/processed/gpu_run_archive_20261003/" in text
    assert "anchor_native_lightglue" not in text


def test_vram_doc_cites_the_official_run_only():
    assert "anchor_native_lightglue" not in _flat("docs/VRAM_CONSTRAINTS.md")
