# custodian — RUNBOOK (v2)
- Only custodian may emit `state=complete`.
- Completion requires:
  - `tasks/<task_id>/receipts/EXECUTION_RECEIPT.json`
  - `tasks/<task_id>/receipts/PROOF_VALIDATION.json` with `result=PASS`
