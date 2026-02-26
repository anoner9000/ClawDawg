# OpenClaw Agents (Canonical Roster)

This file is the **single canonical roster**. Any agent not listed here is **non-canonical**.

## Canonical Agents
- `custodian` — Verifier. Only agent allowed to emit `TASK_UPDATE state=complete` after PASS proof validation.
- `deiphobe` — Planner. Strategy + sequencing only. Never executes. Never completes.
- `scribe` — Recorder + Timekeeper. Documentation, handoffs, and authoritative time queries via `agents/scribe/time_now.py`. Never executes. Never completes.
- `executor-ui` — Worker. UI tasks only. Emits `EXECUTION_RECEIPT.json`. Never completes.
- `executor-code` — Worker. Code tasks only. Emits `EXECUTION_RECEIPT.json`. Never completes.
- `executor-doc` — Worker. Docs tasks only. Emits `EXECUTION_RECEIPT.json`. Never completes.
- `executor-comm` — Worker. **Only** Telegram outbound actor. Emits `EXECUTION_RECEIPT.json`. Never completes.

## Completion Contract (Hard-Block)
Completion is valid only when:
1) `tasks/<task_id>/receipts/EXECUTION_RECEIPT.json` exists, and
2) `tasks/<task_id>/receipts/PROOF_VALIDATION.json` exists with `result=PASS`, and
3) `state=complete` is emitted by `custodian` only.
