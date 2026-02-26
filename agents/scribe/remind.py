#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

def main(argv: list[str]) -> int:
    # HARD boundary: only Scribe should execute this directly.
    # Other agents must request Scribe to run it.
    allow = os.environ.get("OPENCLAW_ALLOW_NON_SCRIBE", "").lower() in ("1", "true", "yes")
    who = os.environ.get("OPENCLAW_AGENT", "")
    if not allow and who not in ("scribe", "Scribe"):
        print("ERROR: Reminder authority is Scribe-only. Route request to Scribe.", file=sys.stderr)
        return 3

    svc = Path("services/reminders.py")
    if not svc.exists():
        print("ERROR: services/reminders.py not found (run from repo root).", file=sys.stderr)
        return 2
    return subprocess.call([sys.executable, str(svc), *argv])

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
