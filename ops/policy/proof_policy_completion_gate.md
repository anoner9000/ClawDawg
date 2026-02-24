# Proof Policy — Completion Gate (v2)
`state=complete` is valid only when emitted by `custodian` after PASS proof validation.
Required per-task artifacts:
- `tasks/<task_id>/receipts/EXECUTION_RECEIPT.json`
- `tasks/<task_id>/receipts/PROOF_VALIDATION.json` (PASS)
