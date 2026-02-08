# Gmail Cleanup Workflow

## Overview
Three-stage workflow to clean up emails from specified senders in the junk Gmail account.

## Stages

### 1. Dry Run (Discovery)
Identifies messages from target senders older than N days.
```bash
python3 scripts/gmail_cleanup_dryrun.py --senders "sender@example.com,another@example.org" --days 180 --samples 20
```

Outputs:
- `mail_cleanup_manifest_YYYY-MM-DD_HHMM.jsonl` - full list of matching messages
- `mail_cleanup_samples_YYYY-MM-DD_HHMM.txt` - sample snippets for review

### 2. Quarantine (Label)
Applies `quarantine/cleanup` label to messages in the manifest.
```bash
python3 scripts/gmail_cleanup_quarantine.py --manifest logs/mail_cleanup_manifest_YYYY-MM-DD_HHMM.jsonl --apply
```

Outputs:
- `mail_cleanup_manifest_YYYY-MM-DD_HHMM.jsonl.quarantine_log` - audit trail

### 3. Trash (Execute)
Moves quarantined messages to Gmail Trash (30-day recovery window).

**Simplified command (uses most recent quarantine log):**
```bash
python3 scripts/gmail_trash_latest.py --confirm TrashApply --apply
```

**Original command (explicit path):**
```bash
python3 scripts/gmail_cleanup_trash.py --quarantine-log logs/mail_cleanup_manifest_YYYY-MM-DD.jsonl.quarantine_log --confirm TrashApply --apply
```

Outputs:
- `.trash_log` appended to quarantine log

## Deiphobe Protocol

When Uther requests trash action, Deiphobe should:

1. Locate most recent quarantine log automatically
2. Request only the confirmation phrase: `TrashApply`
3. Execute using `gmail_trash_latest.py`
4. Report results with message count and log path

**No path required from user.**

## Safety Features

- Dry-run mode for all stages
- Idempotent operations (won't re-process)
- Reversible trash (not permanent delete)
- Full audit trail in logs
- Explicit confirmation phrase required

## Future Enhancements

- [ ] Config file for sender management
- [ ] Auto-scheduling (cron)
- [ ] Pattern-based auto-approval rules
- [ ] Briefing integration

## See Also

- `playbooks/deiphobe_gmail_trash_protocol.md` - Deiphobe's execution protocol
