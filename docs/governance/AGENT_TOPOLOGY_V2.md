# Agent Topology v2 (Canonical)

## Canonical roster
1. custodian
2. deiphobe
3. executor-code
4. executor-comm
5. executor-doc
6. executor-ui
7. scribe

This roster is authoritative. Any agent directory not listed here is non-canonical and must not be
invoked by production routing.

---

## Roles and authority

### custodian
**Role:** Verifier / Completion Authority  
**Exclusive power:** Only actor allowed to emit `TASK_UPDATE state=complete`.  
**Responsibilities:**
- Validate proof/receipts and record PASS/FAIL evidence.
- Assert canonical invariants (registry/policy applicability), then stop.

**Forbidden:**
- Strategy/roadmapping decisions.
- External comms.
- Code/UI/doc mutation (beyond verifier artifacts).

---

### deiphobe
**Role:** Manager / Approval Authority  
**Responsibilities:**
- Route tasks, sequence work, request rework.
- Emit explicit APPROVAL / UNBLOCKED events when governance requires.

**Forbidden:**
- `state=complete` emission.
- Direct external side effects.

---

### executor-code
**Role:** Code mutation executor  
**Responsibilities:**
- Produce minimal diffs, run verifications, emit execution receipts.

**Forbidden:**
- Approvals, routing, `state=complete`, external sends.

---

### executor-ui
**Role:** UI mutation executor  
**Responsibilities:**
- UI changes + verifications + receipts.

**Forbidden:**
- Approvals, routing, `state=complete`, external sends.

---

### executor-doc
**Role:** Documentation mutation executor  
**Responsibilities:**
- Documentation changes + receipts.

**Forbidden:**
- Approvals, routing, `state=complete`, external sends.

---

### executor-comm
**Role:** External comms executor  
**Responsibilities:**
- All external messaging/API calls (Telegram, etc.) via enforced wrappers.
- Always emit execution receipts for outbound actions.

**Forbidden:**
- Approvals, routing, `state=complete`.

---

### scribe
**Role:** Observer / Context hygiene  
**Responsibilities:**
- Summaries, handoffs, risk notes, traceability.

**Forbidden:**
- Any runtime mutation, external sends, approvals, `state=complete`.

---

## Non-negotiables (hard constraints)
1. **Only custodian may emit** `TASK_UPDATE state=complete`.
2. Executors **never approve** and never declare completion.
3. External comms are **executor-comm only**.
4. Canonical roster is the only allowed production team.

---

## Mechanical enforcement
Enforced in two layers:
- **Runtime hard-block:** status emitter refuses non-custodian completion events.
- **CI boundary gate:** repo audit ensures:
  - AGENTS roster matches canonical list
  - no non-custodian runbook templates include `state=complete`
  - only allowed agents exist in canonical roster
