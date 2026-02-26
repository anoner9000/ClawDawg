#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

@dataclass
class TimeNow:
    status: str
    source: str
    timezone: str
    utc_iso: str
    local_iso: str
    plain_english: str
    epoch: int
    offset_seconds: int

def _ordinal(n: int) -> str:
    if 10 <= (n % 100) <= 20:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")

def fmt_plain_english(dt_local: datetime, tz_name: str) -> str:
    tz_abbr = dt_local.tzname() or tz_name
    hour_12 = dt_local.strftime("%I").lstrip("0") or "12"
    minute = dt_local.strftime("%M")
    ampm = dt_local.strftime("%p")
    weekday = dt_local.strftime("%A")
    month = dt_local.strftime("%B")
    day = int(dt_local.strftime("%d"))
    year = dt_local.strftime("%Y")
    return f"It’s {hour_12}:{minute} {ampm} {tz_abbr} on {weekday}, {month} {day}{_ordinal(day)}, {year}."

def get_now(tz_name: str) -> TimeNow:
    tz = ZoneInfo(tz_name)
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(tz)
    offset = int(now_local.utcoffset().total_seconds()) if now_local.utcoffset() else 0
    return TimeNow(
        status="ok",
        source="system_clock",
        timezone=tz_name,
        utc_iso=now_utc.isoformat(),
        local_iso=now_local.isoformat(),
        plain_english=fmt_plain_english(now_local, tz_name),
        epoch=int(now_utc.timestamp()),
        offset_seconds=offset,
    )

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tz", default="America/Chicago")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    tn = get_now(args.tz)
    if args.json:
        print(json.dumps(asdict(tn), indent=2, ensure_ascii=False))
    else:
        print(tn.plain_english)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
