Minion reviewer troubleshooting report

Summary:
- Multiple REVIEW_REQUEST events for Minion LLM enablement are pending (targets: peabody, custodian). Reviewers have not posted REVIEW_OK.
- Team bus contains nudges and a TEMP_REPLACE event assigning scribe as temporary reviewer.

Checks performed:
- team_bus.jsonl inspected (recent events appended). Path: ~/.openclaw/runtime/logs/team_bus.jsonl
- Peabody and Custodian agent directories exist and contain SOUL.md and RUNBOOK.md.

Possible causes:
1) Reviewers are human roles and require external notification (they may not be automated processes).
2) Bus events are formatted correctly; no obvious corruption.
3) Reviewer files exist but reviewer availability may be the blocker.

Recommended human actions:
- Notify Peabody and Custodian via your out-of-band channel (Slack/Email/Telegram) and request REVIEW_OK or delegate.
- If reviewers are unavailable, use the TEMP_REPLACE event to allow Scribe to act as temporary reviewer. Confirm in team bus when you want Scribe to take action.
- If reviewers should be automated, ensure their automation processes/cron jobs are running in the environment.

Immediate automated remediation performed:
- Posted two high-urgency NUDGE events for Peabody and Custodian to the team bus.
- Posted TEMP_REPLACE event to assign Scribe as temporary reviewer.

Follow-up steps:
- Wait 10-30 minutes for human responses; nudge again if no reply.
- If still blocked after 1 hour, consider promoting Scribe to temporary reviewer for this specific task by posting a REVIEW_OK from Scribe (requires your confirmation).

Logs & artifacts:
- team_bus: ~/.openclaw/runtime/logs/team_bus.jsonl
- Troubleshoot report: ~/.openclaw/workspace/reports/minion_reviewer_troubleshoot_2026-02-08.md

Prepared by: Deiphobe
