#!/usr/bin/env bash
set -euo pipefail

export TZ="${TZ:-America/Chicago}"

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
RUNTIME_DIR="${OPENCLAW_RUNTIME_DIR:-$HOME/.openclaw/runtime}"

STRICT=0
JSON=0

for arg in "$@"; do
  case "$arg" in
    --strict) STRICT=1 ;;
    --json) JSON=1 ;;
    *) ;;
  esac
done

# Accumulators
fail=0
warns=0

# JSON arrays
json_items=""

emit_item () {
  local level="$1" msg="$2"
  if [[ "$JSON" -eq 1 ]]; then
    # minimal JSON escaping for quotes/backslashes
    local esc="${msg//\\/\\\\}"
    esc="${esc//\"/\\\"}"
    json_items+="{\"level\":\"$level\",\"msg\":\"$esc\"},"
  else
    case "$level" in
      OK)   echo "OK  - $msg" ;;
      WARN) echo "WARN- $msg" ;;
      ERR)  echo "ERR - $msg" ;;
    esac
  fi
}

ok()   { emit_item "OK" "$1"; }
warn() { emits=1; ((warns+=1)); emit_item "WARN" "$1"; }
err()  { ((fail=1)); emit_item "ERR" "$1"; }

section () {
  if [[ "$JSON" -eq 0 ]]; then
    echo
    echo "## $1"
  fi
}

if [[ "$JSON" -eq 0 ]]; then
  echo "== OpenClaw System Audit (Custodian) =="
  echo "root=$ROOT"
  echo "runtime=$RUNTIME_DIR"
  echo
fi

# -------------------------------------------------------------------
section "Canonical files"
for f in BOOTSTRAP.md IDENTITY.md USER.md AGENTS.md; do
  [[ -e "$ROOT/$f" ]] && ok "$f present" || err "$f missing"
done

# -------------------------------------------------------------------
section "Symlink integrity"
for f in BOOTSTRAP.md IDENTITY.md USER.md; do
  if [[ -L "$ROOT/$f" ]]; then
    target="$(readlink "$ROOT/$f")"
    [[ -e "$ROOT/$target" ]] && ok "$f → $target" || err "$f broken symlink"
  else
    warn "$f is not a symlink (acceptable if intentional)"
  fi
done

# -------------------------------------------------------------------
section "Doctrine policy"
if [[ -f "$ROOT/doctrine/README.md" ]] && grep -q "Agents MUST treat doctrine as read-only" "$ROOT/doctrine/README.md"; then
  ok "Doctrine read-only policy present"
else
  warn "Doctrine read-only policy not found"
fi

# -------------------------------------------------------------------
section "Ledger & usage accounting"
USAGE_JSONL="$RUNTIME_DIR/logs/heartbeat/llm_usage.jsonl"
if [[ -f "$USAGE_JSONL" ]]; then
  lines=$(wc -l < "$USAGE_JSONL" 2>/dev/null || echo 0)
  ok "llm_usage.jsonl present ($lines entries)"
else
  err "llm_usage.jsonl missing"
fi

for s in \
  ops/scripts/ledger/token_today_totals.sh \
  ops/scripts/ledger/token_month_totals.sh
 do
  [[ -x "$ROOT/$s" ]] && ok "$s executable" || err "$s missing or not executable"
done

# -------------------------------------------------------------------
section "Heartbeat posture"
# enabled only if there are non-comment, non-blank lines
if [[ -f "$ROOT/HEARTBEAT.md" ]] && grep -qEv '^\s*($|#)' "$ROOT/HEARTBEAT.md"; then
  warn "Heartbeat enabled (tasks present in HEARTBEAT.md)"
else
  ok "Heartbeat disabled by design (no tasks)"
fi

# -------------------------------------------------------------------
section "Agent layout"
for a in deiphobe scribe custodian; do
  [[ -d "$ROOT/agents/$a" ]] && ok "agent/$a present" || err "agent/$a missing"
done

# -------------------------------------------------------------------
# Decide status/exit
status="clean"
exit_code=0

if [[ "$fail" -ne 0 ]]; then
  status="issues_detected"
  exit_code=1
elif [[ "$STRICT" -eq 1 && "$warns" -ne 0 ]]; then
  status="warnings_as_errors"
  exit_code=2
fi

if [[ "$JSON" -eq 1 ]]; then
  # trim trailing comma
  json_items="${json_items%,}"
  printf '{"root":"%s","runtime":"%s","status":"%s","errors":%d,"warnings":%d,"items":[%s]}\n' \
    "$ROOT" "$RUNTIME_DIR" "$status" "$fail" "$warns" "$json_items"
else
  echo
  echo "## Result"
  echo "STATUS=$status"
fi

exit "$exit_code"
