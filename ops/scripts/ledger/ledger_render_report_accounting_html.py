#!/usr/bin/env python3
"""
ledger_render_report_accounting_html.py

Audit-grade accounting renderer (HTML, Art Deco presentation) for the OpenClaw heartbeat ledger.

Reads:
  - ~/.openclaw/runtime/logs/heartbeat/llm_usage.jsonl
  - ~/.openclaw/runtime/config/model_rates.json

Writes (NEW file; does not overwrite your existing accounting outputs):
  - ~/.openclaw/runtime/logs/heartbeat/ledger_report_accounting_deco_latest.html

Policy:
  OFFICIAL TOTAL = recomputed_total_usd (tokens × pinned rates snapshot)
No emojis. Decorative copy is presentation-only; accounting is canonical.

Edited by Deiphobe/Codex lineage — 2026-02-06
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import os
import sys
from decimal import Decimal, ROUND_HALF_UP, getcontext
from typing import Any, Dict, List, Optional, Tuple

getcontext().prec = 28

MONEY_Q = Decimal("0.000001")  # audit precision (micro-dollar)
MONEY_2 = Decimal("0.01")

def qmoney(x: Decimal) -> Decimal:
    return x.quantize(MONEY_Q, rounding=ROUND_HALF_UP)

def money_str(x: Decimal, places: str = "micro") -> str:
    if places == "cents":
        return f"${x.quantize(MONEY_2, rounding=ROUND_HALF_UP):,.2f}"
    # micro
    return f"${x.quantize(MONEY_Q, rounding=ROUND_HALF_UP):,.6f}"

def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()

def sha256_hex_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def sha256_hex_file(path: str) -> str:
    with open(path, "rb") as f:
        return sha256_hex_bytes(f.read())

def file_mtime_iso(path: str) -> str:
    ts = os.path.getmtime(path)
    return dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")

def must_exists(path: str, label: str) -> None:
    if not os.path.exists(path):
        raise SystemExit(f"Missing {label}: {path}")

def load_json(path: str) -> Any:
    try:
        return json.loads(read_text(path))
    except Exception as e:
        raise SystemExit(f"Failed to parse JSON: {path} ({e})")

def load_jsonl(path: str) -> Tuple[List[Dict[str, Any]], int]:
    valid: List[Dict[str, Any]] = []
    invalid = 0
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    valid.append(obj)
                else:
                    invalid += 1
            except Exception:
                invalid += 1
    return valid, invalid

def parse_rates(rates_obj: Any) -> Dict[str, Dict[str, Decimal]]:
    if not isinstance(rates_obj, dict):
        raise SystemExit("Rates JSON must be an object mapping model -> {input_per_1m, output_per_1m}")
    out: Dict[str, Dict[str, Decimal]] = {}
    for model, v in rates_obj.items():
        if not isinstance(v, dict):
            continue
        try:
            ip = Decimal(str(v.get("input_per_1m", "0")))
            op = Decimal(str(v.get("output_per_1m", "0")))
        except Exception:
            continue
        out[str(model)] = {"input_per_1m": ip, "output_per_1m": op}
    return out

def compute_cost(inp: int, outp: int, rate: Dict[str, Decimal]) -> Decimal:
    ip = rate.get("input_per_1m", Decimal("0"))
    op = rate.get("output_per_1m", Decimal("0"))
    return qmoney((Decimal(inp) / Decimal(1_000_000)) * ip + (Decimal(outp) / Decimal(1_000_000)) * op)

def esc(s: str) -> str:
    return html.escape(s, quote=True)

def iso_date_from_created_at(created_at: Optional[int]) -> Optional[str]:
    if created_at is None:
        return None
    try:
        d = dt.datetime.fromtimestamp(int(created_at)).date()
        return d.isoformat()
    except Exception:
        return None

def days_span(dates: List[str]) -> int:
    if not dates:
        return 0
    ds = sorted(set(dates))
    d0 = dt.date.fromisoformat(ds[0])
    d1 = dt.date.fromisoformat(ds[-1])
    return (d1 - d0).days + 1

def main() -> int:
    runtime = os.environ.get("OPENCLAW_RUNTIME_DIR", os.path.expanduser("~/.openclaw/runtime"))
    hb_dir = os.path.join(runtime, "logs", "heartbeat")
    ledger_path = os.path.join(hb_dir, "llm_usage.jsonl")
    rates_path = os.path.join(runtime, "config", "model_rates.json")

    must_exists(ledger_path, "ledger")
    must_exists(rates_path, "rates file")

    rates_sha = sha256_hex_file(rates_path)
    rates_mtime = file_mtime_iso(rates_path)
    rates_obj = load_json(rates_path)
    rates = parse_rates(rates_obj)

    entries, invalid_lines = load_jsonl(ledger_path)

    # Quality counters
    missing_source = 0
    missing_tokens = 0
    missing_recorded_cost = 0
    fallback_rate_used = 0
    rates_missing_for_model = 0
    duplicate_sources = 0
    dup_involved = 0

    seen_sources = set()
    dup_sources_set = set()

    # Totals
    total_in = 0
    total_out = 0
    total_tok = 0
    recorded_usd_sum = Decimal("0")
    recomputed_usd_sum = Decimal("0")
    recomputed_usd_on_recorded = Decimal("0")  # only where recorded cost present
    recorded_usd_present_count = 0
    dates: List[str] = []

    # By-model
    by_model: Dict[str, Dict[str, Any]] = {}

    # Per-entry rows
    rows: List[Dict[str, Any]] = []

    for idx, e in enumerate(entries, start=1):
        model = str(e.get("model") or "unknown")
        src = e.get("source")
        if not src:
            missing_source += 1
            src = ""

        if src in seen_sources and src:
            dup_sources_set.add(src)
        else:
            if src:
                seen_sources.add(src)

        created_at = e.get("created_at")
        date = e.get("date") or iso_date_from_created_at(created_at) or ""
        if date:
            dates.append(date)

        inp = e.get("input_tokens")
        outp = e.get("output_tokens")
        tot = e.get("total_tokens")

        try:
            inp_i = int(inp) if inp is not None else 0
            out_i = int(outp) if outp is not None else 0
            if tot is None:
                tot_i = inp_i + out_i
            else:
                tot_i = int(tot)
        except Exception:
            missing_tokens += 1
            inp_i, out_i, tot_i = 0, 0, 0

        total_in += inp_i
        total_out += out_i
        total_tok += tot_i

        rec_cost_raw = e.get("cost_usd")
        rec_cost: Optional[Decimal] = None
        if rec_cost_raw is None:
            missing_recorded_cost += 1
        else:
            try:
                rec_cost = qmoney(Decimal(str(rec_cost_raw)))
                recorded_usd_sum += rec_cost
                recorded_usd_present_count += 1
            except Exception:
                missing_recorded_cost += 1
                rec_cost = None

        # Determine rate
        rate_res = "exact"
        reason = "ok"
        rate = rates.get(model)

        if rate is None:
            rates_missing_for_model += 1
            # Safe fallback behavior: try gpt-5-mini then zero
            if "gpt-5-mini" in rates:
                rate = rates["gpt-5-mini"]
                rate_res = "fallback"
                fallback_rate_used += 1
                reason = f"missing model rate; fell back to gpt-5-mini"
            else:
                rate = {"input_per_1m": Decimal("0"), "output_per_1m": Decimal("0")}
                rate_res = "zero"
                reason = "missing model rate; no fallback available"

        recomputed = compute_cost(inp_i, out_i, rate)
        recomputed_usd_sum += recomputed

        delta = Decimal("0")
        if rec_cost is not None:
            recomputed_usd_on_recorded += recomputed
            delta = qmoney(recomputed - rec_cost)

        # by-model aggregation
        bm = by_model.setdefault(model, {"calls": 0, "in": 0, "out": 0, "usd": Decimal("0"), "rate_res": set()})
        bm["calls"] += 1
        bm["in"] += inp_i
        bm["out"] += out_i
        bm["usd"] += recomputed
        bm["rate_res"].add(rate_res)

        rows.append({
            "n": idx,
            "date": date or "—",
            "model": model,
            "in": inp_i,
            "out": out_i,
            "total": tot_i,
            "source": src,
            "recorded_usd": rec_cost,
            "recomputed_usd": recomputed,
            "delta": delta,
            "rate_res": rate_res,
            "reason": reason,
        })

    # Duplicate source accounting
    if dup_sources_set:
        duplicate_sources = len(dup_sources_set)
        # count how many entries are involved
        for r in rows:
            if r["source"] in dup_sources_set:
                dup_involved += 1

    # Headline numbers
    span_days = days_span(dates)
    official_total = qmoney(recomputed_usd_sum)
    # If span is 0 (no dates), prevent div-by-zero; treat per-day as total
    per_day = official_total if span_days <= 0 else qmoney(official_total / Decimal(span_days))

    # Reconciliation delta only across entries with recorded cost present
    reconciliation_delta = qmoney(recomputed_usd_on_recorded - recorded_usd_sum)

    gen_ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Sort models for display
    model_items = sorted(by_model.items(), key=lambda kv: (-(kv[1]["usd"]), kv[0]))

    # ----- HTML (Art Deco) -----
    title = "OpenClaw Heartbeat Ledger — Accounting Report"
    speech = (
        "Ladies and gentlemen of the electric hour: "
        "the figures are pressed, the columns stand in formation, "
        "and the account is rendered with a steady hand. "
        "Let us spend with intention, reckon with clarity, "
        "and keep the books so honest that fortune tips its hat in passing."
    )

    def badge(label: str, value: str) -> str:
        return f'<span class="badge"><span class="badge-k">{esc(label)}</span><span class="badge-v">{esc(value)}</span></span>'

    # Entry rows HTML
    entry_trs = []
    for r in rows:
        src_short = os.path.basename(r["source"]) if r["source"] else "—"
        src_full = r["source"] or "—"
        rec = "—" if r["recorded_usd"] is None else money_str(r["recorded_usd"])
        rec_micro = "—" if r["recorded_usd"] is None else money_str(r["recorded_usd"], places="micro")
        rec_show = rec_micro  # audit view: micro
        rec_usd = "" if r["recorded_usd"] is None else f'{r["recorded_usd"]:.6f}'

        recom = money_str(r["recomputed_usd"], places="micro")
        delt = money_str(r["delta"], places="micro")
        rate_res = r["rate_res"]
        reason = r["reason"]

        # data-* attributes for sorting
        entry_trs.append(
            "<tr>"
            f"<td class='c-num' data-sort='{r['n']}'>{r['n']}</td>"
            f"<td class='c-date' data-sort='{esc(r['date'])}'>{esc(r['date'])}</td>"
            f"<td class='c-model' data-sort='{esc(r['model'])}'>{esc(r['model'])}</td>"
            f"<td class='c-int' data-sort='{r['in']}'>{r['in']:,}</td>"
            f"<td class='c-int' data-sort='{r['out']}'>{r['out']:,}</td>"
            f"<td class='c-int' data-sort='{r['total']}'>{r['total']:,}</td>"
            f"<td class='c-money' data-sort='{rec_usd}' title='{esc(src_full)}'>{esc(src_short)}<div class='sub'>{esc(src_full)}</div></td>"
            f"<td class='c-money' data-sort='{r['recomputed_usd']:.6f}'>{esc(recom)}</td>"
            f"<td class='c-money' data-sort='{r['delta']:.6f}'>{esc(delt)}</td>"
            f"<td class='c-tag' data-sort='{esc(rate_res)}'><span class='tag {esc(rate_res)}'>{esc(rate_res)}</span></td>"
            f"<td class='c-reason'>{esc(reason)}</td>"
            "</tr>"
        )

    # Model rows HTML
    model_trs = []
    for model, m in model_items:
        rate_res_set = m["rate_res"]
        rr = "exact" if rate_res_set == {"exact"} else "+".join(sorted(rate_res_set))
        model_trs.append(
            "<tr>"
            f"<td class='c-model'>{esc(model)}</td>"
            f"<td class='c-int'>{m['calls']:,}</td>"
            f"<td class='c-int'>{m['in']:,}</td>"
            f"<td class='c-int'>{m['out']:,}</td>"
            f"<td class='c-money'>{esc(money_str(qmoney(m['usd']), places='micro'))}</td>"
            f"<td class='c-tag'><span class='tag {esc('exact' if rr=='exact' else 'fallback')}'>{esc(rr)}</span></td>"
            "</tr>"
        )

    css = r"""
:root{
  --ink:#0c0c0f;
  --coal:#111116;
  --night:#0b0b0e;
  --ivory:#f6f1e7;
  --champ:#e7d3a1;
  --brass:#c6a24a;
  --gold:#e0c46a;
  --smoke:#a9a4a0;
  --line:#2a2a33;
  --panel:#12121a;
  --panel2:#0f0f16;
  --glow: rgba(224,196,106,.18);
  --glow2: rgba(198,162,74,.14);
  --danger:#b24a4a;
  --ok:#2f8f6f;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:radial-gradient(1200px 600px at 20% 0%, var(--glow), transparent 60%),
                                     radial-gradient(900px 600px at 90% 10%, var(--glow2), transparent 55%),
                                     linear-gradient(180deg, var(--night), var(--coal));
          color:var(--ivory); font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, "Noto Sans", "Liberation Sans", sans-serif;}
a{color:var(--gold); text-decoration:none}
.container{max-width:1150px;margin:32px auto;padding:0 18px}
.hero{
  border:1px solid rgba(224,196,106,.35);
  background:linear-gradient(180deg, rgba(18,18,26,.92), rgba(12,12,18,.86));
  box-shadow: 0 18px 60px rgba(0,0,0,.55);
  border-radius:18px;
  overflow:hidden;
  position:relative;
}
.hero:before{
  content:"";
  position:absolute; inset:-2px;
  background:
    linear-gradient(90deg, transparent 0%, rgba(224,196,106,.22) 10%, transparent 20%) 0 0 / 260px 100%,
    linear-gradient(0deg, transparent 0%, rgba(224,196,106,.10) 16%, transparent 32%) 0 0 / 100% 260px;
  opacity:.35;
  pointer-events:none;
}
.hero-inner{padding:26px 26px 18px}
.kicker{
  letter-spacing:.18em;
  text-transform:uppercase;
  color:var(--champ);
  font-size:12px;
  opacity:.95;
}
.title{
  margin:10px 0 6px;
  font-size:34px;
  letter-spacing:.04em;
  font-weight:800;
}
.subtitle{
  margin:0;
  color:rgba(246,241,231,.78);
  font-size:14px;
  line-height:1.55;
  max-width:82ch;
}
.rule{
  height:1px;
  background:linear-gradient(90deg, transparent, rgba(224,196,106,.45), transparent);
  margin:18px 0 14px;
}
.badges{display:flex;flex-wrap:wrap;gap:10px;margin-top:10px}
.badge{
  display:inline-flex; gap:10px; align-items:center;
  padding:10px 12px;
  border-radius:999px;
  border:1px solid rgba(224,196,106,.25);
  background:rgba(10,10,14,.55);
}
.badge-k{font-size:12px; color:rgba(246,241,231,.7); letter-spacing:.10em; text-transform:uppercase}
.badge-v{font-weight:700; color:var(--ivory); font-variant-numeric: tabular-nums}
.grid{display:grid;grid-template-columns: 1.2fr .8fr; gap:16px; margin-top:16px}
.card{
  border:1px solid rgba(224,196,106,.22);
  background:linear-gradient(180deg, rgba(18,18,26,.86), rgba(14,14,22,.74));
  border-radius:16px;
  padding:18px;
  box-shadow: 0 10px 40px rgba(0,0,0,.45);
}
.card h2{
  margin:0 0 10px;
  letter-spacing:.14em;
  text-transform:uppercase;
  font-size:12px;
  color:rgba(231,211,161,.92);
}
.card p{margin:0;color:rgba(246,241,231,.80);line-height:1.65}
.statgrid{display:grid;grid-template-columns: 1fr 1fr; gap:10px}
.stat{
  border:1px solid rgba(224,196,106,.18);
  background:rgba(9,9,12,.42);
  border-radius:14px;
  padding:12px 12px;
}
.stat .k{font-size:12px; color:rgba(246,241,231,.72); letter-spacing:.10em; text-transform:uppercase}
.stat .v{margin-top:6px; font-size:18px; font-weight:800; color:var(--ivory); font-variant-numeric: tabular-nums}
.stat .s{margin-top:4px; font-size:12px; color:rgba(169,164,160,.85)}
.section{
  margin-top:18px;
  border:1px solid rgba(224,196,106,.18);
  border-radius:16px;
  overflow:hidden;
  background:rgba(10,10,14,.45);
}
.section-head{
  padding:14px 16px;
  background:linear-gradient(90deg, rgba(224,196,106,.18), rgba(18,18,26,.0));
  border-bottom:1px solid rgba(224,196,106,.18);
  display:flex; align-items:center; justify-content:space-between; gap:12px;
}
.section-head h3{
  margin:0;
  letter-spacing:.16em;
  text-transform:uppercase;
  font-size:12px;
  color:rgba(246,241,231,.85);
}
.tools{display:flex; gap:10px; align-items:center; flex-wrap:wrap}
.btn{
  cursor:pointer;
  padding:9px 12px;
  border-radius:999px;
  border:1px solid rgba(224,196,106,.24);
  background:rgba(11,11,16,.55);
  color:rgba(246,241,231,.88);
  font-weight:700;
  letter-spacing:.06em;
  text-transform:uppercase;
  font-size:11px;
}
.btn:hover{border-color: rgba(224,196,106,.5)}
.tablewrap{overflow:auto}
table{width:100%; border-collapse:separate; border-spacing:0}
th,td{padding:12px 12px; vertical-align:top; border-bottom:1px solid rgba(224,196,106,.10)}
th{
  position:sticky; top:0;
  background:rgba(10,10,14,.95);
  backdrop-filter: blur(6px);
  text-align:left;
  font-size:12px;
  letter-spacing:.12em;
  text-transform:uppercase;
  color:rgba(231,211,161,.90);
  cursor:pointer;
}
td{font-size:13px;color:rgba(246,241,231,.86); font-variant-numeric: tabular-nums}
.sub{margin-top:6px; font-size:11px; color:rgba(169,164,160,.78); max-width:70ch; white-space:normal}
.c-num{width:60px}
.c-date{width:120px}
.c-int{width:110px}
.c-money{width:170px}
.c-tag{width:110px}
.tag{
  display:inline-flex; align-items:center; justify-content:center;
  padding:4px 10px; border-radius:999px;
  border:1px solid rgba(224,196,106,.25);
  background:rgba(0,0,0,.25);
  font-size:11px;
  letter-spacing:.12em;
  text-transform:uppercase;
}
.tag.exact{border-color: rgba(47,143,111,.45); color: rgba(166,238,212,.92)}
.tag.fallback{border-color: rgba(224,196,106,.55); color: rgba(246,241,231,.9)}
.tag.zero{border-color: rgba(178,74,74,.55); color: rgba(255,200,200,.9)}
.footer{
  margin:22px 4px 6px;
  color:rgba(169,164,160,.86);
  font-size:12px;
  line-height:1.6;
}
hr.sep{border:0;height:1px;background:linear-gradient(90deg, transparent, rgba(224,196,106,.35), transparent); margin:18px 0}
.small{font-size:12px;color:rgba(169,164,160,.86)}
"""

    js = r"""
(function(){
  function getCellValue(tr, idx){
    const td = tr.children[idx];
    if(!td) return "";
    const s = td.getAttribute("data-sort");
    if(s !== null) return s;
    return td.innerText || "";
  }
  function comparer(idx, asc){
    return function(a,b){
      const va = getCellValue(asc ? a : b, idx);
      const vb = getCellValue(asc ? b : a, idx);
      const na = Number(va), nb = Number(vb);
      if(!Number.isNaN(na) && !Number.isNaN(nb)) return na - nb;
      return String(va).localeCompare(String(vb));
    }
  }
  function makeSortable(tableId){
    const table = document.getElementById(tableId);
    if(!table) return;
    const ths = table.querySelectorAll("th");
    ths.forEach((th, idx) => {
      let asc = true;
      th.addEventListener("click", () => {
        const tbody = table.tBodies[0];
        Array.from(tbody.querySelectorAll("tr"))
          .sort(comparer(idx, asc))
          .forEach(tr => tbody.appendChild(tr));
        asc = !asc;
      });
    });
  }
  function copyText(txt){
    navigator.clipboard.writeText(txt).catch(()=>{});
  }
  document.getElementById("copy-sha")?.addEventListener("click", () => {
    copyText(document.getElementById("rates-sha")?.innerText || "");
  });
  document.getElementById("copy-ledger")?.addEventListener("click", () => {
    copyText(document.getElementById("ledger-path")?.innerText || "");
  });
  makeSortable("model-table");
  makeSortable("entry-table");
})();
"""

    # Build warnings list
    warnings = []
    if invalid_lines:
        warnings.append(f"Invalid JSON lines: {invalid_lines}")
    if fallback_rate_used:
        warnings.append(f"Fallback rate used: {fallback_rate_used}")
    if rates_missing_for_model:
        warnings.append(f"Rates missing for model: {rates_missing_for_model}")
    if duplicate_sources:
        warnings.append(f"Duplicate sources: {duplicate_sources} (entries involved: {dup_involved})")

    warnings_html = ""
    if warnings:
        warnings_html = "<ul>" + "".join(f"<li>{esc(w)}</li>" for w in warnings) + "</ul>"
    else:
        warnings_html = "<p class='small'>No warnings. The ledger is clean: exact rates, no duplicates, no drift.</p>"

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{esc(title)}</title>
<style>{css}</style>
</head>
<body>
  <div class="container">
    <div class="hero">
      <div class="hero-inner">
        <div class="kicker">OpenClaw • Heartbeat • Ledger</div>
        <div class="title">Accounting Report</div>
        <p class="subtitle">
          Audit-grade totals, pinned rates, explicit reconciliation. Presentation is decorative; arithmetic is canonical.
        </p>
        <div class="rule"></div>
        <div class="badges">
          {badge("Generated", gen_ts)}
          {badge("Policy", "OFFICIAL = recomputed_total_usd")}
          <span class="badge"><span class="badge-k">Rates SHA</span><span class="badge-v" id="rates-sha">{esc(rates_sha)}</span></span>
          <span class="badge"><span class="badge-k">Rates mtime</span><span class="badge-v">{esc(rates_mtime)}</span></span>
          <span class="badge"><span class="badge-k">Ledger</span><span class="badge-v" id="ledger-path">{esc(ledger_path)}</span></span>
        </div>

        <div class="grid">
          <div class="card">
            <h2>A Word From the Ledger</h2>
            <p>{esc(speech)}</p>
            <hr class="sep"/>
            <p class="small">
              Total account: <b>{esc(money_str(official_total, places="micro"))}</b> •
              Official per day: <b>{esc(money_str(per_day, places="micro"))}</b>
            </p>
          </div>

          <div class="card">
            <h2>Headline Figures</h2>
            <div class="statgrid">
              <div class="stat"><div class="k">Entries valid</div><div class="v">{len(entries):,}</div><div class="s">Invalid JSON: {invalid_lines}</div></div>
              <div class="stat"><div class="k">Recorded span</div><div class="v">{span_days:,} day(s)</div><div class="s">Based on entry dates</div></div>
              <div class="stat"><div class="k">Tokens input</div><div class="v">{total_in:,}</div><div class="s">Sum across entries</div></div>
              <div class="stat"><div class="k">Tokens output</div><div class="v">{total_out:,}</div><div class="s">Sum across entries</div></div>
              <div class="stat"><div class="k">Tokens total</div><div class="v">{total_tok:,}</div><div class="s">Input + output</div></div>
              <div class="stat"><div class="k">OFFICIAL total USD</div><div class="v">{esc(money_str(official_total, places="micro"))}</div><div class="s">Pinned rates snapshot</div></div>
              <div class="stat"><div class="k">Recorded USD</div><div class="v">{esc(money_str(qmoney(recorded_usd_sum), places="micro"))}</div><div class="s">Present in {recorded_usd_present_count} entries</div></div>
              <div class="stat"><div class="k">Reconciliation delta</div><div class="v">{esc(money_str(reconciliation_delta, places="micro"))}</div><div class="s">Recomputed − recorded</div></div>
            </div>
            <hr class="sep"/>
            <div class="tools">
              <button class="btn" id="copy-sha" type="button">Copy Rates SHA</button>
              <button class="btn" id="copy-ledger" type="button">Copy Ledger Path</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="section" style="margin-top:18px">
      <div class="section-head">
        <h3>Data Quality</h3>
        <div class="tools">
          <span class="small">Missing source: <b>{missing_source}</b></span>
          <span class="small">Missing tokens: <b>{missing_tokens}</b></span>
          <span class="small">Missing recorded cost: <b>{missing_recorded_cost}</b></span>
          <span class="small">Fallback rate: <b>{fallback_rate_used}</b></span>
          <span class="small">Dup sources: <b>{duplicate_sources}</b></span>
        </div>
      </div>
      <div class="hero-inner" style="padding-top:14px">
        {warnings_html}
      </div>
    </div>

    <div class="section">
      <div class="section-head">
        <h3>By Model</h3>
        <div class="tools small">Click headers to sort</div>
      </div>
      <div class="tablewrap">
        <table id="model-table">
          <thead>
            <tr>
              <th>Model</th>
              <th>Calls</th>
              <th>Input</th>
              <th>Output</th>
              <th>Recomputed USD</th>
              <th>Rate</th>
            </tr>
          </thead>
          <tbody>
            {''.join(model_trs)}
          </tbody>
        </table>
      </div>
    </div>

    <div class="section">
      <div class="section-head">
        <h3>Entries</h3>
        <div class="tools small">Click headers to sort • Sources show full path</div>
      </div>
      <div class="tablewrap">
        <table id="entry-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Date</th>
              <th>Model</th>
              <th>In</th>
              <th>Out</th>
              <th>Total</th>
              <th>Source</th>
              <th>Recomputed USD</th>
              <th>Delta</th>
              <th>Rate</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            {''.join(entry_trs)}
          </tbody>
        </table>
      </div>
    </div>

    <div class="footer">
      <div><b>Canonical arithmetic</b>: recomputed_total_usd = Σ(cost(tokens × pinned rates)).</div>
      <div>Rates file SHA pins the pricing snapshot used for recomputation: <span class="small">{esc(rates_sha)}</span></div>
      <div class="small">Generated by ledger_render_report_accounting_html.py — presentation-only embellishments do not affect totals.</div>
    </div>
  </div>

<script>{js}</script>
</body>
</html>
"""

    out_html = os.path.join(hb_dir, "ledger_report_accounting_deco_latest.html")
    os.makedirs(hb_dir, exist_ok=True)
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html_doc)

    print(f"HTML report written to: {out_html}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
