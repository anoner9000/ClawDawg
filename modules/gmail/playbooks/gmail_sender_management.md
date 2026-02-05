Title: Gmail Sender Management — Operator‑approved procedure

Purpose
- Centralize adding/removing senders to the cleanup/quarantine list using the approved sender‑management script to ensure traceability and prevent ad‑hoc edits.

Operator procedure (must follow)
1. To add a sender to the cleanup list, the operator must:
a) Add this entry locally by running the documented sender-management script (see below), or
b) Edit the playbook file and then confirm the change with the operator token (PolicyUpdated:UseSenderScript).

2. The sender-management script (documented below) will:
  • Validate the email address format,
  • Append the sender to ~/.openclaw/runtime/config/gmail_cleanup_senders.json (timestamped entry),
  • Create an audit line in ~/.openclaw/runtime/logs/gmail_sender_changes.log with operator name, sender, timestamp, and checksum of the config file.

3. Runtime behavior:
  • Deiphobe will call the sender-management script when instructed to add a sender only after the operator has saved this playbook and issued the confirmation token PolicyUpdated:UseSenderScript.
  • Manual edits to gmail_cleanup_senders.json are allowed only for emergency rollback and must be followed by an audit entry and operator confirmation.

Sender-management script (reference usage)
- Run locally (WSL) to add a sender:
python3 ~/.openclaw/workspace/scripts/gmail_cleanup_manage_senders.py add "sender@example.com" "Reason"

- Run locally to remove a sender:
python3 ~/.openclaw/workspace/scripts/gmail_cleanup_manage_senders.py remove "sender@example.com"

- List all senders:
python3 ~/.openclaw/workspace/scripts/gmail_cleanup_manage_senders.py list

Audit & logs
- All changes logged to: ~/.openclaw/runtime/logs/gmail_sender_changes.log
- Policy changes recorded to: ~/.openclaw/runtime/logs/gmail_policy_changes.log

Operator signoff (paste this line below to sign and date)
OperatorSignoff: Uther — saved at $(date -Iseconds)
