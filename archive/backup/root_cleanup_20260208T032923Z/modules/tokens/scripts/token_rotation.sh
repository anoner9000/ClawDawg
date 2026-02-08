#!/usr/bin/env bash
# token_rotation.sh - safe token rotation helper for OpenClaw gateway and related tokens
# Usage: ./token_rotation.sh --dry-run | --apply
set -euo pipefail
DRY_RUN=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=true; shift ;;
    --apply) DRY_RUN=false; shift ;;
    --help) echo "Usage: $0 [--dry-run|--apply]"; exit 0 ;;
    *) echo "Unknown arg $1"; exit 1 ;;
  esac
done
# 1) Inventory
echo "Inventory: searching for token-like entries under $HOME/.openclaw"
grep -R --line-number -I "token\|secret\|gateway" "$HOME/.openclaw" || true
# 2) Generate new token (local random)
NEW_TOKEN=$(openssl rand -hex 32)
echo "Generated candidate token: ${NEW_TOKEN:0:8}..."
# 3) Show proposed config change (dry-run)
if [ "$DRY_RUN" = true ]; then
  echo "DRY RUN: will not modify live config. Proposed action: replace gateway token in config with new token."
  echo "Please review:"
  echo "  - Backup current config before applying: cp ~/.openclaw/config.yaml ~/.openclaw/config.yaml.bak"
  echo "  - To apply: rerun with --apply"
  exit 0
fi
# 4) Apply
echo "Applying token rotation: backing up current config"
cp "$HOME/.openclaw/config.yaml" "$HOME/.openclaw/config.yaml.bak.$(date -Iseconds)"
# Naive replace: looks for OPENCLAW_GATEWAY_TOKEN or gateway.token
if grep -q "OPENCLAW_GATEWAY_TOKEN" "$HOME/.openclaw/config.yaml"; then
  sed -i "s/\(OPENCLAW_GATEWAY_TOKEN:\s*\).*$/\1${NEW_TOKEN}/" "$HOME/.openclaw/config.yaml"
else
  # fallback: attempt YAML key gateway.token
  python3 - <<PY
import sys,ruamel.yaml
from ruamel.yaml import YAML
yaml=YAML()
with open('$HOME/.openclaw/config.yaml') as f:
    data=yaml.load(f)
if 'gateway' not in data:
    data['gateway']={}
data['gateway']['token']='${NEW_TOKEN}'
with open('$HOME/.openclaw/config.yaml','w') as f:
    yaml.dump(data,f)
print('Updated config.yaml with new gateway.token')
PY
fi
# 5) Restart gateway
echo "Restarting openclaw gateway (requires sudo)."
sudo systemctl restart openclaw-gateway
sleep 2
openclaw status
# 6) Validate
echo "Validation: check channel connectivity and sessions"
openclaw status --deep || true
# 7) Recommend revoking old token from external services after 30-60 min of stable operation
echo "Rotation complete. Verify services for 30-60 minutes before revoking old token."
