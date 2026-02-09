#!/usr/bin/env bash
# check_access.sh - dry-run enforcement stub for ACCESS.md rules
# Usage: ./check_access.sh --agent Peabody --file /path/to/target

set -euo pipefail

AGENT="${AGENT:-}"
TARGET_FILE="${TARGET_FILE:-}"

usage(){
  echo "Usage: $0 --agent <AgentName> --file <target-file> [--dry-run]"
  exit 2
}

# parse args
DRY_RUN=1
while (("$#")); do
  case "$1" in
    --agent)
      AGENT="$2"; shift 2;;
    --file)
      TARGET_FILE="$2"; shift 2;;
    --apply)
      DRY_RUN=0; shift;;
    --help)
      usage;;
    *)
      echo "Unknown arg: $1"; usage;;
  esac
done

if [ -z "$AGENT" ] || [ -z "$TARGET_FILE" ]; then
  usage
fi

# canonical ACCESS.md location per project root
# For dry-run, we look for nearest ACCESS.md upwards from TARGET_FILE
find_access(){
  local f="$1"
  while [ "$f" != "/" ]; do
    if [ -f "$f/ACCESS.md" ]; then
      echo "$f/ACCESS.md"
      return 0
    fi
    f=$(dirname "$f")
  done
  return 1
}

ACCESS_PATH=$(find_access "$(dirname "$TARGET_FILE")" ) || true

if [ -z "$ACCESS_PATH" ]; then
  echo "No ACCESS.md found for target: $TARGET_FILE"
  echo "Default policy: deny writes in dry-run unless explicitly allowed."
  echo "Result: DENY (dry-run)"
  exit 0
fi

# ACCESS.md format (simple YAML-ish lines) example:
# allow:
#   Peabody:
#     - write: project/foo/CONTEXT.md
#   Custodian:
#     - write: config.known-good/*

# parse ACCESS.md in a simple way (grep for agent and 'write' entries)
ALLOWED=0
# check exact matches and wildcard suffixes
while IFS= read -r line; do
  # trim
  ltrim=$(echo "$line" | sed -e 's/^[[:space:]]*//')
  if [[ "$ltrim" == "$AGENT":* || "$ltrim" == "$AGENT" ]]; then
    # next lines may contain allowed paths
    agent_block=1
    continue
  fi
  if [[ ${agent_block:-0} -eq 1 ]]; then
    if [[ "$ltrim" =~ ^[A-Za-z] ]] ; then
      # new block
      agent_block=0
      continue
    fi
    # look for write: entries
    if [[ "$ltrim" == *"write:"* ]]; then
      # extract path
      allowed_path=$(echo "$ltrim" | sed -E 's/.*write:[[:space:]]*//')
      # handle wildcard suffix
      if [[ "$allowed_path" == *"*" ]]; then
        prefix=${allowed_path%*}
        if [[ "$TARGET_FILE" == $prefix* ]]; then
          ALLOWED=1; break
        fi
      else
        # resolve relative paths against ACCESS.md dir
        cand="$ACCESS_PATH"/../$allowed_path
        if [ "$(realpath -m "$cand")" = "$(realpath -m "$TARGET_FILE")" ]; then
          ALLOWED=1; break
        fi
      fi
    fi
  fi
done < "$ACCESS_PATH"

if [ "$ALLOWED" -eq 1 ]; then
  echo "ACCESS CHECK: ALLOWED (agent=$AGENT -> $TARGET_FILE) [dry-run=${DRY_RUN}]"
  exit 0
else
  echo "ACCESS CHECK: DENIED (agent=$AGENT -> $TARGET_FILE) [dry-run=${DRY_RUN}]"
  echo "ACCESS policy file used: $ACCESS_PATH"
  exit 0
fi
