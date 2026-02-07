#!/usr/bin/env python3
"""
ledger_render_report.py
Art Deco styled, read-only ledger report renderer.

Reads:
  ~/.openclaw/runtime/logs/heartbeat/llm_usage.jsonl

Writes (overwrites):
  ~/.openclaw/runtime/logs/heartbeat/ledger_report_latest.txt

This script NEVER modifies the ledger.
"""

import json
import os
import datetime as dt
from pathlib import Path
from collections import defaultdict

HOME = Path.home()
RUNTIME_DIR = Path(os.environ.get("OPENCLAW_RUNTIME_DIR", HOME / ".openclaw" / "runtime"))
LEDGER = RUNTIME_DIR / "logs" / "heartbeat" / "llm_usage.jsonl"
OUT = RUNTIME_DIR / "logs" / "heartbeat" / "ledger_report_latest.txt"

WIDTH = 74

# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def line(ch: str, width: int = WIDTH) -> str:
    return ch * width

def center(text: str, width: int = WIDTH) -> str:
    s = (text or "").strip()
    if len(s) >= width:
        return s[:width]
    pad = (width - len(s)) // 2
    return (" " * pad) + s + (" " * (width - len(s) - pad))

def safe_int(x, default=0) -> int:
    try:
        return int(x)
    except Exception:
        return default

def safe_float(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default

def fmt_int(n) -> str:
    return f"{safe_int(n, 0):,}"

def fmt_money(x) -> str:
    return f"${safe_float(x, 0.0):,.6f}"

def derive_date(rec: dict) -> str:
    d = rec.get("date")
    if isinstance(d, str) and d.strip():
        return d.strip()
    ts = rec.get("created_at") or rec.get("created")
    ts_i = safe_int(ts, 0)
    if ts_i > 0:
        try:
            return dt.datetime.fromtimestamp(ts_i).date().isoformat()
        except Exception:
            pass
    return "(missing)"

def shorten_path(p: str):
    try:
        pp = Path(p)
        return (pp.name or "?", str(pp))
    except Exception:
        return ("?", str(p))

def art_header(title: str):
    return [
        "╔" + ("═" * (WIDTH - 2)) + "╗",
        "║" + center(title, WIDTH - 2) + "║",
        "╚" + ("═" * (WIDTH - 2)) + "╝",
    ]

def art_divider(label: str = "") -> str:
    inner = WIDTH - 2
    if not label:
        return "╟" + ("─" * inner) + "╢"
    lab = f" {label.strip()} "
    left = (inner - len(lab)) // 2
    right = inner - len(lab) - left
    return "╟" + ("─" * left) + lab + ("─" * right) + "╢"

def art_box(lines):
    out = []
    out.append("╔" + ("═" * (WIDTH - 2)) + "╗")
    for ln in lines:
        s = (ln or "").rstrip()
        if len(s) > WIDTH - 2:
            s = s[:WIDTH - 5] + "..."
        out.append("║" + s.ljust(WIDTH - 2) + "║")
    out.append("╚" + ("═" * (WIDTH - 2)) + "╝")
    return out

def flapper_speech(total_cost, span_days):
    cents = total_cost * 100.0
    return [
        "A WORD FROM THE LEDGER",
        "",
        "Ladies and gentlemen of the machine age:",
        "The books are balanced, the lamps are lit,",
        "and the figures stand ready for inspection.",
        "",
        f"The total account amounts to {fmt_money(total_cost)} ({cents:.2f} cents).",
        f"Average per day across the recorded span: {fmt_money(total_cost / max(span_days,1))}.",
        "",
        "Spend with intention, keep your ledgers honest,",
        "and prosperity will always know your name.",
    ]

# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

def main():
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    records = []
    invalid = 0

    if LEDGER.exists():
        for ln in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
            if not ln.strip():
                continue
            try:
                records.append(json.loads(ln))
            except Exception:
                invalid += 1

    total_in = total_out = total_tok = 0
    total_cost = 0.0
    dates = []

    by_model_calls = defaultdict(int)
    by_model_cost = defaultdict(float)

    for r in records:
        inp = safe_int(r.get("input_tokens"))
        outp = safe_int(r.get("output_tokens"))
        tot = safe_int(r.get("total_tokens"), inp + outp)
        cost = safe_float(r.get("cost_usd"))

        total_in += inp
        total_out += outp
        total_tok += tot
        total_cost += cost

        d = derive_date(r)
        if d != "(missing)":
            dates.append(d)

        model = r.get("model") or "unknown"
        by_model_calls[model] += 1
        by_model_cost[model] += cost

    if dates:
        dmin = dt.date.fromisoformat(min(dates))
        dmax = dt.date.fromisoformat(max(dates))
        span_days = (dmax - dmin).days + 1
    else:
        span_days = 1

    out = []
    out.extend(art_header("OPENCLAW HEARTBEAT LEDGER"))
    out.append(center("PROVENANCE • APPEND-ONLY • MACHINE ACCOUNTING", WIDTH))
    out.append(center(f"GENERATED: {now}", WIDTH))
    out.append("")

    out.extend(art_box(flapper_speech(total_cost, span_days)))
    out.append("")

    out.extend(art_box([
        "SUMMARY",
        "",
        f"Entries            : {fmt_int(len(records))}",
        f"Invalid lines      : {fmt_int(invalid)}",
        f"Recorded span      : {fmt_int(span_days)} day(s)",
        "",
        f"Input tokens       : {fmt_int(total_in)}",
        f"Output tokens      : {fmt_int(total_out)}",
        f"Total tokens       : {fmt_int(total_tok)}",
        "",
        f"Total cost (USD)   : {fmt_money(total_cost)}",
        f"Cost per day       : {fmt_money(total_cost / max(span_days,1))}",
    ]))
    out.append("")

    if by_model_calls:
        out.append(art_divider("BY MODEL"))
        rows = [
            "MODEL".ljust(40) + "CALLS".rjust(8) + "   COST",
            "-" * 40 + "-" * 8 + "   " + "-" * 10,
        ]
        for m in sorted(by_model_calls, key=lambda k: by_model_cost[k], reverse=True):
            rows.append(
                m[:40].ljust(40) +
                fmt_int(by_model_calls[m]).rjust(8) +
                "   " +
                fmt_money(by_model_cost[m])
            )
        out.extend(art_box(rows))
        out.append("")

    out.append(art_divider("ENTRIES"))
    for i, r in enumerate(records, 1):
        base, full = shorten_path(r.get("source", "?"))
        out.extend(art_box([
            f"ENTRY #{i}  •  {derive_date(r)}  •  {r.get('model','unknown')}",
            "",
            "SOURCE:",
            f"  {base}",
            f"  {full}",
            "",
            f"Input tokens  : {fmt_int(r.get('input_tokens'))}",
            f"Output tokens : {fmt_int(r.get('output_tokens'))}",
            f"Total tokens  : {fmt_int(r.get('total_tokens'))}",
            "",
            f"Cost (USD)    : {fmt_money(r.get('cost_usd'))}",
        ]))
        out.append("")

    out.append(line("═"))
    out.append(center("END OF ACCOUNT", WIDTH))
    out.append(line("═"))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(out), encoding="utf-8")

    print(f"Ledger report written to: {OUT}")

if __name__ == "__main__":
    main()
