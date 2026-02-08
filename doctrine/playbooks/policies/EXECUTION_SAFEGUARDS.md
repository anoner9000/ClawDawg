Reporting Discipline — QUIET Mode (Default)

Directive (copy/paste-ready):

"Reporting directive — QUIET mode (default): For every action reply use exactly this structure and nothing else:
1) Result: success | fail — one sentence.
2) Artifacts: bullet list of full paths written/updated.
3) Next action needed from me: one short line or ‘none’.
Do not include execution narration, heuristics, parsing details, or internal reasoning unless I explicitly request ‘details’ in the same message. If I write the single word details (case-insensitive) in my next message, include a separate 'Details' section with logs/commands/heuristics for that one reply only.
If no artifacts are created or modified, list 'Artifacts: none'."

Purpose
- Keep implementation summaries concise and operator-focused.
- Prevent noisy or dangerous disclosures (secrets, internal commands).
- Preserve an explicit escape hatch ('details') when deeper transparency is required.

Enforcement
- This rule is binding for all implementation-summary replies produced by the agent unless Uther explicitly waives it for a given message.

Placement
- Pin this file in playbooks/policies and reference it in operation checklists and cron-job documentation.
