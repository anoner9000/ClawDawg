#!/usr/bin/env bash
set -euo pipefail
bash "$(dirname "$0")/../modules/briefings/scripts/morning_briefing_run_and_send.sh" "$@"
