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
  ops/scripts/telemetry/token_today_totals.sh \
  ops/scripts/telemetry/token_month_totals.sh
do
  if [[ -x "$ROOT/$s" ]]; then
    ok "$s executable"
  elif [[ -f "$ROOT/${s}.DISABLED" ]]; then
    warn "${s}.DISABLED present (ledger totals intentionally disabled)"
  else
    err "$s missing"
  fi
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
section "Network exposure"
# Check common OpenClaw service ports for public bindings.
# Override with: OPENCLAW_AUDIT_PORTS="8000,8080"
PORTS_CSV="${OPENCLAW_AUDIT_PORTS:-8000,8080,3000,8787}"
listeners="$(ss -lntH 2>/dev/null || true)"
if [[ -z "$listeners" ]]; then
  warn "Could not read listening sockets (ss unavailable or restricted)"
else
  IFS=',' read -r -a ports <<< "$PORTS_CSV"
  for port in "${ports[@]}"; do
    port="${port//[[:space:]]/}"
    [[ -n "$port" ]] || continue

    if grep -Eq "0\\.0\\.0\\.0:${port}[[:space:]]|\\[::\\]:${port}[[:space:]]" <<< "$listeners"; then
      err "Port $port is publicly exposed (wildcard bind)"
    elif grep -Eq "127\\.0\\.0\\.1:${port}[[:space:]]|\\[::1\\]:${port}[[:space:]]" <<< "$listeners"; then
      ok "Port $port bound to localhost only"
    elif grep -Eq ":[[:digit:]]*[[:space:]]" <<< "$listeners" && grep -Eq ":${port}[[:space:]]" <<< "$listeners"; then
      warn "Port $port is listening on a non-localhost interface"
    else
      ok "Port $port not listening"
    fi
  done
fi

# -------------------------------------------------------------------
section "Agent layout"
for a in deiphobe scribe custodian rembrandt; do
  [[ -d "$ROOT/agents/$a" ]] && ok "agent/$a present" || err "agent/$a missing"
done

# -------------------------------------------------------------------
section "Agent existence (canonical)"

# Canonical definition: an agent exists iff it has a filesystem-backed SOUL.
# Enforce minimum structure: agents/<name>/SOUL.md and agents/<name>/RUNBOOK.md
AGENT_ROOT="$ROOT/agents"

if [[ ! -d "$AGENT_ROOT" ]]; then
  err "agents/ directory missing (cannot establish canonical roster)"
else
  # List agents by SOUL.md presence
  mapfile -t SOULS < <(find "$AGENT_ROOT" -mindepth 2 -maxdepth 2 -type f -name 'SOUL.md' | sort)

  if [[ ${#SOULS[@]} -eq 0 ]]; then
    warn "No filesystem-backed agents found (agents/*/SOUL.md)."
  else
    ok "Filesystem-backed agents: ${#SOULS[@]}"

    # Print roster (stable)
    for soul in "${SOULS[@]}"; do
      name="$(basename "$(dirname "$soul")")"
      rb="$AGENT_ROOT/$name/RUNBOOK.md"
      notes="$AGENT_ROOT/$name/NOTES.md"

      missing=""
      [[ -f "$rb" ]] || missing="${missing} RUNBOOK.md"
      [[ -f "$notes" ]] || missing="${missing} NOTES.md"

      if [[ -n "$missing" ]]; then
        warn "agent=$name present (SOUL.md) but missing:${missing}"
      else
        ok "agent=$name present (SOUL/RUNBOOK/NOTES)"
      fi
    done

    if [[ "${STRICT:-0}" == "1" ]]; then
      # In strict mode, any agent with SOUL.md but missing RUNBOOK.md is an error.
      while IFS= read -r soul; do
        name="$(basename "$(dirname "$soul")")"
        rb="$AGENT_ROOT/$name/RUNBOOK.md"
        [[ -f "$rb" ]] || err "STRICT: agent=$name missing RUNBOOK.md"
      done < <(printf "%s\n" "${SOULS[@]}")
    fi
  fi
fi

# -------------------------------------------------------------------
section "Agent roster (canonical)"
active_agents=()
preferred_agents=(deiphobe scribe custodian rembrandt)

# First, add preferred agents in canonical order when SOUL.md exists.
for a in "${preferred_agents[@]}"; do
  if [[ -f "$ROOT/agents/$a/SOUL.md" ]]; then
    active_agents+=("$a")
  fi
done

# Then append any additional filesystem-backed agents not already listed.
if [[ -d "$ROOT/agents" ]]; then
  while IFS= read -r soul_file; do
    a="$(basename "$(dirname "$soul_file")")"
    seen=0
    for existing in "${active_agents[@]}"; do
      if [[ "$existing" == "$a" ]]; then
        seen=1
        break
      fi
    done
    if [[ "$seen" -eq 0 ]]; then
      active_agents+=("$a")
    fi
  done < <(find "$ROOT/agents" -mindepth 2 -maxdepth 2 -type f -name "SOUL.md" -print | sort)
fi

if [[ "$JSON" -eq 1 ]]; then
  ok "Active agents: ${#active_agents[@]}"
  for agent in "${active_agents[@]}"; do
    ok "active_agent=$agent"
  done
else
  echo "Active agents: ${#active_agents[@]}"
  for agent in "${active_agents[@]}"; do
    echo "- $agent"
  done
fi

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
