#!/usr/bin/env bash
# integrate_minion_guard.sh - scaffold to integrate Minion into rate_guard + heartbeat accounting
# Dry-run scaffold: does not modify live monitoring, prints recommended commands.

MODEL_RATES=~/.openclaw/runtime/config/model_rates.json
RATE_GUARD_SCRIPT=~/.openclaw/workspace/scripts/rate_guard.sh
HEARTBEAT_AGG=~/.openclaw/workspace/scripts/heartbeat_aggregator.sh

cat <<'EOF'
Integration plan (dry-run):
1) Ensure Minion entry exists in MODEL_RATES.
   jq '.minion' $MODEL_RATES

2) rate_guard integration:
   - Add a watch entry for actor 'minion' so every LLM call (or intended call) logs {ts,code,actor,task_id}.
   - Example: rate_guard.sh should accept --actor minion and record to ~/.openclaw/runtime/logs/heartbeat/rate_guard_minion.log

3) heartbeat_aggregator:
   - Include Minion accounting in the daily ledger: aggregate rate_guard_minion.log into ledger reports.
   - Ensure accounting_incomplete flag is set if provenance append fails for any Minion response.

4) Alerts:
   - Create alert rule: if tokens/day > model_rates.minion.tokens_per_day OR requests/day > model_rates.minion.requests_per_day -> create alert event to team_bus.jsonl and mute further live calls.

5) Testing:
   - Run synthetic events (use minion_route.sh) and verify rate_guard entries and heartbeat aggregation.

Run the manual steps below to apply (dry-run):
EOF

echo
echo "STEP 1: show minion model_rates entry:"; jq '.minion' "$MODEL_RATES" || true

echo
cat <<'EOF'
STEP 2 (suggested commands):
# record a Minion LLM request (example)
# ./workspace/scripts/rate_guard.sh --actor minion --record --code 200 --task_id task-123

# Example to aggregate minion logs in heartbeat_aggregator:
# ./workspace/scripts/heartbeat_aggregator.sh --include-actor minion

# Example alert (append-only):
# printf '{"ts":"$(date --iso-8601=seconds)","actor":"custodian","type":"ALERT","summary":"Minion quota exceeded"}\n' >> ~/.openclaw/runtime/logs/team_bus.jsonl
EOF

exit 0
