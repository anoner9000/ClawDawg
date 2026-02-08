#!/usr/bin/env bash
set -euo pipefail

MANIFEST="$(scripts/gmail_latest_manifest_path.sh)"
MAX="${1:-5}"

python3 modules/gmail/scripts/gmail_cleanup_quarantine.py --manifest "${MANIFEST}" --max "${MAX}" --apply
