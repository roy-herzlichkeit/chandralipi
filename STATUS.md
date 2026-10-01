# STATUS

current: P1.08
phase: 1
state: READY
branch: phase-1
last_done: P1.07
notes:
- P1.07: constants.py adds LONGITUDE_DIRECTION="east", LONGITUDE_RANGE="0_360", DATUM_SOURCE=ValueSource.INFERRED, DATUM_NOTE, lon_to_360/lon_to_180 (vectorised, NaN kept, scalar->float); no existing constant changed. docs/DATUM.md written (offset stays [INSERT RESULT]); every section 2 table row carries a ValueSource member (internal longitude range INFERRED as project convention), enforced by a new unit test.
- tests/test_datum.py: unit tests + 1 @pytest.mark.data test (ran: 25 grid nodes inside NAC, both mirrors outside).
- Data test printed (pytest tests/test_datum.py -s): "MEASURED grid-vs-corner offset (m): median 2903.6 over the 25 sub-grid nodes, strip centre 2900.4 (ValueSource.MEASURED; ch2_ohr_ncp_20240425T1406019344_d_img_d18 vs NAC NAC_DTM_VIKRAMSITE1_M1442997156_100CM, NAC georeference source inferred)"
- Non-blocking Q-P1.07-1: LLD §3.5 "median ... of the strip centre" is ambiguous; the test prints and asserts both the 25-node median and the centre distance.
- constants.py, tests/test_datum.py ruff-clean and formatted. scripts/ci.sh: 664 passed (log: scratchpad p1/ci_P1.07.log).
