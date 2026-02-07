#!/usr/bin/env python3
"""
ledger_render_report_html.py

Generates an Art Deco HTML report from the append-only ledger:
  ~/.openclaw/runtime/logs/heartbeat/llm_usage.jsonl

Deterministic cost:
- Computes cost from tokens + model_rates.json every run
- Also displays recorded cost_usd (if present) for audit comparison

Writes:
  ~/.openclaw/runtime/logs/heartbeat/ledger_report_latest.html
  ~/.openclaw/runtime/logs/heartbeat/ledger_report_latest.txt  (small receipt)

Never modifies the ledger.
"""

import json
import os
import html
import datetime as dt
from pathlib import Path
from collections import defaultdict

HOME = Path.home()
RUNTIME_DIR = Path(os.environ.get("OPENCLAW_RUNTIME_DIR", HOME / ".openclaw" / "runtime"))
HB_DIR = RUNTIME_DIR / "logs" / "heartbeat"
LEDGER = HB_DIR / "llm_usage.jsonl"
RATES = RUNTIME_DIR / "config" / "model_rates.json"

OUT_HTML = HB_DIR / "ledger_report_latest.html"
OUT_TXT  = HB_DIR / "ledger_report_latest.txt"

FALLBACK_MODEL = "gpt-5-mini"  # used if exact model not found in rates
DECIMALS = 6  # stable rounding

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

def money(x: float) -> str:
    return f"${x:.{DECIMALS}f}"

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

def compute_cost_usd(model: str, input_tokens: int, output_tokens: int, rates: dict) -> float:
    rate = rates.get(model) or rates.get(FALLBACK_MODEL) or {}
    in_per_1m = safe_float(rate.get("input_per_1m"), 0.0)
    out_per_1m = safe_float(rate.get("output_per_1m"), 0.0)
    return (input_tokens / 1_000_000.0) * in_per_1m + (output_tokens / 1_000_000.0) * out_per_1m

def esc(s: str) -> str:
    return html.escape(s or "", quote=True)

def main() -> int:
    HB_DIR.mkdir(parents=True, exist_ok=True)

    # Load rates
    if not RATES.exists():
        raise SystemExit(f"Missing rates file: {RATES}")
    try:
        rates = json.loads(RATES.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit(f"Failed to parse rates JSON: {RATES}: {e}")

    # Load ledger records
    records = []
    invalid_lines = 0
    if LEDGER.exists():
        for ln in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
            if not ln.strip():
                continue
            try:
                records.append(json.loads(ln))
            except Exception:
                invalid_lines += 1
    else:
        records = []

    # Sort by created_at if present, otherwise stable input order
    def sort_key(r):
        return safe_int(r.get("created_at") or r.get("created") or 0)
    records_sorted = sorted(records, key=sort_key)

    # Totals
    total_in = total_out = 0
    total_cost_computed = 0.0
    total_cost_recorded = 0.0
    recorded_present = 0

    by_model = defaultdict(lambda: {"calls": 0, "cost": 0.0, "in": 0, "out": 0})
    dates = []

    enriched = []
    for r in records_sorted:
        model = r.get("model") or "unknown"
        inp = safe_int(r.get("input_tokens"), 0)
        outp = safe_int(r.get("output_tokens"), 0)
        created_at = safe_int(r.get("created_at") or r.get("created") or 0, 0)
        date_s = derive_date(r)
        dates.append(date_s)

        computed = compute_cost_usd(model, inp, outp, rates)
        computed = round(computed, DECIMALS)

        rec_cost = r.get("cost_usd")
        rec_cost_f = safe_float(rec_cost, 0.0) if rec_cost is not None else None
        if rec_cost_f is not None:
            total_cost_recorded += rec_cost_f
            recorded_present += 1

        total_in += inp
        total_out += outp
        total_cost_computed += computed

        by_model[model]["calls"] += 1
        by_model[model]["cost"] += computed
        by_model[model]["in"] += inp
        by_model[model]["out"] += outp

        src = str(r.get("source") or "")
        enriched.append({
            "date": date_s,
            "created_at": created_at,
            "model": model,
            "input_tokens": inp,
            "output_tokens": outp,
            "total_tokens": safe_int(r.get("total_tokens"), inp + outp),
            "source": src,
            "computed_cost": computed,
            "recorded_cost": rec_cost_f,
        })

    # Date span
    span_days = 1
    try:
        real_dates = [d for d in dates if d and d != "(missing)"]
        if real_dates:
            dmin = dt.date.fromisoformat(min(real_dates))
            dmax = dt.date.fromisoformat(max(real_dates))
            span_days = (dmax - dmin).days + 1
    except Exception:
        span_days = 1

    per_day = round(total_cost_computed / max(span_days, 1), DECIMALS)

    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Art Deco HTML (no external deps)
    css = f"""
    :root {{
      --bg: #0b0b0f;
      --panel: #11111a;
      --ink: #f3efe3;
      --muted: #c9c2b0;
      --gold: #d6b25e;
      --gold2: #b8913f;
      --line: rgba(214,178,94,0.35);
      --shadow: rgba(0,0,0,0.55);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: radial-gradient(1100px 600px at 50% -10%, rgba(214,178,94,0.10), transparent 70%),
                  linear-gradient(180deg, #07070b, var(--bg));
      color: var(--ink);
      font-family: ui-serif, Georgia, "Times New Roman", serif;
    }}
    .wrap {{
      max-width: 1100px;
      margin: 36px auto 64px;
      padding: 0 18px;
    }}
    .mast {{
      border: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(214,178,94,0.06), rgba(17,17,26,0.0));
      box-shadow: 0 18px 60px var(--shadow);
      padding: 22px 22px 16px;
      position: relative;
      overflow: hidden;
    }}
    .mast:before {{
      content: "";
      position: absolute;
      inset: -2px;
      background:
        linear-gradient(90deg, transparent 0%, rgba(214,178,94,0.22) 50%, transparent 100%);
      opacity: 0.20;
      transform: rotate(-2deg);
      pointer-events: none;
    }}
    .title {{
      margin: 0;
      font-variant: small-caps;
      letter-spacing: 0.10em;
      font-size: 28px;
    }}
    .subtitle {{
      margin-top: 6px;
      color: var(--muted);
      letter-spacing: 0.14em;
      font-size: 12px;
      text-transform: uppercase;
    }}
    .meta {{
      margin-top: 14px;
      display: flex;
      gap: 14px;
      flex-wrap: wrap;
      color: var(--muted);
      font-size: 12px;
    }}
    .chip {{
      border: 1px solid var(--line);
      padding: 6px 10px;
      background: rgba(17,17,26,0.70);
    }}
    .grid {{
      margin-top: 18px;
      display: grid;
      grid-template-columns: 1.15fr 0.85fr;
      gap: 16px;
    }}
    @media (max-width: 900px) {{
      .grid {{ grid-template-columns: 1fr; }}
    }}
    .card {{
      border: 1px solid var(--line);
      background: rgba(17,17,26,0.86);
      box-shadow: 0 18px 60px var(--shadow);
      padding: 16px 16px 14px;
      position: relative;
      overflow: hidden;
    }}
    .card h2 {{
      margin: 0 0 10px;
      font-variant: small-caps;
      letter-spacing: 0.08em;
      font-size: 16px;
      color: var(--gold);
    }}
    .speech {{
      color: var(--ink);
      line-height: 1.55;
      font-size: 14px;
      margin: 0;
    }}
    .kpi {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }}
    .k {{
      border: 1px solid rgba(214,178,94,0.25);
      background: rgba(0,0,0,0.15);
      padding: 10px 10px 8px;
    }}
    .k .lab {{
      color: var(--muted);
      font-size: 11px;
      letter-spacing: 0.10em;
      text-transform: uppercase;
    }}
    .k .val {{
      margin-top: 6px;
      font-size: 18px;
      letter-spacing: 0.02em;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th, td {{
      padding: 10px 8px;
      border-bottom: 1px solid rgba(214,178,94,0.18);
      vertical-align: top;
    }}
    th {{
      color: var(--muted);
      letter-spacing: 0.10em;
      text-transform: uppercase;
      font-size: 11px;
      font-weight: 600;
    }}
    .mono {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
      font-size: 12px;
      color: var(--muted);
      word-break: break-all;
    }}
    .cost {{
      color: var(--gold);
      font-variant-numeric: tabular-nums;
    }}
    .note {{
      margin-top: 12px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.5;
    }}
    .warn {{
      color: #f0d39a;
    }}
    """

    speech = f"""
    <p class="speech">
      Ladies and gentlemen of the machine age: the books are balanced, the lamps are lit, and the figures stand ready for inspection.
      <br><br>
      The automaton’s running tab stands at <span class="cost">{money(total_cost_computed)}</span> ({total_cost_computed*100:.2f} cents),
      with an average of <span class="cost">{money(per_day)}</span> per day across the recorded span.
      <br><br>
      Spend with intention, keep your ledgers honest, and prosperity will always know your name.
    </p>
    """

    # By-model rows
    model_rows = []
    for model, m in sorted(by_model.items(), key=lambda kv: kv[1]["cost"], reverse=True):
        model_rows.append(
            f"<tr>"
            f"<td>{esc(model)}</td>"
            f"<td style='text-align:right'>{m['calls']}</td>"
            f"<td style='text-align:right'>{m['in']:,}</td>"
            f"<td style='text-align:right'>{m['out']:,}</td>"
            f"<td style='text-align:right' class='cost'>{money(round(m['cost'], DECIMALS))}</td>"
            f"</tr>"
        )

    # Entry rows
    entry_rows = []
    for i, e in enumerate(enriched, 1):
        rec_cost = "" if e["recorded_cost"] is None else money(round(e["recorded_cost"], DECIMALS))
        entry_rows.append(
            "<tr>"
            f"<td style='white-space:nowrap'>{i}</td>"
            f"<td style='white-space:nowrap'>{esc(e['date'])}</td>"
            f"<td>{esc(e['model'])}</td>"
            f"<td style='text-align:right'>{e['input_tokens']:,}</td>"
            f"<td style='text-align:right'>{e['output_tokens']:,}</td>"
            f"<td style='text-align:right'>{e['total_tokens']:,}</td>"
            f"<td style='text-align:right' class='cost'>{money(e['computed_cost'])}</td>"
            f"<td style='text-align:right' class='mono'>{esc(rec_cost)}</td>"
            f"<td class='mono'>{esc(e['source'])}</td>"
            "</tr>"
        )

    recorded_note = ""
    if recorded_present:
        recorded_note = (
            f"<span class='chip'>Recorded cost (ledger sum): {money(round(total_cost_recorded, DECIMALS))}</span>"
        )
    else:
        recorded_note = "<span class='chip'>Recorded cost: (none present in ledger)</span>"

    invalid_note = ""
    if invalid_lines:
        invalid_note = f"<span class='chip warn'>Invalid ledger lines skipped: {invalid_lines}</span>"

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OpenClaw Heartbeat Ledger Report</title>
  <style>{css}</style>
</head>
<body>
  <div class="wrap">
    <div class="mast">
      <h1 class="title">OpenClaw Heartbeat Ledger</h1>
      <div class="subtitle">Provenance First • Append-Only Truth • Decorative Rendering</div>
      <div class="meta">
        <span class="chip">Generated: {esc(now)}</span>
        <span class="chip">Ledger: <span class="mono">{esc(str(LEDGER))}</span></span>
        <span class="chip">Rates: <span class="mono">{esc(str(RATES))}</span></span>
        {recorded_note}
        {invalid_note}
      </div>
    </div>

    <div class="grid">
      <div class="card">
        <h2>Address</h2>
        {speech}
        <div class="note">
          This report computes cost deterministically from tokens and model_rates.json each run.
          Recorded ledger cost is shown only for comparison.
        </div>
      </div>

      <div class="card">
        <h2>Figures</h2>
        <div class="kpi">
          <div class="k"><div class="lab">Entries</div><div class="val">{len(enriched):,}</div></div>
          <div class="k"><div class="lab">Recorded Span (days)</div><div class="val">{span_days:,}</div></div>
          <div class="k"><div class="lab">Input Tokens</div><div class="val">{total_in:,}</div></div>
          <div class="k"><div class="lab">Output Tokens</div><div class="val">{total_out:,}</div></div>
          <div class="k"><div class="lab">Total Tokens</div><div class="val">{(total_in+total_out):,}</div></div>
          <div class="k"><div class="lab">Total Cost (computed)</div><div class="val cost">{money(round(total_cost_computed, DECIMALS))}</div></div>
          <div class="k"><div class="lab">Cost Per Day (computed)</div><div class="val cost">{money(per_day)}</div></div>
          <div class="k"><div class="lab">Fallback Model</div><div class="val">{esc(FALLBACK_MODEL)}</div></div>
        </div>
      </div>
    </div>

    <div class="card" style="margin-top:16px">
      <h2>By Model</h2>
      <table>
        <thead>
          <tr>
            <th>Model</th>
            <th style="text-align:right">Calls</th>
            <th style="text-align:right">Input</th>
            <th style="text-align:right">Output</th>
            <th style="text-align:right">Cost (computed)</th>
          </tr>
        </thead>
        <tbody>
          {''.join(model_rows) if model_rows else '<tr><td colspan="5">(no data)</td></tr>'}
        </tbody>
      </table>
    </div>

    <div class="card" style="margin-top:16px">
      <h2>Entries</h2>
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Date</th>
            <th>Model</th>
            <th style="text-align:right">Input</th>
            <th style="text-align:right">Output</th>
            <th style="text-align:right">Total</th>
            <th style="text-align:right">Cost (computed)</th>
            <th style="text-align:right">Cost (recorded)</th>
            <th>Source</th>
          </tr>
        </thead>
        <tbody>
          {''.join(entry_rows) if entry_rows else '<tr><td colspan="9">(no entries)</td></tr>'}
        </tbody>
      </table>

      <div class="note">
        If “Cost (recorded)” differs from “Cost (computed)”, it means ledger lines were recorded under different rates or rounding at the time.
        Computed cost is the authoritative display.
      </div>
    </div>

  </div>
</body>
</html>
"""

    OUT_HTML.write_text(html_doc, encoding="utf-8")

    # Small receipt TXT for quick tail/ssh checks
    receipt = [
        "OPENCLAW HEARTBEAT LEDGER (RECEIPT)",
        f"Generated: {now}",
        f"Ledger: {LEDGER}",
        f"Rates: {RATES}",
        "",
        f"Entries: {len(enriched)}",
        f"Span days: {span_days}",
        f"Tokens: in={total_in:,} out={total_out:,} total={(total_in+total_out):,}",
        f"Cost (computed): {money(round(total_cost_computed, DECIMALS))}",
        f"Cost/day (computed): {money(per_day)}",
    ]
    OUT_TXT.write_text("\n".join(receipt) + "\n", encoding="utf-8")

    print(f"HTML report written to: {OUT_HTML}")
    print(f"Receipt written to: {OUT_TXT}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
