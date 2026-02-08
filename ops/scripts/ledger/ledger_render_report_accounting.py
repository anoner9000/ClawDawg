#!/usr/bin/env python3
"""
ledger_render_report_accounting.py

Higher-standard accounting renderer for OpenClaw heartbeat ledger.

GOAL:
- Make the accounting portion deterministic, auditable, and self-explaining.

INPUTS (read-only):
- Ledger:  ~/.openclaw/runtime/logs/heartbeat/llm_usage.jsonl
- Rates:   Prefer ~/.openclaw/runtime/config.known-good/model_rates.json if present,
           else ~/.openclaw/runtime/config/model_rates.json

OUTPUTS (overwrite):
- Text:    ~/.openclaw/runtime/logs/heartbeat/ledger_report_accounting_latest.txt
- HTML:    ~/.openclaw/runtime/logs/heartbeat/ledger_report_accounting_latest.html

ACCOUNTING POLICY (defaults):
- "Official" headline total = recomputed_total_usd (computed from tokens + pinned rates snapshot)
- Also show recorded_total_usd (sum of cost_usd present in ledger) and reconciliation deltas
"""

from __future__ import annotations

import json
import os
import html
import hashlib
import datetime as dt
from pathlib import Path
from collections import defaultdict, Counter

HOME = Path.home()
RUNTIME_DIR = Path(os.environ.get("OPENCLAW_RUNTIME_DIR", HOME / ".openclaw" / "runtime"))
HB_DIR = RUNTIME_DIR / "logs" / "heartbeat"

LEDGER_PATH = HB_DIR / "llm_usage.jsonl"
RATES_KNOWN_GOOD = RUNTIME_DIR / "config.known-good" / "model_rates.json"
RATES_CURRENT = RUNTIME_DIR / "config" / "model_rates.json"

OUT_TXT = HB_DIR / "ledger_report_accounting_latest.txt"
OUT_HTML = HB_DIR / "ledger_report_accounting_latest.html"

FALLBACK_MODEL = "gpt-5-mini"   # used if model not found in rates
ROUND_DECIMALS = 6              # stable rounding

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
    return f"${x:.{ROUND_DECIMALS}f}"

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def iso_mtime(p: Path) -> str:
    ts = p.stat().st_mtime
    return dt.datetime.fromtimestamp(ts).isoformat(sep=" ", timespec="seconds")

def derive_date(rec: dict) -> str:
    d = rec.get("date")
    if isinstance(d, str) and d.strip():
        return d.strip()
    ts = rec.get("created_at") or rec.get("created")
    tsi = safe_int(ts, 0)
    if tsi > 0:
        try:
            return dt.datetime.fromtimestamp(tsi).date().isoformat()
        except Exception:
            return "(missing)"
    return "(missing)"

def compute_cost_usd(model: str, input_tokens: int, output_tokens: int, rates: dict) -> tuple[float, str]:
    """
    Returns (computed_cost, rate_resolution) where rate_resolution is:
      - "exact" if model in rates
      - "fallback:<FALLBACK_MODEL>" if fallback used
      - "missing" if neither exact nor fallback exists
    """
    if model in rates:
        r = rates.get(model) or {}
        res = "exact"
    elif FALLBACK_MODEL in rates:
        r = rates.get(FALLBACK_MODEL) or {}
        res = f"fallback:{FALLBACK_MODEL}"
    else:
        r = {}
        res = "missing"

    in_per_1m = safe_float(r.get("input_per_1m"), 0.0)
    out_per_1m = safe_float(r.get("output_per_1m"), 0.0)

    cost = (input_tokens / 1_000_000.0) * in_per_1m + (output_tokens / 1_000_000.0) * out_per_1m
    return (round(cost, ROUND_DECIMALS), res)

def esc(s: str) -> str:
    return html.escape(s or "", quote=True)

def main() -> int:
    HB_DIR.mkdir(parents=True, exist_ok=True)

    # Pick rates snapshot (pinned preference)
    rates_path = RATES_KNOWN_GOOD if RATES_KNOWN_GOOD.exists() else RATES_CURRENT
    if not rates_path.exists():
        raise SystemExit(f"Missing rates file: {rates_path}")

    try:
        rates = json.loads(rates_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit(f"Failed to parse rates JSON: {rates_path}: {e}")

    rates_sha = sha256_file(rates_path)
    rates_mtime = iso_mtime(rates_path)

    # Load ledger
    raw_lines = []
    invalid_lines = 0
    if LEDGER_PATH.exists():
        for ln in LEDGER_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
            if not ln.strip():
                continue
            raw_lines.append(ln)
    else:
        raw_lines = []

    records = []
    for ln in raw_lines:
        try:
            records.append(json.loads(ln))
        except Exception:
            invalid_lines += 1

    # Sort stable by created_at if present, else keep input order
    def sort_key(r, i):
        return (safe_int(r.get("created_at") or r.get("created") or 0), i)

    records_sorted = sorted(list(enumerate(records, 1)), key=lambda t: sort_key(t[1], t[0]))

    # Duplicate detection by source
    sources = [str(r.get("source") or "") for _, r in records_sorted]
    source_counts = Counter(sources)
    dup_sources = {s: c for s, c in source_counts.items() if s and c > 1}
    dup_count_entries = sum(c for c in dup_sources.values())

    # Enrich & compute
    enriched = []
    stats = {
        "missing_source": 0,
        "missing_tokens": 0,
        "missing_recorded_cost": 0,
        "fallback_used": 0,
        "rates_missing": 0,
        "invalid_json_lines": invalid_lines,
        "entries": len(records_sorted),
    }

    totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "recorded_total_usd": 0.0,
        "recomputed_total_usd": 0.0,
        "recon_delta_total_usd": 0.0,   # only across entries with recorded_cost present
        "recorded_present": 0,
    }

    dates = []
    by_model = defaultdict(lambda: {"calls": 0, "recomputed_usd": 0.0, "in": 0, "out": 0, "fallback_used": 0, "rates_missing": 0})

    for idx, rec in records_sorted:
        model = str(rec.get("model") or "unknown")
        src = str(rec.get("source") or "")
        created_at = safe_int(rec.get("created_at") or rec.get("created") or 0)
        date_s = derive_date(rec)
        dates.append(date_s)

        inp = safe_int(rec.get("input_tokens"), 0)
        outp = safe_int(rec.get("output_tokens"), 0)
        tot = safe_int(rec.get("total_tokens"), inp + outp)

        if not src:
            stats["missing_source"] += 1
        if inp == 0 and outp == 0 and tot == 0:
            stats["missing_tokens"] += 1

        recomputed, rate_res = compute_cost_usd(model, inp, outp, rates)
        if rate_res.startswith("fallback:"):
            stats["fallback_used"] += 1
            by_model[model]["fallback_used"] += 1
        if rate_res == "missing":
            stats["rates_missing"] += 1
            by_model[model]["rates_missing"] += 1

        recorded_cost = rec.get("cost_usd", None)
        if recorded_cost is None:
            stats["missing_recorded_cost"] += 1
            recorded_cost_f = None
        else:
            recorded_cost_f = safe_float(recorded_cost, 0.0)
            totals["recorded_total_usd"] += recorded_cost_f
            totals["recorded_present"] += 1

        # reconciliation delta only when recorded is present
        delta = None
        reason = []
        if recorded_cost_f is None:
            reason.append("record_missing")
        else:
            delta = round(recomputed - round(recorded_cost_f, ROUND_DECIMALS), ROUND_DECIMALS)
            totals["recon_delta_total_usd"] += delta
            if delta != 0:
                reason.append("rates_or_rounding_differ")

        if rate_res.startswith("fallback:"):
            reason.append("fallback_rate_used")
        elif rate_res == "missing":
            reason.append("rates_missing_for_model")

        if src and src in dup_sources:
            reason.append("duplicate_source_detected")

        totals["input_tokens"] += inp
        totals["output_tokens"] += outp
        totals["total_tokens"] += tot
        totals["recomputed_total_usd"] += recomputed

        by_model[model]["calls"] += 1
        by_model[model]["recomputed_usd"] += recomputed
        by_model[model]["in"] += inp
        by_model[model]["out"] += outp

        enriched.append({
            "i": idx,
            "date": date_s,
            "created_at": created_at,
            "model": model,
            "source": src,
            "input_tokens": inp,
            "output_tokens": outp,
            "total_tokens": tot,
            "recorded_cost_usd": None if recorded_cost_f is None else round(recorded_cost_f, ROUND_DECIMALS),
            "recomputed_cost_usd": recomputed,
            "delta_usd": delta,
            "rate_resolution": rate_res,
            "reason": ",".join(reason) if reason else "ok",
            "pk": f"{src}|{created_at}|{model}" if src else f"(missing_source)|{created_at}|{model}",
        })

    # Compute date span
    span_days = 1
    try:
        real_dates = [d for d in dates if d and d != "(missing)"]
        if real_dates:
            dmin = dt.date.fromisoformat(min(real_dates))
            dmax = dt.date.fromisoformat(max(real_dates))
            span_days = (dmax - dmin).days + 1
    except Exception:
        span_days = 1

    totals["recomputed_total_usd"] = round(totals["recomputed_total_usd"], ROUND_DECIMALS)
    totals["recorded_total_usd"] = round(totals["recorded_total_usd"], ROUND_DECIMALS)
    totals["recon_delta_total_usd"] = round(totals["recon_delta_total_usd"], ROUND_DECIMALS)

    # ------------------------------
    # TEXT REPORT
    # ------------------------------
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def tline(ch="─", n=78):
        return ch * n

    official_total = totals["recomputed_total_usd"]
    official_per_day = round(official_total / max(span_days, 1), ROUND_DECIMALS)

    txt = []
    txt.append(tline("═"))
    txt.append("OPENCLAW HEARTBEAT LEDGER — ACCOUNTING REPORT (AUDIT GRADE)")
    txt.append(tline("═"))
    txt.append(f"Generated: {now}")
    txt.append(f"Ledger:    {LEDGER_PATH}")
    txt.append(f"Rates:     {rates_path}")
    txt.append(f"Rates SHA: {rates_sha}")
    txt.append(f"Rates mtime: {rates_mtime}")
    txt.append(f"Policy: OFFICIAL TOTAL = recomputed_total_usd (tokens × pinned rates snapshot)")
    txt.append("")
    txt.append(tline())
    txt.append("HEADLINE FIGURES")
    txt.append(tline())
    txt.append(f"Entries (valid):        {stats['entries']}")
    txt.append(f"Invalid JSON lines:     {stats['invalid_json_lines']}")
    txt.append(f"Recorded span (days):   {span_days}")
    txt.append("")
    txt.append(f"Tokens — input:         {totals['input_tokens']:,}")
    txt.append(f"Tokens — output:        {totals['output_tokens']:,}")
    txt.append(f"Tokens — total:         {totals['total_tokens']:,}")
    txt.append("")
    txt.append(f"OFFICIAL recomputed USD: {money(official_total)}")
    txt.append(f"OFFICIAL USD per day:    {money(official_per_day)}")
    txt.append("")
    txt.append(f"Recorded USD (sum of cost_usd present): {money(totals['recorded_total_usd'])}   (present in {totals['recorded_present']} entries)")
    txt.append(f"Reconciliation delta (recomputed - recorded across recorded entries): {money(totals['recon_delta_total_usd'])}")
    txt.append("")
    txt.append(tline())
    txt.append("DATA QUALITY / WARNINGS")
    txt.append(tline())
    txt.append(f"Missing source:         {stats['missing_source']}")
    txt.append(f"Missing tokens:         {stats['missing_tokens']}")
    txt.append(f"Missing recorded cost:  {stats['missing_recorded_cost']}")
    txt.append(f"Fallback rate used:     {stats['fallback_used']}")
    txt.append(f"Rates missing for model:{stats['rates_missing']}")
    txt.append(f"Duplicate sources:      {len(dup_sources)}  (entries involved: {dup_count_entries})")
    txt.append("")
    if dup_sources:
        txt.append("Duplicate source list (source -> count):")
        for s, c in sorted(dup_sources.items(), key=lambda kv: (-kv[1], kv[0]))[:20]:
            txt.append(f"  {c}  {s}")
        txt.append("")

    txt.append(tline())
    txt.append("BY MODEL (recomputed totals, pinned rates)")
    txt.append(tline())
    txt.append(f"{'MODEL':38} {'CALLS':>6} {'IN':>10} {'OUT':>10} {'RECOMP USD':>12} {'RATE':>10}")
    for model, m in sorted(by_model.items(), key=lambda kv: kv[1]["recomputed_usd"], reverse=True):
        rate_flag = "exact"
        if m["rates_missing"] > 0:
            rate_flag = "missing"
        elif m["fallback_used"] > 0:
            rate_flag = "fallback"
        txt.append(
            f"{model[:38]:38} {m['calls']:>6} {m['in']:>10,} {m['out']:>10,} {money(round(m['recomputed_usd'], ROUND_DECIMALS)):>12} {rate_flag:>10}"
        )
    txt.append("")

    txt.append(tline())
    txt.append("ENTRIES (audit fields)")
    txt.append(tline())
    txt.append("Columns:")
    txt.append("  # | date | model | in | out | total | recorded_usd | recomputed_usd | delta | rate_res | reason")
    txt.append("")
    for e in enriched:
        rec_s = "(missing)" if e["recorded_cost_usd"] is None else money(e["recorded_cost_usd"])
        del_s = "(n/a)" if e["delta_usd"] is None else money(e["delta_usd"])
        txt.append(
            f"{e['i']:>3} | {e['date']:<10} | {e['model']:<22} | "
            f"{e['input_tokens']:>6,} | {e['output_tokens']:>6,} | {e['total_tokens']:>6,} | "
            f"{rec_s:>12} | {money(e['recomputed_cost_usd']):>12} | {del_s:>10} | "
            f"{e['rate_resolution']:<14} | {e['reason']}"
        )
    txt.append("")
    txt.append(tline("═"))
    txt.append("END OF REPORT")
    txt.append(tline("═"))
    OUT_TXT.write_text("\n".join(txt) + "\n", encoding="utf-8")

    # ------------------------------
    # HTML REPORT (same accounting, nicer reading)
    # ------------------------------
    css = """
    :root{
      --bg:#0b0b10; --panel:#11111a; --ink:#f2efe6; --muted:#c8c1af; --gold:#d6b25e; --line:rgba(214,178,94,.25);
    }
    *{box-sizing:border-box}
    body{margin:0;background:linear-gradient(180deg,#07070b,var(--bg));color:var(--ink);font-family:ui-serif,Georgia,"Times New Roman",serif}
    .wrap{max-width:1200px;margin:28px auto 64px;padding:0 16px}
    .mast{border:1px solid var(--line);background:rgba(17,17,26,.86);padding:18px 18px 14px}
    .title{margin:0;font-variant:small-caps;letter-spacing:.10em;font-size:24px}
    .sub{margin-top:6px;color:var(--muted);letter-spacing:.14em;font-size:12px;text-transform:uppercase}
    .meta{margin-top:10px;display:flex;flex-wrap:wrap;gap:10px;color:var(--muted);font-size:12px}
    .chip{border:1px solid var(--line);padding:6px 10px;background:rgba(0,0,0,.15)}
    .grid{margin-top:14px;display:grid;grid-template-columns:1fr 1fr;gap:14px}
    @media (max-width: 900px){.grid{grid-template-columns:1fr}}
    .card{border:1px solid var(--line);background:rgba(17,17,26,.86);padding:14px}
    h2{margin:0 0 10px;font-variant:small-caps;letter-spacing:.08em;font-size:15px;color:var(--gold)}
    .kpi{display:grid;grid-template-columns:1fr 1fr;gap:10px}
    .k{border:1px solid rgba(214,178,94,.18);padding:10px;background:rgba(0,0,0,.12)}
    .lab{color:var(--muted);font-size:11px;letter-spacing:.10em;text-transform:uppercase}
    .val{margin-top:6px;font-size:18px}
    table{width:100%;border-collapse:collapse;font-size:13px}
    th,td{padding:10px 8px;border-bottom:1px solid rgba(214,178,94,.16);vertical-align:top}
    th{color:var(--muted);letter-spacing:.10em;text-transform:uppercase;font-size:11px}
    .mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace;font-size:12px;color:var(--muted);word-break:break-all}
    .cost{color:var(--gold);font-variant-numeric:tabular-nums}
    .warn{color:#f0d39a}
    """

    def chip(label, value, mono=False):
        if mono:
            return f"<span class='chip'>{esc(label)}: <span class='mono'>{esc(value)}</span></span>"
        return f"<span class='chip'>{esc(label)}: {esc(value)}</span>"

    # model table rows
    model_rows = []
    for model, m in sorted(by_model.items(), key=lambda kv: kv[1]["recomputed_usd"], reverse=True):
        rate_flag = "exact"
        if m["rates_missing"] > 0:
            rate_flag = "missing"
        elif m["fallback_used"] > 0:
            rate_flag = "fallback"
        model_rows.append(
            "<tr>"
            f"<td>{esc(model)}</td>"
            f"<td style='text-align:right'>{m['calls']}</td>"
            f"<td style='text-align:right'>{m['in']:,}</td>"
            f"<td style='text-align:right'>{m['out']:,}</td>"
            f"<td style='text-align:right' class='cost'>{money(round(m['recomputed_usd'], ROUND_DECIMALS))}</td>"
            f"<td style='text-align:right' class='mono'>{esc(rate_flag)}</td>"
            "</tr>"
        )

    # entries rows
    entry_rows = []
    for e in enriched:
        rec_s = "" if e["recorded_cost_usd"] is None else money(e["recorded_cost_usd"])
        del_s = "" if e["delta_usd"] is None else money(e["delta_usd"])
        reason_cls = "warn" if e["reason"] != "ok" else ""
        entry_rows.append(
            "<tr>"
            f"<td style='white-space:nowrap'>{e['i']}</td>"
            f"<td style='white-space:nowrap'>{esc(e['date'])}</td>"
            f"<td>{esc(e['model'])}</td>"
            f"<td style='text-align:right'>{e['input_tokens']:,}</td>"
            f"<td style='text-align:right'>{e['output_tokens']:,}</td>"
            f"<td style='text-align:right'>{e['total_tokens']:,}</td>"
            f"<td style='text-align:right' class='mono'>{esc(rec_s)}</td>"
            f"<td style='text-align:right' class='cost'>{money(e['recomputed_cost_usd'])}</td>"
            f"<td style='text-align:right' class='mono'>{esc(del_s)}</td>"
            f"<td class='mono'>{esc(e['rate_resolution'])}</td>"
            f"<td class='{reason_cls}'>{esc(e['reason'])}</td>"
            f"<td class='mono'>{esc(e['source'])}</td>"
            "</tr>"
        )

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>OpenClaw Ledger — Accounting Report</title>
<style>{css}</style>
</head>
<body>
<div class="wrap">
  <div class="mast">
    <h1 class="title">OpenClaw Heartbeat Ledger — Accounting Report</h1>
    <div class="sub">Deterministic totals • Rates provenance • Reconciliation</div>
    <div class="meta">
      {chip("Generated", now)}
      {chip("Ledger", str(LEDGER_PATH), mono=True)}
      {chip("Rates", str(rates_path), mono=True)}
      {chip("Rates SHA256", rates_sha[:16] + "…", mono=True)}
      {chip("Rates mtime", rates_mtime)}
      {chip("Policy", "OFFICIAL = recomputed_total_usd")}
    </div>
  </div>

  <div class="grid">
    <div class="card">
      <h2>Headline Figures</h2>
      <div class="kpi">
        <div class="k"><div class="lab">Entries (valid)</div><div class="val">{stats['entries']:,}</div></div>
        <div class="k"><div class="lab">Invalid JSON lines</div><div class="val">{stats['invalid_json_lines']:,}</div></div>
        <div class="k"><div class="lab">Recorded span (days)</div><div class="val">{span_days:,}</div></div>
        <div class="k"><div class="lab">Fallback model</div><div class="val">{esc(FALLBACK_MODEL)}</div></div>

        <div class="k"><div class="lab">Input tokens</div><div class="val">{totals['input_tokens']:,}</div></div>
        <div class="k"><div class="lab">Output tokens</div><div class="val">{totals['output_tokens']:,}</div></div>
        <div class="k"><div class="lab">Total tokens</div><div class="val">{totals['total_tokens']:,}</div></div>
        <div class="k"><div class="lab">Duplicate sources</div><div class="val">{len(dup_sources):,}</div></div>

        <div class="k"><div class="lab">OFFICIAL recomputed USD</div><div class="val cost">{money(official_total)}</div></div>
        <div class="k"><div class="lab">OFFICIAL USD per day</div><div class="val cost">{money(official_per_day)}</div></div>
        <div class="k"><div class="lab">Recorded USD (sum)</div><div class="val">{money(totals['recorded_total_usd'])}</div></div>
        <div class="k"><div class="lab">Recon delta (sum)</div><div class="val">{money(totals['recon_delta_total_usd'])}</div></div>
      </div>
    </div>

    <div class="card">
      <h2>Data Quality</h2>
      <table>
        <tbody>
          <tr><td>Missing source</td><td style="text-align:right">{stats['missing_source']:,}</td></tr>
          <tr><td>Missing tokens</td><td style="text-align:right">{stats['missing_tokens']:,}</td></tr>
          <tr><td>Missing recorded cost</td><td style="text-align:right">{stats['missing_recorded_cost']:,}</td></tr>
          <tr><td>Fallback rate used</td><td style="text-align:right">{stats['fallback_used']:,}</td></tr>
          <tr><td>Rates missing for model</td><td style="text-align:right">{stats['rates_missing']:,}</td></tr>
          <tr><td>Duplicate-source entries involved</td><td style="text-align:right">{dup_count_entries:,}</td></tr>
        </tbody>
      </table>
      <div style="margin-top:10px;color:var(--muted);font-size:12px;line-height:1.5">
        This report renders the ledger as-is. Recomputed USD is derived from tokens using the pinned rates snapshot above.
        Recorded USD is the sum of <span class="mono">cost_usd</span> fields present in the ledger. Differences are explained per-entry.
      </div>
    </div>
  </div>

  <div class="card" style="margin-top:14px">
    <h2>By Model (recomputed totals)</h2>
    <table>
      <thead>
        <tr>
          <th>Model</th><th style="text-align:right">Calls</th><th style="text-align:right">Input</th>
          <th style="text-align:right">Output</th><th style="text-align:right">Recomputed USD</th><th style="text-align:right">Rate</th>
        </tr>
      </thead>
      <tbody>
        {''.join(model_rows) if model_rows else '<tr><td colspan="6">(no data)</td></tr>'}
      </tbody>
    </table>
  </div>

  <div class="card" style="margin-top:14px">
    <h2>Entries (audit fields)</h2>
    <table>
      <thead>
        <tr>
          <th>#</th><th>Date</th><th>Model</th>
          <th style="text-align:right">In</th><th style="text-align:right">Out</th><th style="text-align:right">Total</th>
          <th style="text-align:right">Recorded USD</th><th style="text-align:right">Recomputed USD</th><th style="text-align:right">Delta</th>
          <th>Rate resolution</th><th>Reason</th><th>Source</th>
        </tr>
      </thead>
      <tbody>
        {''.join(entry_rows) if entry_rows else '<tr><td colspan="12">(no entries)</td></tr>'}
      </tbody>
    </table>
  </div>
</div>
</body>
</html>
"""
    OUT_HTML.write_text(html_doc, encoding="utf-8")

    print(f"Text report written to: {OUT_TXT}")
    print(f"HTML report written to: {OUT_HTML}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
