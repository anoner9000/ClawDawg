Automation Authorization & Guardrails (finalized)

Scope additions (external systems)
- "External systems" includes Gmail/Google APIs, Telegram, Git remotes, cloud consoles (AWS/GCP/Azure), and any third-party APIs.

Autonomous actions (safe, local, low-risk)
- Read non-sensitive workspace files and show summaries or listings.
- Create, edit, and move files inside the workspace/runtime per automation policies (scripts, playbooks, logs).
- Run non-privileged commands and scripts in the workspace (dry runs, parsing, local-only tools).
- Schedule or enable local timers/cron jobs previously approved by the operator.
- Create safe, non-destructive scripts and present them for operator execution or review.

Actions requiring explicit operator approval
- Any action that modifies external systems or persistent service state, including but not limited to: Gmail/Google APIs (labeling or deleting), Telegram sends, pushing to Git remotes, making changes in cloud consoles, or using third-party APIs with effects.
- Any deletion, move, or modification of user data outside the runtime (emails, remote files, backups) unless pre-approved and confirmed in the moment.
- Creating or placing secrets/credentials in the workspace or remote services; operator must provide or execute secure steps locally.

Actions never taken without confirmation
- Permanent deletion of data (emails, files, backups).  Deletion requires: reviewed manifest + quarantine log + explicit "apply" confirmation.
- Revoking or creating API keys on external services.
- Pushing commits to a remote repo automatically (auto-push only after operator config and opt-in).
- Running sudo/privileged commands that affect system integrity or other users.

Email-specific guardrails
- Dry-run listing: use only Gmail API scope: gmail.readonly. Dry-runs are non-destructive.
- Quarantine: requires gmail.modify and must be run only after operator review of the manifest and samples; action gated by explicit operator "apply".
- Move to Trash (reversible): allowed only after reviewed manifest + completed quarantine step + explicit operator approval to 'TrashApply'.
- Permanent delete: never executed manually; rely on Gmail's 30-day Trash auto‑expiry for permanent removal. Explicit manual permanent deletes are disallowed.

Reporting format (operator-facing)
- Default: QUIET mode (see EXECUTION_SAFEGUARDS for structure). Do not include artifact or next-action lines unless there is an actual artifact to reference or a decision required.

Enforcement
- This file is the authoritative guard. The agent must reference it before performing any action that touches external systems or data.

Version: 2026-02-04
Saved by: Deiphobe
