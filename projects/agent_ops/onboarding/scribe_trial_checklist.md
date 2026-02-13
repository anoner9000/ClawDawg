# Scribe Trial Checklist

## Pre-Run Checks (Gate 1 — Preconditions)
- [ ] Runbook present and reviewed (`scribe_trial_runbook.md`)
- [ ] Acceptance criteria present (`scribe_trial_acceptance.md`)
- [ ] Evidence template ready (`scribe_trial_evidence_template.md`)
- [ ] Required inputs identified and available
- [ ] Scope defined for this trial

## In-Run Checks (Gate 2 — Approval Validation)
- [ ] Approval required determined (Yes/No recorded)
- [ ] If required: `APPROVAL_GRANTED` event verified
- [ ] `approval_id` captured
- [ ] `expires_at` verified as valid at execution time

## In-Run Checks (Gate 3 — Risk Evaluation)
- [ ] Risk level assessed and recorded
- [ ] If High/Critical: `RISK_BLOCKED` event emitted
- [ ] Execution halted if High/Critical
- [ ] If Low/Medium: continuation documented

## In-Run Checks (Gate 4 — Unblock Authorization)
- [ ] Unblock required determination recorded
- [ ] If unblock required: authorized by Deiphobe
- [ ] `UNBLOCKED` event verified (with valid `approval_id`)

## Post-Run Checks (Gate 5 — Evidence Integrity)
- [ ] Required bus events referenced in evidence template
- [ ] Artifact paths captured
- [ ] Evidence mapped to acceptance criteria

## Post-Run Checks (Gate 6 — Final Decision)
- [ ] Pass/Fail determined
- [ ] Decision recorded in acceptance document
- [ ] Evidence template completed

## Sign-Off
- Operator: [Placeholder]
- Reviewer: [Placeholder]
- Date: [Placeholder]
