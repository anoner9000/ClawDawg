#!/usr/bin/env bash
# permissions_audit.sh - report files/dirs with permissive modes under home and .openclaw
if [ -f "$HOME/.openclaw/workspace/.env" ]; then
  source "$HOME/.openclaw/workspace/.env"
fi
RUNTIME_DIR="${OPENCLAW_RUNTIME_DIR:-$HOME/.openclaw/runtime}"
OUT=$RUNTIME_DIR/logs/permissions_audit_$(date -I).log
mkdir -p "$RUNTIME_DIR/logs"
echo "Permissions audit run at $(date -Is)" > "$OUT"
# Check .openclaw dir and credentials
stat -c "%a %n" "$HOME/.openclaw" || true >> "$OUT"
find "$HOME/.openclaw" -maxdepth 2 -type f -printf "%m %p\n" >> "$OUT" || true
# Check for world/group-writable files in home
find "$HOME" -xdev -perm /o+w -type f -printf "%m %p\n" >> "$OUT" || true
# Summary
echo "---- End of report" >> "$OUT"
# Only report if changes since last run
LAST=$HOME/logs/permissions_audit_last.log
if [ -f "$LAST" ]; then
  if ! cmp -s "$OUT" "$LAST"; then
    cp "$OUT" "$LAST"
    echo "$OUT"
  fi
else
  cp "$OUT" "$LAST"
  echo "$OUT"
fi
