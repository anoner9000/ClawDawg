Encrypted Off‑Host Backup Process

Goal
Backup sensitive OpenClaw credentials and configuration to an encrypted off-host location using battle-tested tools (restic or duplicity). Prioritize ease of restore, integrity, and minimal exposure.

Scope
- Source: ~/.openclaw/credentials, ~/.openclaw/config.yaml, /etc/openclaw (if present), any custom scripts related to OpenClaw
- Destination options: remote SFTP server, DigitalOcean Spaces / S3-compatible bucket, or encrypted archive pushed to a private VPS

Recommended tools
1) Restic (preferred)
   - Pros: deduplicating, fast, encrypted, supports S3/SFTP/backends, easy restore
   - Cons: needs repository password; ensure secure storage of repo key
2) Duplicity
   - Pros: incremental, encrypted, S3/SFTP support
   - Cons: slower, more complex CLI

Restic example (S3-compatible)
1) Install restic
   - sudo apt-get install restic
2) Initialize repository (one-time)
   - export AWS_ACCESS_KEY_ID=...; export AWS_SECRET_ACCESS_KEY=...
   - restic -r s3:s3.amazonaws.com/my-bucket init
3) One-off backup
   - restic -r s3:s3.amazonaws.com/my-bucket backup ~/.openclaw/credentials ~/.openclaw/config.yaml
4) Automated cron (daily at 02:00)
   - 0 2 * * * /usr/local/bin/restic-backup.sh
   - restic-backup.sh should export credentials securely (from vault or env file with mode 600) and run backup + forget/prune policies
5) Restore
   - restic -r s3:s3.amazonaws.com/my-bucket restore latest --target /tmp/restore-test

Security best practices
- Use an off-host repository with server-side encryption disabled; let restic handle encryption client-side.
- Store restic repository password in a secrets manager or local file with mode 600; consider using pass or HashiCorp Vault.
- Test restores quarterly.

I can produce the restic backup script (/usr/local/bin/restic-backup.sh) and an encryption-key storage recommendation. Approve target backend (S3-compatible bucket vs SFTP to VPS) and I will draft scripts and cron entries.
