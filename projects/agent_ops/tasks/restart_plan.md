# Restart Plan — agent_ops

## A) State recap

### What exists
- `projects/agent_ops/CONTEXT.md` defines purpose and current system invariants.
- `projects/agent_ops/ACCESS.md` defines read/write access by role.
- `projects/agent_ops/tasks/` now exists as the task artifact location.

### Key invariants (from CONTEXT)
- `team_bus.jsonl` is append-only truth.
- Gate requires Deiphobe `APPROVAL` with `expires_at`.
- High/critical `RISK` auto-blocks.
- `UNBLOCKED` is Deiphobe-only.
- Dashboard scripts are read-only.

### What is missing
- No onboarding trial runbook/artifact for Scribe yet.
- No monthly scorecard template artifact yet.
- No local project README/docs/doctrine folder content for operational handoff.

## B) Open items / gaps
- Define a concrete, testable Scribe onboarding trial flow.
- Capture evidence/output format for onboarding completion.
- Define scorecard schema (metrics, cadence, ownership, source-of-truth fields).
- Create first monthly scorecard template in Markdown.
- Add minimal task tracking artifacts under `tasks/` for repeatability.

## C) Reboot plan with concrete next actions

### (a) First agent onboarding trial (Scribe)
1. Create `onboarding/scribe_trial_runbook.md` with preconditions, workflow steps, and gate checkpoints.
2. Create `onboarding/scribe_trial_checklist.md` with operator checklist and sign-off placeholders.
3. Create `onboarding/scribe_trial_acceptance.md` with explicit pass/fail criteria.
4. Create `onboarding/scribe_trial_evidence_template.md` to capture artifacts and observed outcomes.
5. Execute one dry-run walkthrough using runbook + checklist and capture evidence using the template.

### (b) First monthly scorecard template
1. Define schema in `scorecards/schema.md` (required fields, metric definitions, and status model).
2. Create fillable template in `scorecards/scorecard_template.md` aligned to schema.
3. Add event taxonomy placeholder in `bus/event_types.md` so scorecard inputs map to bus events.
4. Produce first monthly instance only after schema and template are approved.

## D) Explicit deliverables: Scribe onboarding trial

### Required documents
- `onboarding/scribe_trial_runbook.md`
- `onboarding/scribe_trial_checklist.md`
- `onboarding/scribe_trial_acceptance.md`
- `onboarding/scribe_trial_evidence_template.md`

### Deliverable expectations
- Runbook: objective, prerequisites, step-by-step procedure, gate checks, rollback/stop conditions.
- Checklist: pre-run checks, in-run checks, post-run checks, owner/date/signature placeholders.
- Acceptance: entry criteria, pass criteria, fail conditions, escalation path.
- Evidence template: run metadata, evidence links/paths, outcome summary, open issues.

### Completion definition
- All four artifacts exist and are reviewable.
- A dry-run references the checklist and records output in evidence template format.
- Acceptance criteria are evaluated and marked pass/fail with notes.

## E) Scorecard schema (initial frame)

### Minimum required fields
- Period metadata (month, start date, end date, generated at).
- Ownership metadata (author, reviewer, approver placeholders).
- KPI entries (name, definition, owner, source, target, actual, status, notes).
- Risk/incidents summary (identifier, severity, status, resolution owner).
- Gate/compliance checks tied to invariants in `CONTEXT.md`.
- Action register (action, owner, due date, status, dependency).

### Status model placeholders
- `on_track`
- `at_risk`
- `off_track`
- `blocked`

### Source linkage
- Each KPI and incident entry should reference a source artifact path or event type key.

## F) Ordered task list (concrete)

| Task | Owner | Size | Dependencies | Success criteria |
|---|---|---|---|---|
| Draft Scribe runbook | Scribe | M | `CONTEXT.md`, `ACCESS.md` | `onboarding/scribe_trial_runbook.md` includes prerequisites, steps, and gates |
| Draft Scribe checklist | Scribe | S | Scribe runbook | `onboarding/scribe_trial_checklist.md` includes pre/in/post checks and sign-off placeholders |
| Draft Scribe acceptance criteria | Deiphobe | S | Scribe runbook | `onboarding/scribe_trial_acceptance.md` defines pass/fail and escalation conditions |
| Draft Scribe evidence template | Scribe | S | Scribe checklist, acceptance criteria | `onboarding/scribe_trial_evidence_template.md` captures evidence and outcome fields |
| Run onboarding dry-run | Scribe + Deiphobe | M | All onboarding docs | One trial executed with recorded evidence and acceptance decision |
| Define scorecard schema | Deiphobe | M | `CONTEXT.md` invariants | `scorecards/schema.md` has required fields and status model |
| Draft monthly scorecard template | Scribe | S | `scorecards/schema.md` | `scorecards/scorecard_template.md` maps all schema fields with placeholders |
| Define bus event types mapping | Deiphobe + Scribe | S | `scorecards/schema.md` | `bus/event_types.md` defines event categories used by scorecard inputs |
| Prepare first monthly scorecard instance | Scribe | M | scorecard template, event type mapping | Instance can be completed without schema gaps |

## G) Blockers / questions
- None currently blocking draft creation.
- Clarification to resolve before execution: who is final approver for scorecard sign-off beyond Deiphobe review (if needed).
<!-- hook test -->
<!-- hook test -->
