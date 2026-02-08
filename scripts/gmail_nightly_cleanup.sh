#!/usr/bin/env bash
set -euo pipefail

WORKSPACE="${HOME}/.openclaw/workspace"
RUNTIME="${HOME}/.openclaw/runtime"
CONFIG="${RUNTIME}/config/gmail_cleanup_senders.json"
LOGDIR="${RUNTIME}/logs"
TMPDIR="${RUNTIME}/tmp"
HEARTBEAT_DIR="${RUNTIME}/logs/heartbeat"

mkdir -p "$LOGDIR" "$TMPDIR" "$HEARTBEAT_DIR"

TS="$(date -Iseconds | tr ':' '-')"
LOG="${LOGDIR}/gmail_cleanup_${TS}.log"

PY="${HOME}/.openclaw/venv/bin/python3"
if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3)"
fi

cd "$WORKSPACE"

{
  echo "=== $(date -Iseconds) START gmail nightly cleanup ==="
  echo "workspace: $WORKSPACE"
  echo "runtime:    $RUNTIME"
  echo "config:     $CONFIG"
  echo "python:     $PY"
  echo

  if [[ ! -f "$CONFIG" ]]; then
    echo "ERROR: config not found: $CONFIG"
    exit 1
  fi

  SENDERS_CSV="$("$PY" - <<'PY'
import json, os
cfg_path = os.path.expanduser("~/.openclaw/runtime/config/gmail_cleanup_senders.json")
with open(cfg_path, "r", encoding="utf-8") as f:
    cfg = json.load(f)
senders = [s.get("email","").strip() for s in cfg.get("senders", [])]
senders = [s for s in senders if s]
print(",".join(senders))
PY
)"

  DAYS="$("$PY" - <<'PY'
import json, os
cfg_path = os.path.expanduser("~/.openclaw/runtime/config/gmail_cleanup_senders.json")
with open(cfg_path, "r", encoding="utf-8") as f:
    cfg = json.load(f)
print(int(cfg.get("default_days", 180)))
PY
)"

  # Optional hard override from environment (cron-friendly)
  if [[ -n "${GMAIL_CLEANUP_DAYS:-}" ]]; then
    DAYS="$GMAIL_CLEANUP_DAYS"
  fi

  if [[ -z "$SENDERS_CSV" ]]; then
    echo "No senders configured. Exiting."
    echo "=== $(date -Iseconds) END gmail nightly cleanup ==="
    exit 0
  fi

  echo "Senders: $SENDERS_CSV"
  echo "Days:    $DAYS"
  echo "Samples: 0 (no cap; all matches)"
  echo

  DRYRUN_STDOUT="${TMPDIR}/gmail_cleanup_dryrun_${TS}.out"
  "$PY" -u modules/gmail/scripts/gmail_cleanup_dryrun.py \
    --senders "$SENDERS_CSV" \
    --days "$DAYS" \
    --samples 0 | tee "$DRYRUN_STDOUT"

  MANIFEST="$(sed -n 's/.*manifest=\([^ ]*\).*/\1/p' "$DRYRUN_STDOUT" | tail -n 1)"
  if [[ -z "$MANIFEST" ]]; then
    echo
    echo "ERROR: Could not parse manifest path from dryrun output."
    echo "dryrun_stdout: $DRYRUN_STDOUT"
    exit 1
  fi
  if [[ ! -f "$MANIFEST" ]]; then
    echo
    echo "ERROR: Manifest file not found: $MANIFEST"
    exit 1
  fi

  if [[ ! -s "$MANIFEST" ]]; then
    echo "Manifest empty; skipping quarantine+trash."
    echo "=== $(date -Iseconds) END gmail nightly cleanup ==="
    exit 0
  fi

  echo
  echo "manifest: $MANIFEST"
  echo

  "$PY" -u modules/gmail/scripts/gmail_cleanup_quarantine.py --manifest "$MANIFEST" --apply

  QUAR_LOG="${MANIFEST}.quarantine_log"
  if [[ ! -f "$QUAR_LOG" ]]; then
    echo
    echo "ERROR: quarantine log not found: $QUAR_LOG"
    exit 1
  fi

  : "${GMAIL_TRASH_CONFIRM:=}"
  echo "trash_apply=${GMAIL_TRASH_APPLY:-0} trash_confirm=${GMAIL_TRASH_CONFIRM:-}"
  if [[ "${GMAIL_TRASH_APPLY:-0}" != "1" ]]; then
    echo "Skipping trash step (set GMAIL_TRASH_APPLY=1 to enable)."
  elif [[ "$GMAIL_TRASH_CONFIRM" != "TrashApply" ]]; then
    echo "Refusing trash: set GMAIL_TRASH_CONFIRM=TrashApply"
  else
    "$PY" -u modules/gmail/scripts/gmail_cleanup_trash.py \
      --quarantine-log "$QUAR_LOG" \
      --confirm "$GMAIL_TRASH_CONFIRM" \
      --apply
  fi

  SUMMARY_JSON="${LOGDIR}/gmail_cleanup_last_summary.json"
  HEARTBEAT_JSONL="${HEARTBEAT_DIR}/gmail_cleanup.jsonl"

  # Pass values via environment variables to avoid bash interpolation pitfalls
  GMAIL_QUAR_LOG="$QUAR_LOG" \
  GMAIL_TRASH_LOG="${QUAR_LOG}.trash_log" \
  GMAIL_SUMMARY_JSON="$SUMMARY_JSON" \
  GMAIL_HEARTBEAT_JSONL="$HEARTBEAT_JSONL" \
  GMAIL_SENDERS_CSV="$SENDERS_CSV" \
  GMAIL_DAYS="$DAYS" \
  GMAIL_MANIFEST="$MANIFEST" \
  "$PY" - <<'PY'
import json, os, time, datetime
from pathlib import Path

quar_log = Path(os.environ["GMAIL_QUAR_LOG"])
trash_log = Path(os.environ["GMAIL_TRASH_LOG"])
summary_json = Path(os.environ["GMAIL_SUMMARY_JSON"])
hb_jsonl = Path(os.environ["GMAIL_HEARTBEAT_JSONL"])

senders_csv = os.environ.get("GMAIL_SENDERS_CSV", "")
days = int(os.environ.get("GMAIL_DAYS", "0") or 0)
manifest = os.environ.get("GMAIL_MANIFEST", "")

def count_jsonl(path: Path) -> int:
    if (not path.exists()) or path.stat().st_size == 0:
        return 0
    n = 0
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                json.loads(line)
                n += 1
            except Exception:
                continue
    return n

now = datetime.datetime.now(datetime.timezone.utc)
payload = {
    "created_at": int(time.time()),
    "date": now.date().isoformat(),
    "ts_utc": now.isoformat(),
    "days": days,
    "senders_csv": senders_csv,
    "manifest": manifest,
    "quarantine_log": str(quar_log),
    "trash_log": str(trash_log),
    "quarantined_count": count_jsonl(quar_log),
    "trashed_count": count_jsonl(trash_log),
}

summary_json.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")

hb_jsonl.parent.mkdir(parents=True, exist_ok=True)
with hb_jsonl.open("a", encoding="utf-8") as f:
    f.write(json.dumps(payload, ensure_ascii=False) + "\n")
PY

  echo
  echo "Wrote summary: $SUMMARY_JSON"
  echo "Appended heartbeat: $HEARTBEAT_JSONL"
  echo
  echo "=== $(date -Iseconds) END gmail nightly cleanup ==="
} >>"$LOG" 2>&1
