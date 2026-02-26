#!/usr/bin/env python3
"""
reminder_authority_audit.py

Enforce reminder/time authority boundaries.

Rules:
1) Agent code outside agents/scribe/* must not reference reminder ledger state tokens.
2) Agent code must not call services/reminders.py create directly (must route via agents/scribe/remind.py).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AGENTS_DIR = ROOT / "agents"

# Gate executable-ish sources only (avoid docs/fixtures false positives).
CODE_SUFFIXES = {".py", ".sh", ".bash", ".zsh"}

FAILS: list[str] = []


def fail(msg: str) -> None:
    FAILS.append(msg)


def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def is_code_file(p: Path) -> bool:
    if p.suffix.lower() in CODE_SUFFIXES:
        return True
    # Extensionless executable scripts with shebang
    try:
        with p.open("r", encoding="utf-8", errors="replace") as f:
            first = f.readline(256)
        return first.startswith("#!")
    except Exception:
        return False


def check_ledger_write_boundary() -> None:
    # Outside scribe code, block direct ledger path and ledger env token references.
    forbidden = [
        re.compile(r"memory/reminders\.jsonl"),
        re.compile(r"OPENCLAW_REMINDER_LEDGER"),
    ]
    for p in AGENTS_DIR.rglob("*"):
        if not p.is_file() or not is_code_file(p):
            continue
        rel = p.relative_to(ROOT).as_posix()
        if rel.startswith("agents/scribe/"):
            continue
        text = read_text(p)
        for pat in forbidden:
            if pat.search(text):
                fail(f"[rule1] non-scribe agent references reminder ledger token: {rel} (matched {pat.pattern})")
                break


def check_no_direct_service_create_calls() -> None:
    # Forbid direct create calls from agent code; route via agents/scribe/remind.py.
    # Catch: python services/reminders.py create, python3 services/reminders.py create, and bare services/reminders.py create
    direct_create = re.compile(
        r"""(?ix)
        (?:^|\s)
        (?:python(?:3)?\s+)?services/reminders\.py\s+create\b
        """
    )
    for p in AGENTS_DIR.rglob("*"):
        if not p.is_file() or not is_code_file(p):
            continue
        rel = p.relative_to(ROOT).as_posix()
        # allow the wrapper itself to invoke the service
        if rel == "agents/scribe/remind.py":
            continue
        text = read_text(p)
        if direct_create.search(text):
            fail(f"[rule2] agent directly calls services/reminders.py create: {rel} (must route via agents/scribe/remind.py)")


def main() -> int:
    if not AGENTS_DIR.exists():
        fail("agents/ directory missing")
    else:
        check_ledger_write_boundary()
        check_no_direct_service_create_calls()

    if FAILS:
        print("❌ Reminder authority audit FAILED:", file=sys.stderr)
        for f in FAILS:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print("✅ Reminder authority audit PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
