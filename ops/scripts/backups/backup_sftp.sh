#!/usr/bin/env bash
# backup_sftp.sh - restic-style encrypted backup to SFTP backend (using restic recommended)
# Assumes key-based auth to SFTP host is set up for the user and environment variables are set for RESTIC_PASSWORD
# Example usage: RESTIC_REPOSITORY=sftp:user@host:/path/to/repo RESTIC_PASSWORD_FILE=~/.config/restic/pass restic init
set -euo pipefail
: ${RESTIC_REPOSITORY:?"Set RESTIC_REPOSITORY e.g. sftp:user@host:/path"}
: ${RESTIC_PASSWORD_FILE:?"Set RESTIC_PASSWORD_FILE to file containing repo password (mode 600)"}
export RESTIC_PASSWORD=$(cat "$RESTIC_PASSWORD_FILE")
# Paths to backup
BACKUP_PATHS=("$HOME/.openclaw/credentials" "$HOME/.openclaw/config.yaml")
# Run backup
restic -r "$RESTIC_REPOSITORY" backup "${BACKUP_PATHS[@]}"
# Prune/forget policy (keep 12 monthly, 7 weekly, 30 daily)
restic -r "$RESTIC_REPOSITORY" forget --keep-monthly 12 --keep-weekly 7 --keep-daily 30 --prune || true
# Exit
exit 0
