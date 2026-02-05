#!/usr/bin/env python3
"""
gmail_cleanup_from_config.py

Runs gmail_cleanup_dryrun.py using senders from:
  ~/.openclaw/runtime/config/gmail_cleanup_senders.json

Notes:
- Uses sys.executable so cron + venv are consistent
- Calls the module script directly (no wrappers)
"""
import os
import json
import subprocess
import sys

HOME = os.path.expanduser("~")
CONFIG_PATH = os.path.join(HOME, ".openclaw", "runtime", "config", "gmail_cleanup_senders.json")
HERE = os.path.dirname(os.path.abspath(__file__))
DRYRUN = os.path.join(HERE, "gmail_cleanup_dryrun.py")


def main() -> int:
    if not os.path.exists(CONFIG_PATH):
        print(f"Config file not found: {CONFIG_PATH}", file=sys.stderr)
        return 1

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    senders = []
    for item in cfg.get("senders", []):
        email = (item.get("email") or "").strip()
        if email:
            senders.append(email)

    if not senders:
        print("No senders configured in config file", file=sys.stderr)
        return 1

    days = int(cfg.get("default_days", 180))
    samples = int(cfg.get("default_samples", 20))

    print(f"Running cleanup dry-run for {len(senders)} senders (days={days}, samples={samples})...")
    for item in cfg.get("senders", []):
        email = (item.get("email") or "").strip()
        if email:
            print(f"  • {email} ({item.get('reason', 'no reason')})")
    print()

    cmd = [
        sys.executable,
        DRYRUN,
        "--senders", ",".join(senders),
        "--days", str(days),
        "--samples", str(samples),
    ]

    print("[from_config] exec:", " ".join(cmd))
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())