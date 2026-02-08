#!/usr/bin/env bash
set -euo pipefail

export TZ="${TZ:-America/Chicago}"

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
RUNTIME_DIR="${OPENCLAW_RUNTIME_DIR:-$HOME/.openclaw/runtime}"

echo "== OpenClaw System Audit (Custodian) =="
echo "root=$ROOT"
echo "runtime=$RUNTIME_DIR"
echo

fail=0

section () {
  echo
  echo "## $1"
}

ok () {
  echo "OK  - $1"
}

warn () {
  echo "WARN- $1"
}

err () {
  echo "ERR - $1"
  fail=1
}

# -------------------------------------------------------------------
section "Canonical files"

for f in BOOTSTRAP.md IDENTITY.md USER.md AGENTS.md; do
  if [[ -e "$ROOT/$f" ]]; then
    ok "$f present"
  else
    err "$f missing"
  fi
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

if grep -q "Agents MUST treat doctrine as read-only" "$ROOT/doctrine/README.md"; then
  ok "Doctrine read-only policy present"
else
  warn "Doctrine read-only policy not found"
fi

# -------------------------------------------------------------------
section "Ledger & usage accounting"

USAGE_JSONL="$RUNTIME_DIR/logs/heartbeat/llm_usage.jsonl"
if [[ -f "$USAGE_JSONL" ]]; then
  lines=$(wc -l < "$USAGE_JSONL")
  ok "llm_usage.jsonl present ($lines entries)"
else
  err "llm_usage.jsonl missing"
fi

for s in \
  ops/scripts/ledger/token_today_totals.sh \
  ops/scripts/ledger/token_month_totals.sh
do
  if [[ -x "$ROOT/$s" ]]; then
    ok "$s executable"
  else
    err "$s missing or not executable"
  fi
done

# -------------------------------------------------------------------
section "Heartbeat posture"

if grep -qEv '^\s*($|#)' "$ROOT/HEARTBEAT.md"; then
  warn "Heartbeat enabled (tasks present in HEARTBEAT.md)"
else
  ok "Heartbeat disabled by design (no tasks)"
fi

# -------------------------------------------------------------------
section "Agent layout"

for a in deiphobe scribe custodian; do
  if [[ -d "$ROOT/agents/$a" ]]; then
    ok "agent/$a present"
  else
    err "agent/$a missing"
  fi
done

# -------------------------------------------------------------------
section "Result"

if [[ "$fail" -eq 0 ]]; then
  echo "STATUS=clean"
  exit 0
else
  echo "STATUS=issues_detected"
  exit 1
fi
