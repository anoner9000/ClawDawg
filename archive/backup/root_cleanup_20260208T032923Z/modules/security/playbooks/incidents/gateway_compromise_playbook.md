Gateway Compromise — Incident Playbook (expanded)

Purpose: Contain, investigate, remediate, and recover from a suspected Clawdbot/Moltbot gateway compromise.

Summary of today's remediation (2026-02-04)
- Action: Scanner run, exposure scan on port 18789, local-only.
- Findings: Gateway UI responded locally with secure headers; no external exposure on port 80; risk_score 10 for local UI.
- Containment: nftables rule applied to allow only 127.0.0.1 to port 18789; external curl to public IP on 18789 refused.
- Persistence: systemd service enabled for gateway; firewall rules persistent.
- Token posture: advised rotation; operator confirmed token rotation steps are in playbooks/token_rotation_playbook.md

Triage (Immediate)
- Confirm the indicator: review exposure_scan JSONL + runtime gateway logs.
- Create incident folder: ~/.openclaw/runtime/logs/incidents/<YYYY-MM-DD>-gateway
- Snapshot (non-destructive):
  - ss -tunap > inventory.txt
  - ps aux | rg molt|claw > proc.txt
  - docker ps --no-trunc > docker.txt
  - journalctl -u openclaw-gateway -n 500 > gateway_journal.txt

Contain
- Apply host firewall rule to restrict access:
  - nft add rule inet filter input tcp dport 18789 ip saddr 127.0.0.1 accept
  - nft add rule inet filter input tcp dport 18789 drop
- If public exposure found, remove public ACLs and restrict to trusted management CIDR or VPN.

Evidence collection checklist
- Copy runtime logs to incident folder (do not truncate): cp ~/.openclaw/runtime/logs/* incidents/
- Export agent messages and processed manifests from runtime logs
- Preserve browser-side artifacts if available (consent required)

Eradicate
- Patch to fixed release and rebuild from known-good artifacts
- Revoke tokens for affected instances and create new tokens (follow token_rotation_playbook.md)
- Re-deploy patched instance behind firewall

Recover
- Start service behind ACLs and run scanner to confirm no external exposure
- Monitor agent logs and gateway logs for 72 hours

Post-incident actions
- Update CI checks: ensure source maps removed and gatewayUrl overrides not permitted
- Enforce token rotation cadence and add token use monitoring
- Add Sigma rules created to signature store and enable SIEM alerts

Quick commands reference
- Inventory: ss -tunap | tee inventory.txt
- Firewall restrict (example): nft add rule inet filter input tcp dport 18789 ip saddr 127.0.0.1 accept; nft add rule inet filter input tcp dport 18789 drop
- Run scanner: ~/.openclaw/.venv/bin/python ~/.openclaw/workspace/scripts/gateway_exposure_scanner.py --targets /home/kyler/.openclaw/runtime/targets.txt --output ~/.openclaw/runtime/logs/gateway_scan_$(date -I).jsonl

Incident note: remediation completed by operator on 2026-02-04 — local-only exposure confirmed, firewall rules applied, systemd persistence enabled. Keep incident folder for 90 days.
