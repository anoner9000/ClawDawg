# doctrine/

Authoritative rules for how the agent system operates.

Contains:
- playbooks/  — operational procedures
- policies/   — hard safety and authorization rules
- templates/  — reusable starting points

If it changes how agents behave, it belongs here.

## Doctrine policy (write rules)

- `doctrine/` is the canonical reference library: playbooks, policies, and templates.
- **Agents MUST treat doctrine as read-only.** They may read and cite doctrine, but must not modify it.
- **Humans may modify doctrine intentionally** (e.g., to update protocols, templates, and canonical configuration).
- `doctrine/meta/` contains human-maintained canonical configuration that is exposed to agents via repo-root entrypoints (`BOOTSTRAP.md`, `IDENTITY.md`, `USER.md`). Agents still treat `doctrine/meta/` as read-only.

## Communication policy
- doctrine/policies/COMMUNICATION_AUTHZ.md
