#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-.}"

# Allowed roots for governance logic
ALLOWED_PREFIXES=(
  "ops/policy/"
  "ops/schemas/"
  "ops/scripts/policy/"
  "ops/governance/"
)

# Directories we scan for violations (everything else)
SCAN_PREFIXES=(
  "agents/"
  "ui/"
  "ops/scripts/agents/"
  "ops/scripts/runtime/"
  "ops/scripts/ui/"
  "scripts/"
  "doctrine/"
)

# High-signal governance keywords/patterns
# (Tune after report if needed.)
PATTERN='(risk[_ -]?tier|proof[_ -]?policy|proof[_ -]?receipt|execution[_ -]?receipt|state[ =:]*complete|TASK_UPDATE|PASS|FAIL|authority|authz|merge[_ -]?gate|policy[_ -]?gate|custodian-only|verification|preflight|investigation-gate|CodeRabbit)'

is_allowed_path() {
  local p="$1"
  for pref in "${ALLOWED_PREFIXES[@]}"; do
    [[ "$p" == "$pref"* ]] && return 0
  done
  return 1
}

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

# Gather matches with file:line:match
for pref in "${SCAN_PREFIXES[@]}"; do
  if [[ -d "$ROOT/$pref" ]]; then
    rg -n --no-heading -S "$PATTERN" "$ROOT/$pref" || true
  fi
done > "$tmp"

# Filter out matches that are inside allowed surfaces (shouldn't happen, but keep logic symmetrical)
violations=0
while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  file="${line%%:*}"
  file="${file#./}"
  if is_allowed_path "$file"; then
    continue
  fi
  echo "$line"
  violations=$((violations+1))
done < "$tmp" > "$tmp.violations" || true

if [[ -s "$tmp.violations" ]]; then
  echo "GOVERNANCE SURFACE VIOLATIONS DETECTED"
  echo "------------------------------------"
  cat "$tmp.violations"
  echo
  echo "Fix: move governance logic into ops/governance or ops/scripts/policy; keep callers thin."
  exit 2
fi

echo "OK: no governance surface violations detected."
