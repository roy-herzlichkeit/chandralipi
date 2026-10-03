"""Status claims in README / CONTEXT / CONTEXT_HANDOFF stay sourced (P1.22 review fixes)."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (REPO / rel).read_text()


def test_readme_keeps_pca_in_the_papers_ohrc_nac_row():
    """The paper's §4.2 A track includes PCA; only ohrc_nac_config() leaves it out."""
    text = _read("README.md")
    assert "| OHRC/NAC (§4.2 A) | CLAHE, image inversion, morphological dilation, PCA |" in text
    assert "`ohrc_nac_config()` leaves out the paper's PCA step" in text


def test_synthetic_store_is_described_as_a_default_path_not_a_location():
    """No doc claims the synthetic set currently lives in the backup store."""
    for rel in ("README.md", "docs/project/CONTEXT.md", "docs/project/CONTEXT_HANDOFF.md"):
        text = " ".join(_read(rel).split())
        assert "lives in its own store" not in text, rel
        assert "set lives in `data/processed/results_ch2_synthetic_backup/`" not in text, rel
        assert "the synthetic set was moved out of the live store" not in text, rel


def test_readme_crop_mapping_names_the_geometry_grid_first():
    text = " ".join(_read("README.md").split())
    assert "which is itself unverified" not in text
    assert "`PriorSource.GEOMETRY_GRID`" in text
    assert "`test_corner_numbering_is_not_ring_order`" in text
    # the cited test must exist
    assert "def test_corner_numbering_is_not_ring_order" in _read("tests/test_ingest_labels.py")


def test_handoff_header_does_not_imply_unmarked_claims_are_current():
    text = " ".join(_read("docs/project/CONTEXT_HANDOFF.md").split())
    assert "kept as written, except where a status claim is marked" not in text
    assert "a claim without one is not thereby current" in text
    assert "Each is genuinely open." not in text


def test_live_store_counts_results_not_pairs():
    """Index rows are (image pair, matcher) results; the image-pair count has its own source."""
    for rel in ("docs/project/CONTEXT.md", "docs/project/CONTEXT_HANDOFF.md"):
        text = _read(rel)
        assert "16 registered pairs" not in text, rel
        assert "docs/results/live_store_pairs_20261002.txt" in text, rel
    assert (REPO / "docs/results/live_store_pairs_20261002.txt").exists()
