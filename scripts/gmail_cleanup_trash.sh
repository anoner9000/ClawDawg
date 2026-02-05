#!/usr/bin/env bash
set -euo pipefail
python3 "$(dirname "$0")/../modules/gmail/scripts/gmail_cleanup_trash.py" "$@"
