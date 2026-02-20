#!/usr/bin/env bash
set -euo pipefail

PR_NUMBER="${1:-}"
REPO="${GITHUB_REPOSITORY:-${REPO:-}}"
[ -n "$PR_NUMBER" ] || { echo "usage: $0 <pr_number>"; exit 2; }
[ -n "$REPO" ] || { echo "ERROR: REPO not set (e.g., anoner9000/ClawDawg)"; exit 2; }

need_cmd() { command -v "$1" >/dev/null 2>&1 || { echo "ERROR: missing $1"; exit 2; }; }
need_cmd gh
need_cmd jq

echo "[shepherd] repo=$REPO pr=$PR_NUMBER"

# 1) Pull PR facts
pr_json="$(gh api "repos/$REPO/pulls/$PR_NUMBER")"

draft="$(jq -r '.draft' <<<"$pr_json")"
state="$(jq -r '.state' <<<"$pr_json")"
head_sha="$(jq -r '.head.sha' <<<"$pr_json")"

if [ "$state" != "open" ] || [ "$draft" = "true" ]; then
  echo "[shepherd] skip: state=$state draft=$draft"
  exit 0
fi

# 2) Must be risk:low label
labels="$(jq -r '.labels[].name' <<<"$pr_json" | tr '\n' ' ')"
if ! jq -e '.labels[].name | select(.=="risk:low")' >/dev/null <<<"$pr_json"; then
  echo "[shepherd] skip: not risk:low (labels: $labels)"
  exit 0
fi

# 3) Required checks green on head SHA (contract-driven)
# Determine required checks (contract-driven)
required_checks=()

if [ -f gate_output.json ]; then
  echo "[shepherd] using requiredChecks from gate_output.json"
  # gate emits requiredChecks as a JSON array
  mapfile -t required_checks < <(jq -r '.requiredChecks[]? // empty' gate_output.json)
else
  echo "[shepherd] using required_checks from risk_policy.yml"
  # fallback: read contract directly
  mapfile -t required_checks < <(python3 - <<'PY'
import yaml
p = yaml.safe_load(open("ops/policy/risk_policy.yml", "r", encoding="utf-8"))
req = (p.get("tiers", {}).get("low", {}) or {}).get("required_checks", []) or []
for x in req:
    print(str(x))
PY
  )
fi

if [ "${#required_checks[@]}" -eq 0 ]; then
  echo "[shepherd] block: required_checks empty; refusing"
  exit 0
fi

checks_json="$(gh api "repos/$REPO/commits/$head_sha/check-runs" -H "Accept: application/vnd.github+json")"

require_check_green() {
  local name="$1"
  local status conclusion
  status="$(jq -r --arg n "$name" '.check_runs[] | select(.name==$n) | .status' <<<"$checks_json" | head -n1)"
  conclusion="$(jq -r --arg n "$name" '.check_runs[] | select(.name==$n) | .conclusion' <<<"$checks_json" | head -n1)"
  if [ -z "${status:-}" ] || [ -z "${conclusion:-}" ]; then
    echo "[shepherd] block: missing check '$name'"
    return 1
  fi
  if [ "$status" != "completed" ] || [ "$conclusion" != "success" ]; then
    echo "[shepherd] block: check not green '$name' status=$status conclusion=$conclusion"
    return 1
  fi
  return 0
}

for check in "${required_checks[@]}"; do
  [ -n "$check" ] || continue
  require_check_green "$check" || exit 0
done

# 4) Unresolved review threads must be 0 (paginate)
owner="${REPO%/*}"
name="${REPO#*/}"

unresolved=0
cursor=null

while :; do
  page="$(
    gh api graphql -f query='
      query($o:String!, $n:String!, $num:Int!, $after:String) {
        repository(owner:$o, name:$n) {
          pullRequest(number:$num) {
            reviewThreads(first:100, after:$after) {
              pageInfo { hasNextPage endCursor }
              nodes { isResolved }
            }
          }
        }
      }' \
      -F o="$owner" -F n="$name" -F num="$PR_NUMBER" -F after="$cursor"
  )"

  # count unresolved in this page
  page_unresolved="$(jq '[.data.repository.pullRequest.reviewThreads.nodes[]? | select(.isResolved==false)] | length' <<<"$page")"
  unresolved=$((unresolved + page_unresolved))

  has_next="$(jq -r '.data.repository.pullRequest.reviewThreads.pageInfo.hasNextPage' <<<"$page")"
  if [ "$has_next" != "true" ]; then
    break
  fi
  cursor="$(jq -r '.data.repository.pullRequest.reviewThreads.pageInfo.endCursor' <<<"$page")"
done

if [ "$unresolved" -ne 0 ]; then
  echo "[shepherd] block: unresolved review threads=$unresolved"
  exit 0
fi

# 5) Mergeability
mergeable="$(jq -r '.mergeable // empty' <<<"$pr_json")"
# mergeable can be null briefly; treat null as "not ready"
if [ "$mergeable" != "true" ]; then
  echo "[shepherd] block: mergeable=$mergeable (may be computing)"
  exit 0
fi

echo "[shepherd] OK: conditions satisfied; merging PR #$PR_NUMBER"
gh pr merge "$PR_NUMBER" --repo "$REPO" --squash --delete-branch=false
echo "[shepherd] merge command issued"
