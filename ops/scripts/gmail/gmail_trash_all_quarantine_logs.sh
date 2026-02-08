#!/usr/bin/env bash
set -euo pipefail

# Durable "TrashApplyAll" helper:
# - Scans ~/.openclaw/runtime/logs/*.quarantine_log (newest first)
# - Skips empty logs
# - Skips logs where everything is already recorded in <qlog>.trash_log
# - Requires BOTH:
#     GMAIL_TRASH_APPLY=1
#     GMAIL_TRASH_CONFIRM=TrashApply
#
# Usage:
#   GMAIL_TRASH_APPLY=1 GMAIL_TRASH_CONFIRM=TrashApply bash ~/.openclaw/workspace/scripts/gmail_trash_all_quarantine_logs.sh
#
# Safe preview:
#   bash ~/.openclaw/workspace/scripts/gmail_trash_all_quarantine_logs.sh

WS="${HOME}/.openclaw/workspace"
RUNTIME="${HOME}/.openclaw/runtime"
LOGDIR="${RUNTIME}/logs"
TRASHER="${WS}/modules/gmail/scripts/gmail_cleanup_trash.py"

: "${GMAIL_TRASH_CONFIRM:=}"

echo "=== $(date -Iseconds) START gmail_trash_all_quarantine_logs ==="
echo "workspace: $WS"
echo "runtime:   $RUNTIME"
echo "trasher:   $TRASHER"
echo "gate:      GMAIL_TRASH_APPLY=${GMAIL_TRASH_APPLY:-0}  GMAIL_TRASH_CONFIRM=${GMAIL_TRASH_CONFIRM:-}"
echo

if [[ ! -f "$TRASHER" ]]; then
  echo "ERROR: trasher not found: $TRASHER"
  exit 1
fi

# Newest first
mapfile -t files < <(ls -1t "${LOGDIR}"/*.quarantine_log 2>/dev/null || true)

if (( ${#files[@]} == 0 )); then
  echo "No quarantine_log files found under: $LOGDIR"
  echo "=== $(date -Iseconds) END gmail_trash_all_quarantine_logs ==="
  exit 0
fi

processed=0
skipped_empty=0
skipped_already=0

for qlog in "${files[@]}"; do
  if [[ ! -s "$qlog" ]]; then
    echo "Skip empty: $qlog"
    ((skipped_empty+=1))
    continue
  fi

  tlog="${qlog}.trash_log"

  # Use python to decide if there's any work left for this qlog
  # (eligible quarantined entries not already in tlog)
  needs_work="$(
    python3 - <<'PY' "$qlog" "$tlog"
import json, sys, pathlib

qlog = pathlib.Path(sys.argv[1])
tlog = pathlib.Path(sys.argv[2])

def load_ids(path: pathlib.Path):
    ids=set()
    if (not path.exists()) or path.stat().st_size == 0:
        return ids
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line=line.strip()
        if not line:
            continue
        try:
            o=json.loads(line)
        except Exception:
            continue
        mid=o.get("id")
        if mid:
            ids.add(mid)
    return ids

trashed=set()
if tlog.exists() and tlog.stat().st_size > 0:
    for line in tlog.read_text(encoding="utf-8", errors="replace").splitlines():
        line=line.strip()
        if not line:
            continue
        try:
            o=json.loads(line)
        except Exception:
            continue
        if o.get("action") == "trashed" and o.get("id"):
            trashed.add(o["id"])

eligible=0
remaining=0
for line in qlog.read_text(encoding="utf-8", errors="replace").splitlines():
    line=line.strip()
    if not line:
        continue
    try:
        o=json.loads(line)
    except Exception:
        continue
    if o.get("action") in ("quarantined","already_quarantined"):
        mid=o.get("id")
        if not mid:
            continue
        eligible += 1
        if mid not in trashed:
            remaining += 1

# Print machine-friendly result
print(f"eligible={eligible} remaining={remaining}")
PY
  )"

  eligible="$(awk -F'[ =]' '{for(i=1;i<=NF;i++) if($i=="eligible") print $(i+1)}' <<<"$needs_work")"
  remaining="$(awk -F'[ =]' '{for(i=1;i<=NF;i++) if($i=="remaining") print $(i+1)}' <<<"$needs_work")"
  eligible="${eligible:-0}"
  remaining="${remaining:-0}"

  if [[ "$remaining" == "0" ]]; then
    echo "Skip already-trashed: $qlog (eligible=$eligible remaining=0)"
    ((skipped_already+=1))
    continue
  fi

  echo "=== Candidate: $qlog (eligible=$eligible remaining=$remaining) ==="

  if [[ "${GMAIL_TRASH_APPLY:-0}" != "1" ]]; then
    echo "DRY_ONLY: would apply trash to remaining=$remaining (set GMAIL_TRASH_APPLY=1 to enable)"
    echo
    continue
  fi

  if [[ "$GMAIL_TRASH_CONFIRM" != "TrashApply" ]]; then
    echo "Refusing trash: set GMAIL_TRASH_CONFIRM=TrashApply"
    exit 2
  fi

  # Preflight dry-run from the trasher (will show up to 20)
  python3 "$TRASHER" --quarantine-log "$qlog" --confirm "$GMAIL_TRASH_CONFIRM"
  # Apply
  python3 "$TRASHER" --quarantine-log "$qlog" --confirm "$GMAIL_TRASH_CONFIRM" --apply

  ((processed+=1))
  echo
done

echo "=== Summary ==="
echo "processed=$processed skipped_empty=$skipped_empty skipped_already_trashed=$skipped_already total_found=${#files[@]}"
echo "=== $(date -Iseconds) END gmail_trash_all_quarantine_logs ==="
