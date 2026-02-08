# ops/

Enforcement and tooling.

Contains:
- scripts/    — executable logic (gates, dashboards, automation)
- schemas/    — formal definitions (bus schema, etc.)

Agents may read ops, not modify it.

## Quick commands

### Token usage (today)
```bash
./ops/oc tokens today
# (or directly)
./ops/scripts/ledger/token_today_totals.sh

Ledger report (accounting HTML)
./ops/scripts/ledger/ledger_render_report_accounting_html.py
```
