#!/usr/bin/env bash
# minion_route.sh - dry-run task router for Minion
BUS=~/.openclaw/runtime/logs/team_bus.jsonl
TASK_ID=${1:-task-$(date +%s)}
OWNER=${2:-unassigned}
SUMMARY=${3:-"no-summary"}
TS=$(date --iso-8601=seconds)
EVENT=$(cat <<EOF
{"ts":"$TS","actor":"minion","action":"route","task_id":"$TASK_ID","owner":"$OWNER","summary":"$SUMMARY","dry_run":true}
EOF
)
mkdir -p "$(dirname "$BUS")"
echo "$EVENT" >> "$BUS"
echo "Dry-run: appended route event to $BUS"
exit 0
