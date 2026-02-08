#!/usr/bin/env bash
# gateway_ws_probe.sh - simple WebSocket TCP probe helper
# Usage: gateway_ws_probe.sh <host> <port> <path>
set -euo pipefail
host=${1:-localhost}
port=${2:-18789}
path=${3:-/}
outdir="$HOME/.openclaw/runtime/logs"
mkdir -p "$outdir"
out="$outdir/gateway_ws_probe_$(date -Iseconds).log"
{
  echo "=== probe $(date -Is) ==="
  echo "target: $host:$port$path"
  echo "tcp_connect: $(nc -z -v -w 3 $host $port >/dev/null 2>&1 && echo ok || echo fail)"
  # attempt a minimal HTTP GET to the path
  status=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 6 "http://$host:$port$path" || echo 000)
  echo "http_status: $status"
} > "$out"
echo "$out"
