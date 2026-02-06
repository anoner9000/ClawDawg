#!/usr/bin/env bash
set -euo pipefail

WORKSPACE="${HOME}/.openclaw/workspace"
RUNTIME="${HOME}/.openclaw/runtime"
CONFIG="${RUNTIME}/config/yahoo_cleanup_rules.json"

BASE="${RUNTIME}/yahoo_cleanup"
LOGDIR="${BASE}/logs"
TMPDIR="${BASE}/tmp"
STATEDIR="${BASE}/state"

mkdir -p "$LOGDIR" "$TMPDIR" "$STATEDIR"

TS="$(date -Iseconds | tr ':' '-')"
LOG="${LOGDIR}/cron_yahoo_cleanup_${TS}.log"

PY="${HOME}/.openclaw/venv/bin/python3"
if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3)"
fi

cd "$WORKSPACE"

{
  echo "=== $(date -Iseconds) START yahoo nightly cleanup ==="
  echo "workspace: $WORKSPACE"
  echo "runtime:    $RUNTIME"
  echo "config:     $CONFIG"
  echo "python:     $PY"
  echo

  if [[ ! -f "$CONFIG" ]]; then
    echo "ERROR: config not found: $CONFIG"
    exit 1
  fi

  MANIFEST_OUT="${TMPDIR}/yahoo_cleanup_manifest_${TS}.jsonl"

  # 1) DRYRUN -> manifest jsonl
  "$PY" -u scripts/yahoo_cleanup_dryrun.py --config "$CONFIG" --manifest "$MANIFEST_OUT" | tee "${MANIFEST_OUT}.stdout"

  if [[ ! -s "$MANIFEST_OUT" ]]; then
    echo
    echo "No matches found. Exiting."
    echo "=== $(date -Iseconds) END yahoo nightly cleanup ==="
    exit 0
  fi

  echo
  echo "manifest: $MANIFEST_OUT"
  echo

  # 2) QUARANTINE APPLY (safe)
  "$PY" -u scripts/yahoo_cleanup_quarantine.py --manifest "$MANIFEST_OUT" --apply

  QUAR_LOG="${MANIFEST_OUT}.quarantine_log"
  if [[ ! -f "$QUAR_LOG" ]]; then
    echo
    echo "ERROR: quarantine log not found: $QUAR_LOG"
    exit 1
  fi

  # 3) TRASH APPLY (guarded) - optional; comment out if you want quarantine-only
  "$PY" -u scripts/yahoo_cleanup_trash.py \
    --quarantine-log "$QUAR_LOG" \
    --confirm "TrashApply" \
    --apply

  # Summary
  SUMMARY_JSON="${STATEDIR}/yahoo_cleanup_last_summary.json"
  "$PY" -u - <<'PY'
import json, time, datetime, os
from pathlib import Path

base = Path(os.path.expanduser("~/.openclaw/runtime/yahoo_cleanup"))
tmp = base/"tmp"
state = base/"state"

# newest manifest is the one we just wrote; find by mtime in tmp
man = sorted(tmp.glob("yahoo_cleanup_manifest_*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)[0]
quar = Path(str(man) + ".quarantine_log")
trash = Path(str(quar) + ".trash_log")

def count_jsonl(p: Path) -> int:
    if not p.exists() or p.stat().st_size == 0:
        return 0
    n = 0
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if not line:
                continue
            try:
                json.loads(line)
                n += 1
            except Exception:
                continue
    return n

now = datetime.datetime.now(datetime.UTC)
payload = {
    "created_at": int(time.time()),
    "date": now.date().isoformat(),
    "ts_utc": now.isoformat(),
    "manifest": str(man),
    "quarantine_log": str(quar) if quar.exists() else None,
    "trash_log": str(trash) if trash.exists() else None,
    "quarantined_count": count_jsonl(quar),
    "trashed_count": count_jsonl(trash),
}
(state/"yahoo_cleanup_last_summary.json").write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
print("Wrote summary:", state/"yahoo_cleanup_last_summary.json")
PY

  echo
  echo "=== $(date -Iseconds) END yahoo nightly cleanup ==="
} >>"$LOG" 2>&1
