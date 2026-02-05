#!/usr/bin/env python3
"""
gmail_cleanup_manage_senders.py
Manage the sender list for Gmail cleanup.

Usage:
  python3 gmail_cleanup_manage_senders.py list
  python3 gmail_cleanup_manage_senders.py add "email@example.com" "Reason" [--added-by NAME]
  python3 gmail_cleanup_manage_senders.py remove "email@example.com" [--added-by NAME]

Config: ~/.openclaw/runtime/config/gmail_cleanup_senders.json
Audit log: ~/.openclaw/runtime/logs/gmail_sender_changes.jsonl
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict


HOME = os.path.expanduser("~")
CONFIG_PATH = os.path.join(HOME, ".openclaw", "runtime", "config", "gmail_cleanup_senders.json")
AUDIT_LOG = os.path.join(HOME, ".openclaw", "runtime", "logs", "gmail_sender_changes.jsonl")


DEFAULT_CONFIG = {"senders": [], "default_days": 180, "default_samples": 20}


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dirs() -> None:
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    os.makedirs(os.path.dirname(AUDIT_LOG), exist_ok=True)


def atomic_write_json(path: str, data: Dict[str, Any]) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    os.chmod(path, 0o600)


def load_config() -> Dict[str, Any]:
    if not os.path.exists(CONFIG_PATH):
        return dict(DEFAULT_CONFIG)

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        # If corrupted, preserve by renaming and starting fresh
        backup = CONFIG_PATH + ".corrupt." + datetime.utcnow().strftime("%Y%m%d%H%M%S")
        os.replace(CONFIG_PATH, backup)
        print(f"Warning: config was invalid JSON. Moved to: {backup}", file=sys.stderr)
        return dict(DEFAULT_CONFIG)

    if not isinstance(cfg, dict):
        return dict(DEFAULT_CONFIG)
    cfg.setdefault("senders", [])
    cfg.setdefault("default_days", 180)
    cfg.setdefault("default_samples", 20)
    if not isinstance(cfg["senders"], list):
        cfg["senders"] = []
    return cfg


def save_config(cfg: Dict[str, Any]) -> None:
    ensure_dirs()
    atomic_write_json(CONFIG_PATH, cfg)


def valid_email(email: str) -> bool:
    email = (email or "").strip()
    return bool(email) and "@" in email and " " not in email


def audit(operator: str, action: str, target: str, reason: str = "") -> None:
    ensure_dirs()
    entry = {
        "time": now_utc_iso(),
        "operator": operator,
        "action": action,
        "target": target,
        "reason": reason,
    }
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def add_sender(email: str, reason: str, operator: str) -> bool:
    if not valid_email(email):
        print(f"Invalid email: {email}", file=sys.stderr)
        return False

    cfg = load_config()
    existing = { (s.get("email") or "").lower() for s in cfg["senders"] if isinstance(s, dict) }
    if email.lower() in existing:
        print(f"Sender already exists: {email}")
        return False

    cfg["senders"].append(
        {
            "email": email.strip(),
            "reason": reason or "No reason provided",
            "added": datetime.now().strftime("%Y-%m-%d"),
            "added_by": operator,
        }
    )
    save_config(cfg)
    audit(operator, "add", email.strip(), reason or "")
    print(f"Added: {email}")
    return True


def remove_sender(email: str, operator: str) -> bool:
    if not valid_email(email):
        print(f"Invalid email: {email}", file=sys.stderr)
        return False

    cfg = load_config()
    before = len(cfg["senders"])
    cfg["senders"] = [
        s for s in cfg["senders"]
        if not (isinstance(s, dict) and (s.get("email") or "").lower() == email.lower())
    ]
    if len(cfg["senders"]) == before:
        print(f"Sender not found: {email}")
        return False

    save_config(cfg)
    audit(operator, "remove", email.strip(), "")
    print(f"Removed: {email}")
    return True


def list_senders() -> None:
    cfg = load_config()
    senders = [s for s in cfg.get("senders", []) if isinstance(s, dict)]
    if not senders:
        print("No senders configured")
        return

    print(f"Gmail Cleanup Senders ({len(senders)} total):")
    for s in senders:
        print(f"  • {s.get('email','')}")
        print(f"    Reason: {s.get('reason', 'N/A')}")
        print(f"    Added: {s.get('added', 'N/A')} by {s.get('added_by', 'N/A')}")


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="List configured senders")

    p_add = sub.add_parser("add", help="Add a sender")
    p_add.add_argument("email")
    p_add.add_argument("reason", nargs="?", default="No reason provided")
    p_add.add_argument("--added-by", dest="operator", default=os.environ.get("USER", "unknown"))

    p_rm = sub.add_parser("remove", help="Remove a sender")
    p_rm.add_argument("email")
    p_rm.add_argument("--added-by", dest="operator", default=os.environ.get("USER", "unknown"))

    args = p.parse_args()

    if args.cmd == "list":
        list_senders()
    elif args.cmd == "add":
        add_sender(args.email, args.reason, args.operator)
    elif args.cmd == "remove":
        remove_sender(args.email, args.operator)
    else:
        p.print_help()
        raise SystemExit(1)


if __name__ == "__main__":
    main()
