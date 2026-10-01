# STATUS

current: P1.13
phase: 1
state: READY
branch: phase-1
last_done: P1.12
notes:
- P1.12: new src/lunar_reg/eval/agreement.py (C14 AgreementResult + cross_matcher_agreement, LLD §2 agreement_for_stored); pre-ECC transforms only; probes = 4 corners + centre via Transform.apply (placeholder model name); eval/__init__.py NOT changed (outside fence) -> import from lunar_reg.eval.agreement.
- Skipped with one WARNING per matcher: non-finite entry, singular 3x3 (|det|<1e-12), or a probe mapped to a non-finite point. A matrix that is not 3x3 or 2x3 raises ValueError.
- agreement_for_stored also raises ValueError on duplicate matcher name among usable results, or when no usable result has source_image; v1 records skipped (one INFO line); all-v1 -> n_matchers=0, NaN, fails. Extra beyond LLD -> list as LLD deviations in the review pack.
- Q-P1.12-1 (non-blocking): duplicate matcher raises, so P1.16's Exp-1 gate must pass one result per matcher (and one source/reference pair per call) unless the architect chooses variant-keyed names.
- scripts/ci.sh: 819 passed (log: scratchpad p1/ci_P1.12.log); check_P1.12 < 1 s.
