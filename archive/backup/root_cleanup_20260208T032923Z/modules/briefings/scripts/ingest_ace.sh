#!/usr/bin/env bash
# ingest_ace.sh - local ingestion helper for ACE vault
# Converts memory/YYYY-MM-DD.md into Calendar/YYYY-MM-DD.md if present, and produces a manifest of links
set -euo pipefail
WORKDIR="$PWD"
MEM_DIR="$WORKDIR/memory"
CAL_DIR="$WORKDIR/Calendar"
EFF_DIR="$WORKDIR/Efforts"
ATLAS_DIR="$WORKDIR/Atlas"
MANIFEST="$WORKDIR/ingest_manifest_$(date -I).json"
mkdir -p "$CAL_DIR"
echo "[]" > "$MANIFEST"
for f in "$MEM_DIR"/*.md; do
  [ -e "$f" ] || continue
  base=$(basename "$f")
  dest="$CAL_DIR/$base"
  cp "$f" "$dest"
  # Simple heuristic linking: if file contains 'OpenClaw' link to Efforts/OpenClaw_Hardening.md
  if grep -qi "openclaw" "$dest"; then
    # Add link if not present
    if ! grep -q "Efforts/OpenClaw_Hardening.md" "$dest"; then
      echo -e "\n\nLinks:\n- Efforts/OpenClaw_Hardening.md" >> "$dest"
    fi
  fi
  # Append to manifest
  jq -n --arg file "$dest" '{file:$file}' >> "$MANIFEST" || true
done
echo "Ingestion complete. Manifest: $MANIFEST"
