#!/usr/bin/env bash
# ingest_ace.sh - local ingestion helper for ACE vault
# Converts memory/YYYY-MM-DD.md into Calendar/YYYY-MM-DD.md if present, and produces a manifest of links
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ingest_ace.sh [--dry-run|-n] [--manifest-dir DIR]

Options:
  --dry-run, -n       Simulate ingestion without copying files or modifying links.
  --manifest-dir DIR  Directory to write the manifest JSON (default: $HOME/logs/ingest).
  --help              Show this message.

Dry-run mode:
  - No files are copied into Calendar/
  - No link annotations are appended
  - Manifest still records the actions that would have occurred
EOF
}

DRY_RUN=0
DEFAULT_MANIFEST_DIR="$HOME/logs/ingest"
MANIFEST_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run|-n)
      DRY_RUN=1
      shift
      ;;
    --manifest-dir)
      MANIFEST_DIR="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
WORKDIR="$ROOT_DIR"
MEM_DIR="$WORKDIR/memory"
CAL_DIR="$WORKDIR/Calendar"
MANIFEST_BASE_DIR="${MANIFEST_DIR:-$DEFAULT_MANIFEST_DIR}"
TIMESTAMP="$(date -Iseconds | tr ':' '-')"
MANIFEST="$MANIFEST_BASE_DIR/ingest_manifest_${TIMESTAMP}.json"
TMP_MANIFEST="$(mktemp)"
HISTORY_FILE="$HOME/logs/ingest/history.jsonl"

echo "[]" > "$TMP_MANIFEST"

if [[ ! -d "$MEM_DIR" ]]; then
  echo "Memory directory not found: $MEM_DIR" >&2
  exit 1
fi

if [[ $DRY_RUN -eq 0 ]]; then
  mkdir -p "$CAL_DIR"
else
  echo "[dry-run] Calendar directory will be assumed at $CAL_DIR"
fi

mkdir -p "$MANIFEST_BASE_DIR"
mkdir -p "$(dirname "$HISTORY_FILE")"

shopt -s nullglob
files=("$MEM_DIR"/*.md)
shopt -u nullglob

if [[ ${#files[@]} -eq 0 ]]; then
  echo "No memory files found to ingest."
fi

file_count=0
link_needed_count=0

append_manifest() {
  local entry_json="$1"
  jq --argjson entry "$entry_json" '. + [$entry]' "$TMP_MANIFEST" > "$TMP_MANIFEST.tmp"
  mv "$TMP_MANIFEST.tmp" "$TMP_MANIFEST"
}

for f in "${files[@]}"; do
  base="$(basename "$f")"
  dest="$CAL_DIR/$base"
  action="copy"
  link_action="none"
  would_create_dir=0

  if [[ ! -d "$CAL_DIR" ]]; then
    would_create_dir=1
  fi

  if [[ $DRY_RUN -eq 1 ]]; then
    action="would-copy"
    echo "[dry-run] Would copy $f -> $dest"
  else
    echo "Copying $f -> $dest"
    cp "$f" "$dest"
  fi

  needs_link=0
  if grep -qi "openclaw" "$f"; then
    if [[ $DRY_RUN -eq 1 ]]; then
      needs_link=1
      link_action="would-append Efforts/OpenClaw_Hardening.md"
      echo "[dry-run] Would append link to Efforts/OpenClaw_Hardening.md in $dest"
    else
      if ! grep -q "Efforts/OpenClaw_Hardening.md" "$dest"; then
        needs_link=1
        link_action="appended Efforts/OpenClaw_Hardening.md"
        printf '\n\nLinks:\n- Efforts/OpenClaw_Hardening.md\n' >> "$dest"
      else
        link_action="link-already-present"
      fi
    fi
  else
    link_action="not-needed"
  fi

  entry=$(jq -n \
    --arg source "$f" \
    --arg destination "$dest" \
    --arg action "$action" \
    --arg link_action "$link_action" \
    --argjson dry_run "$([[ $DRY_RUN -eq 1 ]] && echo true || echo false)" \
    --argjson link_needed "$([[ $needs_link -eq 1 ]] && echo true || echo false)" \
    --argjson calendar_would_be_created "$([[ $would_create_dir -eq 1 ]] && echo true || echo false)" \
    '{source:$source,destination:$destination,action:$action,link_action:$link_action,dry_run:$dry_run,link_needed:$link_needed,calendar_would_be_created:$calendar_would_be_created}')

  append_manifest "$entry"

  ((file_count+=1))
  if [[ $needs_link -eq 1 ]]; then
    ((link_needed_count+=1))
  fi

done

mv "$TMP_MANIFEST" "$MANIFEST"

history_entry=$(jq -c -n \
  --arg timestamp "$TIMESTAMP" \
  --arg manifest "$MANIFEST" \
  --argjson dry_run "$([[ $DRY_RUN -eq 1 ]] && echo true || echo false)" \
  --argjson file_count "$file_count" \
  --argjson link_needed_count "$link_needed_count" \
  --argjson errors '[]' \
  '{timestamp:$timestamp,manifest:$manifest,dry_run:$dry_run,file_count:$file_count,link_needed_count:$link_needed_count,errors:$errors}')

printf '%s\n' "$history_entry" >> "$HISTORY_FILE"

echo "Ingestion complete. Manifest: $MANIFEST"
if [[ $DRY_RUN -eq 1 ]]; then
  echo "Dry-run mode: no files were modified."
fi
