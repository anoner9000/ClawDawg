Token Rotation Playbook

Purpose
Rotate OPENCLAW and related service tokens safely with a dry-run option and optional monthly automation. Minimize downtime and maintain access.

Overview
- Target tokens: OPENCLAW_GATEWAY_TOKEN, Telegram bot token, any other service API tokens stored under ~/.openclaw/credentials or environment.
- Rotation strategy: generate new token, update config, restart gateway (or service), validate, revoke old token.

Steps — manual dry-run
1) Inventory
   - List tokens: grep -R "token" ~/.openclaw -n || grep -R "OPENCLAW_GATEWAY_TOKEN" ~/.openclaw -n
   - Note current values and which services use them (Telegram, gateway, etc.)
2) Generate new token
   - Method depends on service. For OpenClaw gateway, generate a new random token locally: openssl rand -hex 32
   - Store new token temporarily in a secure local editor (not in shell history).
3) Update config (dry-run)
   - Edit ~/.openclaw/config.yaml (or relevant file) and add the new token under gateway.token or appropriate field; save as config.yaml.test
   - Validate config: openclaw gateway config.get (inspect), or openclaw status --all to ensure no syntax errors
4) Apply in staging (if available)
   - If you have a staging host, apply config there first and test connectivity (recommended). If not, proceed carefully on prod during low-traffic window.
5) Apply in production
   - Backup current config: cp ~/.openclaw/config.yaml ~/.openclaw/config.yaml.bak.$(date -Iseconds)
   - Replace token in live config with new value
   - Restart gateway: sudo systemctl restart openclaw-gateway
6) Validate
   - Check openclaw status, channel connectivity (Telegram), and agent sessions
   - Monitor logs: sudo journalctl -u openclaw -n 200 --no-pager
7) Revoke old token
   - Once validation completes (30–60 minutes), remove old token from config/history and any external services

Automation — monthly rotation (optional)
- Create a script that generates a token, updates config, restarts gateway, validates, and emails/logs report. Because this is sensitive, require manual approval step by default.
- Cron example (monthly): 0 4 1 * * /usr/local/bin/openclaw-rotate-token.sh --dry-run

Safety notes
- Never commit tokens to git. Ensure ~/.openclaw/credentials is mode 700 (done).
- Keep backups before changes. Test in staging when possible.

I can produce the rotation script (with safe prompts) and a monthly cron job if you approve. I will not rotate tokens without your explicit confirmation.
