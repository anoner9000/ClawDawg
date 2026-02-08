#!/usr/bin/env python3
"""
gmail_cleanup_manage_senders.py (CANONICAL)

Supports BOTH schemas for cfg["senders"]:
  A) legacy: list[str] emails
  B) new: list[{"email":..., "reason":..., "added":..., "added_by":...}]

Canonical artifacts:
- Config: ~/.openclaw/runtime/config/gmail_cleanup_senders.json
- Audit log (JSONL): ~/.openclaw/runtime/logs/gmail_sender_changes.log

CLI:
  list
  add <email> --reason "..." --by "name"
  remove <email> --by "name"
  normalize --by "name"   # rewrites config to object schema (dedup + lowercase)
"""

import argparse
import datetime as dt
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

RUNTIME = Path(os.path.expanduser("~/.openclaw/runtime"))
CONFIG_PATH = RUNTIME / "config" / "gmail_cleanup_senders.json"
AUDIT_PATH = RUNTIME / "logs" / "gmail_sender_changes.log"

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _norm_email(s: str) -> str:
    return (s or "").strip().lower()


def _validate_email(s: str) -> None:
    if not EMAIL_RE.match(s):
        raise SystemExit(f"Invalid email: {s}")


def _load_cfg() -> Dict[str, Any]:
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            cfg = json.load(f)
            if not isinstance(cfg, dict):
                raise SystemExit(f"Config is not a JSON object: {CONFIG_PATH}")
            return cfg
    return {"senders": [], "default_days": 180, "default_samples": 20}


def _write_cfg(cfg: Dict[str, Any]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _audit(operator: str, action: str, target: str, extra: Dict[str, Any] | None = None) -> None:
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry: Dict[str, Any] = {
        "operator": operator,
        "action": action,
        "target": target,
        "time": dt.datetime.now().isoformat(),
    }
    if extra:
        entry.update(extra)
    with AUDIT_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _coerce_senders(raw: Any) -> Tuple[List[Dict[str, Any]], bool]:
    """
    Returns: (senders_as_objects, was_legacy_or_messy)
    """
    if raw is None:
        return ([], False)

    if not isinstance(raw, list):
        # if totally wrong type, treat as empty but mark messy
        return ([], True)

    out: List[Dict[str, Any]] = []
    messy = False

    for item in raw:
        if isinstance(item, str):
            email = _norm_email(item)
            if not email:
                messy = True
                continue
            out.append({"email": email})
            messy = True  # legacy schema
        elif isinstance(item, dict):
            email = _norm_email(item.get("email", ""))
            if not email:
                messy = True
                continue
            obj = dict(item)
            obj["email"] = email
            out.append(obj)
        else:
            messy = True

    return (out, messy)


def _dedup_objects(objs: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], bool]:
    seen = set()
    out: List[Dict[str, Any]] = []
    changed = False
    for o in objs:
        email = _norm_email(o.get("email", ""))
        if not email:
            changed = True
            continue
        if email in seen:
            changed = True
            continue
        seen.add(email)
        if o.get("email") != email:
            changed = True
            o = dict(o)
            o["email"] = email
        out.append(o)
    return (out, changed)


def _get_sender_objects(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], bool]:
    objs, messy = _coerce_senders(cfg.get("senders"))
    objs, dedup_changed = _dedup_objects(objs)
    return (objs, messy or dedup_changed)


def cmd_list(cfg: Dict[str, Any]) -> int:
    senders, _ = _get_sender_objects(cfg)
    if not senders:
        print("(no senders configured)")
        return 0

    def k(x: Dict[str, Any]) -> str:
        return _norm_email(x.get("email", ""))

    for s in sorted(senders, key=k):
        email = s.get("email", "")
        reason = s.get("reason", "")
        added = s.get("added", "")
        added_by = s.get("added_by", "")
        line = email
        if reason:
            line += f" — {reason}"
        if added or added_by:
            line += f" (added {added or '?'} by {added_by or '?'})"
        print(line)
    return 0


def cmd_add(cfg: Dict[str, Any], email: str, reason: str, by: str) -> int:
    email_n = _norm_email(email)
    _validate_email(email_n)

    senders, _ = _get_sender_objects(cfg)
    if any(_norm_email(s.get("email", "")) == email_n for s in senders):
        print(f"already_present: {email_n}")
        return 0

    senders.append(
        {
            "email": email_n,
            "reason": reason,
            "added": dt.date.today().isoformat(),
            "added_by": by,
        }
    )

    # auto-normalize on write (object schema)
    senders, _ = _dedup_objects(senders)
    cfg["senders"] = senders
    _write_cfg(cfg)
    _audit(by, "add", email_n, {"reason": reason})
    print(f"added: {email_n}")
    return 0


def cmd_remove(cfg: Dict[str, Any], email: str, by: str) -> int:
    email_n = _norm_email(email)
    _validate_email(email_n)

    senders, _ = _get_sender_objects(cfg)
    before = len(senders)
    senders = [s for s in senders if _norm_email(s.get("email", "")) != email_n]
    after = len(senders)

    if after == before:
        print(f"not_found: {email_n}")
        return 0

    cfg["senders"] = senders
    _write_cfg(cfg)
    _audit(by, "remove", email_n)
    print(f"removed: {email_n}")
    return 0


def cmd_normalize(cfg: Dict[str, Any], by: str) -> int:
    senders, changed = _get_sender_objects(cfg)
    # force object schema + known keys
    normalized: List[Dict[str, Any]] = []
    for s in senders:
        email = _norm_email(s.get("email", ""))
        if not email:
            continue
        out = {"email": email}
        # keep optional fields if present
        for k in ("reason", "added", "added_by"):
            if k in s and s[k]:
                out[k] = s[k]
        normalized.append(out)

    cfg["senders"] = normalized
    _write_cfg(cfg)
    _audit(by, "normalize", "senders")
    print(f"normalized: {len(normalized)} senders")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list")

    p_add = sub.add_parser("add")
    p_add.add_argument("email")
    p_add.add_argument("--reason", default="manual quarantine")
    p_add.add_argument("--by", default="Uther")

    p_rm = sub.add_parser("remove")
    p_rm.add_argument("email")
    p_rm.add_argument("--by", default="Uther")

    p_norm = sub.add_parser("normalize")
    p_norm.add_argument("--by", default="Uther")

    args = p.parse_args()
    cfg = _load_cfg()

    if args.cmd == "list":
        return cmd_list(cfg)
    if args.cmd == "add":
        return cmd_add(cfg, args.email, args.reason, args.by)
    if args.cmd == "remove":
        return cmd_remove(cfg, args.email, args.by)
    if args.cmd == "normalize":
        return cmd_normalize(cfg, args.by)

    raise SystemExit("unhandled command")


if __name__ == "__main__":
    raise SystemExit(main())
