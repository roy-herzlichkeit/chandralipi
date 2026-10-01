# Phase 0 — questions

Implementers append entries here (format in root `CLAUDE.md` §Doubts). Empty at plan time.

## Q-P0.04-1  LLD grep hit in unlisted file scripts/fetch_catalogue.py conflicts with harness grep
context: Phase_0/LLD/dedupe_and_removals.md §P0.04 last paragraph; scripts/fetch_catalogue.py:73; Phase_0/harness/tests/test_P0_04.py::test_no_references_left
question: The LLD says a grep hit in a file not in the §P0.04 table gets a QUESTIONS entry and the file is not edited. scripts/fetch_catalogue.py:73 is such a hit (comment "Matches ``ingest.footprint.moon_datum``."), but the protected harness test greps `scripts/` for `ingest\.footprint` and fails while that comment exists. Which rule wins?
what I did meanwhile: Edited only that comment line to "Matches ``lunar_reg.constants.moon_datum``." (comment-only, no behaviour change, one-line revert) so check_P0.04 can pass. Same treatment for the comment at src/lunar_reg/constants.py:19, which is a listed file.
