Title: Deiphobe Gmail Trash Protocol — Policy Change (Operator‑approved)

Effective immediately upon saving this file and operator confirmation (see below), Deiphobe will accept the single confirmation token "TrashApply" as the runtime authorization to move messages previously recorded in the quarantine log to Gmail Trash.

Authorization conditions (must all be true)
1. Operator has saved this exact policy text to playbooks/deiphobe_gmail_trash_protocol.md.
2. Operator issues the single runtime confirmation message (case‑sensitive): PolicyUpdated:TrashApply. This serves as proof the operator intentionally changed the protocol.
3. Deiphobe will log the policy change event (file path + operator confirmation + timestamp) before performing any TrashApply action. The log will be stored at: ~/.openclaw/runtime/logs/gmail_policy_changes.log

Runtime behavior after policy change
- On receiving the runtime token "TrashApply" (as one message), Deiphobe will:
a) Verify the policy change timestamp in playbooks/deiphobe_gmail_trash_protocol.md.
b) Append an audit record to ~/.openclaw/runtime/logs/gmail_policy_changes.log containing: operator id (Uther), timestamp, and checksum of the policy file.
c) Execute the existing trash workflow, move quarantined messages to Gmail Trash, and append per‑message results to the quarantine log's trash_log file (same location as existing quarantine logs).
d) Report a QUIET summary: Result + path to the updated quarantine trash_log.

Safeguards retained
- Deiphobe will NOT perform any permanent deletion; only move to Gmail Trash (retained by Gmail ~30 days).
- The policy change itself is auditable and requires operator confirmation before any runtime action.
- All actions and logs remain in ~/.openclaw/runtime/logs and will be retained for review.

Operator signoff (paste the following line into this file to explicit sign and date)
OperatorSignoff: Uther — saved at $(date -Iseconds)
