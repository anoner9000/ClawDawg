#!/usr/bin/env bash
set -euo pipefail
exec "$(dirname "$0")/../modules/briefings/scripts/ingest_ace.sh" "$@"
