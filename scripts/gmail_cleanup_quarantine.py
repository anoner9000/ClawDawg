#!/usr/bin/env bash
set -euo pipefail

WORKSPACE="${HOME}/.openclaw/workspace"
RUNTIME="${HOME}/.openclaw/runtime"
CONFIG="${RUNTIME}/config/gmail_cleanup_senders.json"
LOGDIR="${RUNTIME}/logs"
TMPDIR="${RUNTIME}/tmp"

mkdir -p "$LOGDIR" "$TMPDIR"

TS="$(date -Iseconds | tr ':' '-')"
LOG="${LOGDIR}/cron_gmail_cleanup_${TS}.log"

# Use OpenClaw venv python (your logs show this exists)
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

  # Build senders CSV + days from config
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

  if [[ -z "$SENDERS_CSV" ]]; then
    echo "No senders configured. Exiting."
    echo "=== $(date -Iseconds) END gmail nightly cleanup ==="
    exit 0
  fi

  echo "Senders: $SENDERS_CSV"
  echo "Days:    $DAYS"
  echo "Samples: 0 (no cap; all matches)"
  echo

  # 1) Dry-run (build manifest for ALL matches) and write its stdout to a temp file for parsing
  DRYRUN_STDOUT="${TMPDIR}/gmail_cleanup_dryrun_${TS}.out"
  "$PY" -u modules/gmail/scripts/gmail_cleanup_dryrun.py \
    --senders "$SENDERS_CSV" \
    --days "$DAYS" \
    --samples 0 | tee "$DRYRUN_STDOUT"

  # 2) Parse manifest path (line contains: manifest=/path/to/file)
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

  echo
  echo "manifest: $MANIFEST"
  echo

  # 3) Quarantine ALL rows in manifest (APPLY)
  "$PY" -u modules/gmail/scripts/gmail_cleanup_quarantine.py --manifest "$MANIFEST" --apply

  echo
  echo "=== $(date -Iseconds) END gmail nightly cleanup ==="
} >>"$LOG" 2>&1
