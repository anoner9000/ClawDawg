#!/usr/bin/env python3
"""
agent_boundary_audit.py

Mechanical audit for Agent Topology v2.

Checks:
- Canonical roster matches required list.
- No non-custodian RUNBOOK.md contains templates for state=complete.
- Agent directories exist for canonical roster.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # ops/scripts/agents/ -> repo root
AGENTS_MD = ROOT / "AGENTS.md"
AGENTS_DIR = ROOT / "agents"

CANONICAL = [
    "custodian",
    "deiphobe",
    "executor-code",
    "executor-comm",
    "executor-doc",
    "executor-ui",
    "scribe",
]

FAILS: list[str] = []

def fail(msg: str) -> None:
    FAILS.append(msg)

def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")

def check_agents_md() -> None:
    if not AGENTS_MD.exists():
        fail("AGENTS.md missing at repo root")
        return
    s = read_text(AGENTS_MD)

    # Heuristic: ensure each canonical name appears as a roster entry somewhere.
    # (We avoid overfitting exact formatting; this is a governance guard, not a parser contract.)
    for a in CANONICAL:
        if re.search(rf"(?mi)^\s*[-*]?\s*`?{re.escape(a)}`?\b", s) is None and a not in s:
            fail(f"AGENTS.md does not appear to list canonical agent: {a}")

def check_agent_dirs() -> None:
    if not AGENTS_DIR.exists():
        fail("agents/ directory missing")
        return
    for a in CANONICAL:
        d = AGENTS_DIR / a
        if not d.exists():
            fail(f"Missing agent directory: agents/{a}")
            continue
        soul = d / "SOUL.md"
        runbook = d / "RUNBOOK.md"
        if not soul.exists():
            fail(f"Missing SOUL.md: agents/{a}/SOUL.md")
        if not runbook.exists():
            fail(f"Missing RUNBOOK.md: agents/{a}/RUNBOOK.md")

def check_runbooks_no_complete() -> None:
    # Non-custodian runbooks must not template state=complete.
    for a in CANONICAL:
        rb = AGENTS_DIR / a / "RUNBOOK.md"
        if not rb.exists():
            continue
        s = read_text(rb)
        if a != "custodian":
            if re.search(r'(?i)\bstate\s*["=: ]\s*complete\b', s) or re.search(r'(?i)"state"\s*:\s*"complete"', s):
                fail(f"Non-custodian runbook contains state=complete template: {rb}")
            if re.search(r'(?i)TASK_UPDATE.*complete', s):
                fail(f"Non-custodian runbook mentions TASK_UPDATE complete: {rb}")

def main() -> int:
    check_agents_md()
    check_agent_dirs()
    check_runbooks_no_complete()

    if FAILS:
        print("❌ Agent boundary audit FAILED:", file=sys.stderr)
        for f in FAILS:
            print(f"  - {f}", file=sys.stderr)
        return 2

    print("✅ Agent boundary audit PASSED")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())




# --- GLOBAL_COMPLETE_SCAN ---
# Prevent any direct completion emission outside responder

import sys
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]

COMPLETE_PATTERN = re.compile(r'"state"\s*:\s*"complete"|TASK_UPDATE.*complete')

def scan_for_illegal_complete():
    violations = []

    for path in ROOT.rglob("*.py"):
        if "agent_status_responder.py" in str(path):
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for lineno, line in enumerate(content.splitlines(), 1):
            if COMPLETE_PATTERN.search(line):
                violations.append(f"{path}:{lineno}: {line.strip()}")

    if violations:
        print("FAIL: direct completion construction detected outside responder:")
        for v in violations:
            print(v)
        sys.exit(2)

scan_for_illegal_complete()
