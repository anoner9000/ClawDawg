#!/usr/bin/env python3
"""
ledger_render_report.py

Render a human-readable ledger report from llm_usage.jsonl.
This script NEVER modifies the ledger. It is read-only.
"""

import json
import os
import datetime
from pathlib import Path

HOME = Path.home()
RUNTIME_DIR = Path(os.environ.get("OPENCLAW_RUNTIME_DIR", HOME / ".openclaw" / "runtime"))
LEDGER = RUNTIME_DIR / "logs" / "heartbeat" / "llm_usage.jsonl"
OUT = RUNTIME_DIR / "logs" / "heartbeat" / "ledger_report_latest.txt"

def fmt_int(n):
    return f"{n:,}"

def fmt_money(n):
    return f"${n:,.6f}"


def as_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def as_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def entry_date(rec):
    date_value = rec.get("date")
    if date_value not in (None, ""):
        return str(date_value)

    created_at = rec.get("created_at", rec.get("created"))
    if created_at in (None, ""):
        return "(missing)"

    try:
        ts = int(float(created_at))
        return datetime.datetime.fromtimestamp(ts).date().isoformat()
    except Exception:
        return "(missing)"

lines = []
now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

lines.append("════════════════════════════════════════════")
lines.append("OpenClaw Usage Ledger — Human Report")
lines.append("════════════════════════════════════════════")
lines.append(f"Generated: {now}")
lines.append(f"Ledger: {LEDGER}")
lines.append("")

if not LEDGER.exists():
    lines.append("⚠ Ledger file not found.")
else:
    with LEDGER.open("r", encoding="utf-8") as f:
        entries = [line.strip() for line in f if line.strip()]

    if not entries:
        lines.append("Ledger is empty.")
    else:
        summary_entries = 0
        summary_input = 0
        summary_output = 0
        summary_total = 0
        summary_cost = 0.0

        for raw in entries:
            try:
                rec = json.loads(raw)
            except Exception:
                rec = {}

            input_tokens = as_int(rec.get("input_tokens", 0), 0)
            output_tokens = as_int(rec.get("output_tokens", 0), 0)
            total_tokens = as_int(rec.get("total_tokens", input_tokens + output_tokens), input_tokens + output_tokens)
            cost_usd = as_float(rec.get("cost_usd", 0.0), 0.0)

            summary_entries += 1
            summary_input += input_tokens
            summary_output += output_tokens
            summary_total += total_tokens
            summary_cost += cost_usd

        lines.append("Summary:")
        lines.append(f"  Entries  : {fmt_int(summary_entries)}")
        lines.append(f"  Input    : {fmt_int(summary_input)}")
        lines.append(f"  Output   : {fmt_int(summary_output)}")
        lines.append(f"  Total    : {fmt_int(summary_total)}")
        lines.append(f"  Cost USD : {fmt_money(summary_cost)}")
        lines.append("")

        for idx, raw in enumerate(entries, 1):
            parse_error = False
            try:
                rec = json.loads(raw)
            except Exception:
                parse_error = True
                rec = {}

            input_tokens = as_int(rec.get("input_tokens", 0), 0)
            output_tokens = as_int(rec.get("output_tokens", 0), 0)
            total_tokens = as_int(rec.get("total_tokens", input_tokens + output_tokens), input_tokens + output_tokens)
            cost_usd = as_float(rec.get("cost_usd", 0.0), 0.0)
            source = str(rec.get("source", "(missing)"))
            source_name = Path(source).name if source not in ("", "(missing)") else "(missing)"

            lines.append("────────────────────────────────────────────")
            lines.append(f"Entry #{idx}")
            lines.append("────────────────────────────────────────────")
            if parse_error:
                lines.append("⚠ Invalid JSON record (defaults applied)")
                lines.append(f"  Raw: {raw}")
                lines.append("")

            lines.append(f"Date:   {entry_date(rec)}")
            lines.append(f"Model:  {rec.get('model', '(missing)')}")
            lines.append("")
            lines.append("Source:")
            lines.append(f"  Name   : {source_name}")
            lines.append(f"  Path   : {source}")
            lines.append("")
            lines.append("Tokens:")
            lines.append(f"  Input   : {fmt_int(input_tokens)}")
            lines.append(f"  Output  : {fmt_int(output_tokens)}")
            lines.append(f"  Total   : {fmt_int(total_tokens)}")
            lines.append("")
            lines.append("Cost:")
            lines.append(f"  USD     : {fmt_money(cost_usd)}")
            lines.append("")

with OUT.open("w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"Ledger report written to: {OUT}")
