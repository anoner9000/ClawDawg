INTERNAL — Operator Token Playbook

Purpose
- Document the operator token gating policy and procedures for production task lifecycle operations that require human/operator authorization.

Scope
- Tokens described here are lightweight filesystem tokens used as explicit operator approvals for actions that change production state (e.g., mark TASK complete, apply deployment, purge mail). They are authoritative in the runtime environment and kept outside the repository in ~/.openclaw/runtime/var/operator_tokens/.

Principles
- Explicit: A token file must be present for an agent to perform a gated production action (e.g., marking a task COMPLETE with production=true).
- Append-only audit: Every attempt to perform a gated action (success or blocked) is appended to the team bus (team_bus.jsonl) with details and provenance.
- Minimal surface: Tokens are per-action (e.g., CompleteApply, DeployApply, TrashApply). Each token grants a narrowly-scoped approval and is single-purpose.
- Operator control: Tokens are created and removed only by an operator (human) with local access. Creation and removal are auditable (touch/unlink recorded outside this playbook).

Token mechanics
- Location: ~/.openclaw/runtime/var/operator_tokens/
- File names: descriptive, e.g. CompleteApply, DeployApply, TrashApply
- Permissions: 0640 (owner: kyler, group: kyler or custodian). Tokens must not be world-readable.
- Enforcement: Agent tooling (task_lifecycle_logger.py, deploy scripts, gmail trash apply) will check for the presence of the appropriate token file before performing the gated action. If absent, the agent must log a TASK_UPDATE with state=blocked and details={required_token: <name>} to the bus.

Operator workflow (create a token)
1. Operator decides to approve a gated action.
2. Operator runs locally:
   mkdir -p ~/.openclaw/runtime/var/operator_tokens
   touch ~/.openclaw/runtime/var/operator_tokens/<TokenName>
   chmod 640 ~/.openclaw/runtime/var/operator_tokens/<TokenName>
3. Operator performs or allows the action to proceed (agents will detect token and proceed). After the operation, remove the token:
   rm ~/.openclaw/runtime/var/operator_tokens/<TokenName>
4. Optionally: operator posts an ANNOUNCE on the team bus indicating token creation and intended task (manual step):
   printf '{"ts":"$(date --iso-8601=seconds)","actor":"operator","type":"TOKEN_CREATED","token":"<TokenName>","notes":"<context>"}\n' >> ~/.openclaw/runtime/logs/team_bus.jsonl

Audit & monitoring
- Agents must log both blocked attempts and successful uses to the team bus. Logs must include task_id, agent, ts, and the token name when used.
- Custodian is responsible for periodic checks of operator_tokens directory and must report anomalies to Deiphobe.

Best practices
- Create tokens only for immediate operations and remove them promptly.
- Prefer dry-run and simulation before creating tokens.
- Keep token names narrow and descriptive.
- Treat token files as ephemeral approvals, not permanent credentials.

Example: Mark production task complete
- Agent runs:
  task_lifecycle_logger.py update --agent peabody --task <task_id> --state complete --summary "all tests passed" --production
- task_lifecycle_logger.py checks for ~/.openclaw/runtime/var/operator_tokens/CompleteApply
  - If present: logs TASK_UPDATE(state=complete) and proceeds
  - If absent: logs TASK_UPDATE(state=blocked) with details.required_token=CompleteApply

Notes
- This playbook is internal. Any changes to enforcement code must be reviewed by Peabody and Custodian and approved by Deiphobe.
- The filesystem token approach is intentionally simple and auditable. If you prefer HSM or signed approvals later, we can extend the scheme.
