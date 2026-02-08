#!/usr/bin/env python3
import json, pathlib, sys
from collections import Counter
from datetime import date, timedelta

LEDGER = pathlib.Path.home()/".openclaw/runtime/logs/heartbeat/llm_usage.jsonl"

def load_rows():
    if not LEDGER.exists():
        return []
    rows=[]
    for line in LEDGER.read_text().splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows

def main():
    days = 14
    if len(sys.argv) > 1:
        days = int(sys.argv[1])

    cutoff = (date.today() - timedelta(days=days)).isoformat()

    rows = [r for r in load_rows() if (r.get("date") or "") >= cutoff]
    calls = len(rows)
    total = sum(int(r.get("total_tokens") or 0) for r in rows)

    by_model = Counter()
    by_day = Counter()
    for r in rows:
        by_model[r.get("model","unknown")] += int(r.get("total_tokens") or 0)
        by_day[r.get("date","unknown")] += int(r.get("total_tokens") or 0)

    print(f"Custodian ledger summary (last {days} days)")
    print(f"- calls: {calls}")
    print(f"- total_tokens: {total:,}")
    print("- tokens_by_model:")
    for m,t in by_model.most_common():
        print(f"  - {m}: {t:,}")
    print("- tokens_by_date:")
    for d in sorted(by_day):
        print(f"  - {d}: {by_day[d]:,}")

if __name__ == "__main__":
    raise SystemExit(main())
