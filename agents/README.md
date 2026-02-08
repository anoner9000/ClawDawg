# agents/

Agent identities and role-specific guidance.

Each agent has:
- SOUL.md     — identity, constraints, promotion rules
- RUNBOOK.md  — how the agent operates day to day
- NOTES.md    — curated learnings (not raw logs)

Agents never write to doctrine directly.

## Doctrine interaction rule
Agents may READ doctrine freely (playbooks, templates, policies).
Agents must NOT WRITE to doctrine. Any proposed doctrine change must be described as a patch for a human to apply.
