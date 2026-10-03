"""P1.22 — docs + status refresh (Phase_1/LLD/viewers_docs.md §P1.22). Protected (G05)."""

from __future__ import annotations

import re
import subprocess

from _h1 import REPO

STALE = ("431 passed", "431 tests", "zero real OHRC", "No Chandrayaan-2 product was available")
DOCS = ("README.md", "docs/project/CONTEXT.md", "docs/project/CONTEXT_HANDOFF.md")


def test_stale_claims_gone():
    for rel in DOCS:
        text = (REPO / rel).read_text()
        for phrase in STALE:
            assert phrase not in text, f"{rel}: {phrase}"


def test_results_docs_tracked():
    for rel in ("docs/results/vikram_2024.md", "docs/results/jaxa_wac_2026-09-08.md"):
        assert (REPO / rel).exists(), rel


def test_added_numbers_have_sources():
    base = subprocess.run(["git", "merge-base", "HEAD", "phase-0-approved"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip() or "HEAD~1"
    diff = subprocess.run(["git", "diff", "-U0", base, "--", *DOCS], cwd=REPO,
                          capture_output=True, text=True).stdout
    bad = []
    for line in diff.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        if re.search(r"\b(tests?|pairs?)\b", line, re.I) and re.search(r"\d", line):
            if not any(s in line for s in ("docs/results/", "data/processed/", "[INSERT RESULT]")):
                bad.append(line[:160])
    assert not bad, "numbers without a source:\n" + "\n".join(bad[:10])
