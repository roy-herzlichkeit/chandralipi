#!/usr/bin/env bash
# check_P1.DL — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
"$PY" - <<'PY' || fail "data/raw/DOWNLOADS.json is not valid C08"
import json, pathlib, re, sys
p = pathlib.Path("data/raw/DOWNLOADS.json")
if not p.exists():
    sys.exit("DOWNLOADS.json missing")
doc = json.loads(p.read_text())
keys = {"path", "bytes", "sha256", "source", "url", "product_id", "instrument", "role", "downloaded_utc", "recorded_by"}
assert doc.get("schema") == 1 and isinstance(doc.get("files"), list) and isinstance(doc.get("failures", []), list)
for f in doc["files"]:
    assert set(f) == keys, f
    assert re.fullmatch(r"[0-9a-f]{64}", f["sha256"]) and f["path"].startswith("data/raw/")
    assert pathlib.Path(f["path"]).exists(), f["path"]
print(len(doc["files"]), "file(s) recorded;", len(doc.get("failures", [])), "failure(s)")
PY
ok P1.DL
