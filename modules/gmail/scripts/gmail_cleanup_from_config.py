#!/usr/bin/env python3
"""
gmail_cleanup_from_config.py
Runs gmail_cleanup_dryrun.py using senders from config file.

Config: ~/.openclaw/runtime/config/gmail_cleanup_senders.json
Schema:
{
  "senders": [{"email":"a@b.com","reason":"...","added":"YYYY-MM-DD","added_by":"..."}],
  "default_days": 180,
  "default_samples": 20
}
"""
import json
import os
import subprocess
import sys


HOME = os.path.expanduser("~")
CONFIG_PATH = os.path.join(HOME, ".openclaw", "runtime", "config", "gmail_cleanup_senders.json")


def die(msg: str, code: int = 1) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def main() -> None:
    if not os.path.exists(CONFIG_PATH):
        die(f"Config file not found: {CONFIG_PATH}")

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        die(f"Failed to read config JSON: {CONFIG_PATH}\n{e}")

    raw_senders = config.get("senders", [])
    if not isinstance(raw_senders, list):
        die("Config error: 'senders' must be a list")

    senders = []
    bad = 0
    for s in raw_senders:
        if isinstance(s, dict):
            email = (s.get("email") or "").strip()
        elif isinstance(s, str):
            # tolerate legacy list-of-strings if it ever appears
            email = s.strip()
        else:
            email = ""
        if email and "@" in email:
            senders.append(email)
        else:
            bad += 1

    if not senders:
        die("No valid senders configured in config file")

    days = config.get("default_days", 180)
    samples = config.get("default_samples", 20)
    try:
        days = int(days)
        samples = int(samples)
    except Exception:
        die("Config error: default_days and default_samples must be integers")

    if days <= 0 or samples <= 0:
        die("Config error: default_days and default_samples must be > 0")

    print(f"Running cleanup dry-run for {len(senders)} senders (days={days}, samples={samples})...")
    for s in raw_senders:
        if isinstance(s, dict) and s.get("email"):
            print(f"  • {s['email']} ({s.get('reason', 'no reason')})")
    if bad:
        print(f"\nNote: skipped {bad} invalid sender entries.\n")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    dryrun_path = os.path.join(script_dir, "gmail_cleanup_dryrun.py")

    if not os.path.exists(dryrun_path):
        die(f"Expected dry-run script not found next to this file: {dryrun_path}")

    cmd = [
        "python3",
        dryrun_path,
        "--senders",
        ",".join(senders),
        "--days",
        str(days),
        "--samples",
        str(samples),
    ]

    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
