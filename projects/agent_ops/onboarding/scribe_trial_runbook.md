# Scribe Trial Runbook

## Purpose
- [Placeholder]

## Scope
- [Placeholder]

## Preconditions
- [Placeholder]

## Inputs
- [Placeholder]

## Procedure
1. [Placeholder]
2. [Placeholder]
3. [Placeholder]

## Gate Checks

### Gate 1 — Preconditions satisfied
- All required inputs present: [Yes/No + Placeholder note]
- Checklist available: `onboarding/scribe_trial_checklist.md` [Yes/No]
- Acceptance criteria available: `onboarding/scribe_trial_acceptance.md` [Yes/No]

### Gate 2 — Approval required (if applicable)
- Approval required for this scope: [Yes/No]
- Approval event present (`APPROVAL_GRANTED`): [Placeholder]
- `approval_id` recorded: [Placeholder]
- `expires_at` is in the future at execution time: [Yes/No]
- If approval missing or expired -> **STOP** and record fail condition

### Gate 3 — Risk evaluation
- Risk level assessed: [Placeholder]
- High or Critical risk detected: [Yes/No]
- If High/Critical:
- `RISK_BLOCKED` event emitted: [Yes/No + Placeholder ref]
- Execution halted immediately: [Yes/No]
- If Low/Medium -> continue

### Gate 4 — Unblock authorization (Deiphobe-only)
- Unblock required to proceed: [Yes/No]
- Unblock authorized by Deiphobe: [Yes/No]
- `UNBLOCKED` event present with valid `approval_id`: [Placeholder]
- If unblock not authorized -> **STOP**

### Gate 5 — Evidence integrity
- Required bus events recorded and referenced: [Yes/No]
- Artifact paths captured in evidence template: [Yes/No]
- Evidence maps 1:1 to acceptance criteria: [Yes/No]

### Gate 6 — Final decision
- All gates passed: [Yes/No]
- Outcome recorded in evidence template: [Pass/Fail]
- Decision recorded in acceptance doc: [Yes/No]
