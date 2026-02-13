# Edge Cases

## Approval expired mid-run
- Trigger: `expires_at` is no longer valid during execution.
- Action: stop execution, mark fail condition, request/record renewed approval path.

## Approval required but missing event linkage
- Trigger: approval required, but `APPROVAL_GRANTED` or `approval_id` not verifiable.
- Action: stop execution, record missing approval evidence, escalate per acceptance path.

## High/Critical risk with no block record
- Trigger: risk assessed High/Critical but no `RISK_BLOCKED` reference.
- Action: emit/record `RISK_BLOCKED`, halt, and update evidence mapping.

## Unblock attempted without Deiphobe authorization
- Trigger: unblock needed but no Deiphobe authorization evidence.
- Action: remain blocked; do not continue until `UNBLOCKED` linkage is valid.

## Missing bus references in evidence
- Trigger: required event refs absent from evidence template.
- Action: mark incomplete evidence, backfill references, and re-check acceptance mapping.

## Unclear risk classification
- Trigger: risk cannot be classified from available inputs.
- Action: pause execution, escalate for risk determination, and record pending decision.

## Missing required artifact
- Trigger: runbook/checklist/acceptance/evidence document missing or stale.
- Action: stop, restore required artifact path, then restart from preconditions gate.
