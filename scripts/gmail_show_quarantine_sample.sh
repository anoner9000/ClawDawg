#!/usr/bin/env bash
set -euo pipefail

QLOG="$(scripts/gmail_latest_quarantine_log_path.sh)"
N="${1:-20}"

echo "Quarantine log: ${QLOG}"
echo "Showing first ${N} entries:"
echo

python3 - <<PY
import json
import sys

path = "${QLOG}"
n = int("${N}")

shown = 0
with open(path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        # show key fields
        rec = {
            "action": obj.get("action"),
            "from": obj.get("from"),
            "subject": obj.get("subject"),
            "date": obj.get("date"),
            "id": obj.get("id"),
        }
        print(json.dumps(rec, ensure_ascii=False))
        shown += 1
        if shown >= n:
            break

if shown == 0:
    print("(no entries)")
PY
