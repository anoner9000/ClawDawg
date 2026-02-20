#!/usr/bin/env bash
set -euo pipefail

PR_NUMBER="${1:-}"
REPO="${GITHUB_REPOSITORY:-${REPO:-}}"
[ -n "$PR_NUMBER" ] || { echo "usage: $0 <pr_number>"; exit 2; }
[ -n "$REPO" ] || { echo "ERROR: REPO not set (e.g., anoner9000/ClawDawg)"; exit 2; }

need_cmd() { command -v "$1" >/dev/null 2>&1 || { echo "ERROR: missing $1"; exit 2; }; }
need_cmd gh
need_cmd jq

POST="$HOME/.openclaw/workspace/ops/scripts/status/post_event.sh"
if [[ ! -x "$POST" ]]; then
  echo "ERROR: post_event.sh not executable: $POST"
  exit 2
fi

scribe_close_task() {
  set -euo pipefail

  if [[ $# -lt 3 ]]; then
    echo "Usage: scribe_close_task <task_id> <report_path> <summary>"
    return 2
  fi

  local TASK_ID="$1"
  local REPORT_PATH="$2"
  local SUMMARY="$3"
  local TASK_LANE="$HOME/.openclaw/runtime/logs/status/tasks/$TASK_ID/scribe.jsonl"
  local BUS="$HOME/.openclaw/runtime/logs/team_bus.jsonl"

  if [[ ! -f "$REPORT_PATH" ]]; then
    echo "ERROR: report_path does not exist: $REPORT_PATH"
    return 2
  fi

  # Idempotency: no-op if completion already exists.
  if [[ -f "$TASK_LANE" ]]; then
    if jq -n -e '
      reduce inputs as $ev (false;
        . or ($ev.type=="TASK_UPDATE" and ($ev.state=="complete" or $ev.status=="complete"))
      )' < "$TASK_LANE" >/dev/null 2>&1; then
      echo "✔ already complete (persisted): $TASK_ID"
      return 0
    fi
  elif [[ -f "$BUS" ]]; then
    if jq -n -e --arg t "$TASK_ID" '
      reduce inputs as $ev (false;
        . or ($ev.task_id==$t and $ev.type=="TASK_UPDATE" and ($ev.state=="complete" or $ev.status=="complete"))
      )' < "$BUS" >/dev/null 2>&1; then
      echo "✔ already complete (bus): $TASK_ID"
      return 0
    fi
  fi

  jq -n \
    --arg actor "shepherd" \
    --arg type "STATUS_REPORT" \
    --arg task_id "$TASK_ID" \
    --arg report_path "$REPORT_PATH" \
    --arg summary "$SUMMARY" \
    --argjson dry_run false \
    '{actor:$actor,type:$type,task_id:$task_id,report_path:$report_path,summary:$summary,dry_run:$dry_run}' \
  | "$POST" >/dev/null

  jq -n \
    --arg actor "shepherd" \
    --arg type "TASK_UPDATE" \
    --arg task_id "$TASK_ID" \
    --arg state "complete" \
    --arg summary "$SUMMARY" \
    --argjson dry_run false \
    '{actor:$actor,type:$type,task_id:$task_id,state:$state,summary:$summary,dry_run:$dry_run}' \
  | "$POST" >/dev/null

  echo "✔ Scribe receipt + completion emitted for task: $TASK_ID"
}

echo "[shepherd] repo=$REPO pr=$PR_NUMBER"

# 1) Pull PR facts.
pr_json="$(gh api "repos/$REPO/pulls/$PR_NUMBER")"
draft="$(jq -r '.draft' <<<"$pr_json")"
state="$(jq -r '.state' <<<"$pr_json")"
head_sha="$(jq -r '.head.sha' <<<"$pr_json")"
if [ "$state" != "open" ] || [ "$draft" = "true" ]; then
  echo "[shepherd] skip: state=$state draft=$draft"
  exit 0
fi

# 2) Must be risk:low.
labels="$(jq -r '.labels[].name' <<<"$pr_json" | tr '\n' ' ')"
if ! jq -e '.labels[].name | select(.=="risk:low")' >/dev/null <<<"$pr_json"; then
  echo "[shepherd] skip: not risk:low (labels: $labels)"
  exit 0
fi

# 3) Required checks from gate output first; fallback to YAML contract.
required_checks=()
policy_source="ops/policy/risk_policy.yml"
check_source="risk_policy.yml"
if [ -f gate_output.json ] || [ -f gate.json ]; then
  if [ -f gate_output.json ]; then
    echo "[shepherd] using requiredChecks from gate_output.json"
    mapfile -t required_checks < <(jq -r '.requiredChecks[]? // empty' gate_output.json)
    check_source="gate_output.json"
  else
    echo "[shepherd] using requiredChecks from gate.json"
    mapfile -t required_checks < <(jq -r '.requiredChecks[]? // empty' gate.json)
    check_source="gate.json"
  fi
else
  echo "[shepherd] using required_checks from risk_policy.yml"
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

# 4) Unresolved review threads must be 0 (paginated).
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

# 5) Mergeability gate.
mergeable="$(jq -r '.mergeable // empty' <<<"$pr_json")"
if [ "$mergeable" != "true" ]; then
  echo "[shepherd] block: mergeable=$mergeable (may be computing)"
  exit 0
fi

# 6) Merge.
echo "[shepherd] OK: conditions satisfied; merging PR #$PR_NUMBER"
gh pr merge "$PR_NUMBER" --repo "$REPO" --squash --delete-branch=false
echo "[shepherd] merge command issued"

# 7) On successful merge, emit Scribe receipt+closure with audit metadata.
post_merge_json="$(gh api "repos/$REPO/pulls/$PR_NUMBER")"
merged="$(jq -r '.merged' <<<"$post_merge_json")"
if [ "$merged" != "true" ]; then
  echo "[shepherd] WARN: merge command returned but PR is not marked merged yet; skipping scribe_close_task."
  exit 0
fi
merge_sha="$(jq -r '.merge_commit_sha // empty' <<<"$post_merge_json")"
if [ -z "$merge_sha" ]; then
  merge_sha="$head_sha"
fi

task_id="merge-receipt-pr${PR_NUMBER}-${merge_sha:0:7}"
report_dir="$HOME/.openclaw/runtime/logs/status/tasks/$task_id"
report_path="$report_dir/scribe-report.md"
mkdir -p "$report_dir"

required_checks_csv="$(printf '%s\n' "${required_checks[@]}" | paste -sd ', ' -)"
cat > "$report_path" <<EOF
# Merge Receipt — PR #$PR_NUMBER

## Repository
- repo: $REPO

## Merge Details
- PR: #$PR_NUMBER
- headSha: $head_sha
- mergeSha: $merge_sha
- riskTier: low
- policySource: $policy_source
- requiredChecks: $required_checks_csv
- checkRunSource: $check_source

## Governance
- Merge permitted because riskTier == low
- Required checks verified green before merge
- Unresolved review threads: 0

## Notes
This receipt was published by Scribe (L1, non-executing observer) via shepherd automation.
EOF

summary="Published merge receipt for PR #$PR_NUMBER (riskTier=low, headSha=$head_sha, mergeSha=$merge_sha, requiredChecks=$required_checks_csv, source=$check_source)."
scribe_close_task "$task_id" "$report_path" "$summary"
