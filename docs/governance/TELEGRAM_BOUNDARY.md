# Telegram Boundary

Policy: outbound Telegram sends must be performed only by `executor-comm`.

Enforcement:
- `ops/scripts/comm/telegram_send.sh` hard-requires `OPENCLAW_ACTOR=executor-comm` and a `TASK_ID`.
- Every send writes:
  - `tasks/<task_id>/receipts/telegram_send_result.json`
  - `tasks/<task_id>/receipts/EXECUTION_RECEIPT.json`

Migration:
- Cron jobs must enqueue or dispatch to `executor-comm` rather than calling Telegram directly.

## Step 2 wiring
- Cron calls: `ops/scripts/comm/dispatch_briefing_send.sh`
- Dispatcher derives message TEXT from the briefings module and calls:
  - `ops/scripts/comm/telegram_send.sh` (enforced executor-comm + receipts)
