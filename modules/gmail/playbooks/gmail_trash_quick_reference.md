# Gmail Trash - Quick Reference for Deiphobe

## User Command
When Uther says: "Move quarantined emails to trash" or "Trash the quarantined emails"

## Deiphobe Response Protocol

1. **Acknowledge and request confirmation:**
```
   I'll move the most recent quarantined emails to Gmail Trash (30-day recovery window).
   
   Please confirm with: TrashApply
```

2. **Execute command (after receiving TrashApply):**
```bash
   cd ~/.openclaw/workspace
   python3 scripts/gmail_trash_latest.py --confirm TrashApply --apply
```

3. **Report results:**
```
   ✓ Moved [N] messages to Trash
   Log: [path to .trash_log file]
```

## Important Notes

- Script automatically finds the most recent quarantine log
- No path needed from Uther
- Always runs from within venv if active
- Reversible for 30 days via Gmail Trash
- Requires exact confirmation phrase: `TrashApply` (case-sensitive)

## Error Handling

If no quarantine log found:
```
No quarantine log found. Please run the quarantine step first.
```

If wrong confirmation phrase:
```
Incorrect confirmation phrase. Expected: TrashApply
```
