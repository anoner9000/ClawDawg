#!/usr/bin/env bash
set -euo pipefail
WINDOW_DAYS="${1:-14}"
exec python3 "$(dirname "$0")/custodian_telemetry_summary.py" "$WINDOW_DAYS"
