"""P1.23 — code docstrings and script hints (Phase_1/LLD/viewers_docs.md §P1.23). Protected (G05)."""

from __future__ import annotations

import subprocess

from _h1 import REPO


def test_setup_hints():
    for rel in ("scripts/setup.sh", "scripts/up.sh", "scripts/run_dashboard.sh"):
        text = (REPO / rel).read_text()
        assert "build_demo_results.py" not in text or "run_vikram.py" in text, rel


def test_docstrings():
    assert "moon_datum" in (REPO / "src/lunar_reg/ingest/__init__.py").read_text()
    cfg = (REPO / "src/lunar_reg/preprocess/config.py").read_text()
    start = cfg.index("def ohrc_nac_config")
    assert "pca" not in cfg[start:start + 1500].lower() or "band_reduction=false" in \
        cfg[start:start + 1500].lower().replace(" ", "")


def test_gitignore():
    assert "Phase_*/benchmark/out/" in (REPO / ".gitignore").read_text()


def test_only_text_changed_in_src():
    """No code statement may change in P1.23: compile each touched module's AST without
    docstrings and compare with the previous commit."""
    import ast

    def strip(src: str) -> str:
        tree = ast.parse(src)
        for node in ast.walk(tree):
            body = getattr(node, "body", None)
            if isinstance(body, list) and body and isinstance(body[0], ast.Expr) and \
                    isinstance(getattr(body[0], "value", None), ast.Constant) and \
                    isinstance(body[0].value.value, str):
                node.body = body[1:] or [ast.Pass()]
        return ast.dump(tree)

    for rel in ("src/lunar_reg/ingest/__init__.py", "src/lunar_reg/ingest/fieldmap.py",
                "src/lunar_reg/ingest/manifest.py", "src/lunar_reg/preprocess/config.py"):
        old = subprocess.run(["git", "show", f"HEAD~1:{rel}"], cwd=REPO, capture_output=True,
                             text=True).stdout
        if not old:
            continue
        assert strip(old) == strip((REPO / rel).read_text()), f"code changed in {rel}"
