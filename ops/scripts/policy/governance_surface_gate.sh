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


# Allowlist: files that may mention governance keywords as documentation/examples
ALLOWLIST_FILES=(
  "docs/governance/"
  "doctrine/"
  "agents/"        # runbooks may show event examples; they are not executable governance
)
# High-signal governance keywords/patterns
# (Tune after report if needed.)
PATTERN='(risk_policy\.yml|risk[_ -]?policy|risk[_ -]?tier|proof_policy\.yml|proof[_ -]?policy|proof[_ -]?receipt|execution[_ -]?receipt|merge[_ -]?gate|policy[_ -]?gate|authority|authz|coderabbit|review[_ -]?agent|require_coderabbit|shepherd_merge|wait_for_check_runs|telegram|sendMessage|api\.telegram)'

is_allowed_path() {
  local p="$1"
  for pref in "${ALLOWED_PREFIXES[@]}"; do
    [[ "$p" == "$pref"* ]] && return 0
  done
  return 1
}


is_allowlisted_path() {
  local p="$1"
  for pref in "${ALLOWLIST_FILES[@]}"; do
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
  if is_allowed_path "$file" || is_allowlisted_path "$file"; then
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
