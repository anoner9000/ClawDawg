# Timekeeping & Reminders (Canonical)

## Authority
**Scribe is the sole authority for time and reminders.**

No other agent is allowed to:
- compute "in 1 hour" into an absolute time
- infer reminder status from memory
- claim a reminder is pending/delivered without querying Scribe’s ledger

## Reminder ledger = receipts
Append-only receipts at:
- `memory/reminders.jsonl`

Receipt events:
- `created`
- `attempted`
- `delivered`
- `missed`
- `canceled`

## Usage (Scribe runs; others request)
- Create: `OPENCLAW_AGENT=scribe python3 agents/scribe/remind.py create --agent deiphobe --content "Drink water" --in 1h`
- Pulse:  `python3 services/reminders.py pulse` (run on cadence, e.g., every minute)
