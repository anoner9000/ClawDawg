#!/usr/bin/env python3
"""
Rembrandt Worker (executor-enforced contract)

Goal:
- Enforce "dashboard-wide style-only overhaul" as a *contract*, not prompt text.
- Fail-fast if Scribe design principles canon cannot be located.
- Block "complete" unless all gates pass.

This file is intentionally self-contained and conservative. It does NOT attempt
to implement the entire redesign itself; it enforces that the *execution* which
does the redesign cannot claim completion unless evidence and constraints match.

Integrate it by importing and calling `run_rembrandt_task(...)` from your agent runner.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


WORKSPACE = Path(os.environ.get("OPENCLAW_WORKSPACE", Path.cwd())).resolve()

# --- Scribe canon (adjust if your canon location differs) ---
SCRIBE_CANON_CANDIDATES = [
    WORKSPACE / "docs" / "design" / "corpus" / "principles_index.jsonl",
    WORKSPACE / "docs" / "design" / "corpus" / "PRINCIPLES_CITATIONS.md",
    WORKSPACE / "docs" / "design" / "CANON_INDEX.md",
]

# Required directive values (exact match after lowercasing)
CONTRACT_REQUIRED_DIRECTIVES = {
    "strict_overhaul_contract": "true",
    "mode": "implementation",
    "scope": "dashboard-wide",
    "type": "style-only",
}

ALLOWED_SUFFIXES = (".css", ".scss", ".html")
ALLOWED_PREFIX = "ui/dashboard/"


@dataclass
class ContractResolution:
    strict_requested: bool
    directives: dict[str, str]


@dataclass
class ScribeSourceResolution:
    ok: bool
    path: str
    searched: list[str]
    reason: str


def _run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return p.returncode, p.stdout or ""


def _parse_contract_directives(message: str) -> dict[str, str]:
    """
    Parse key=value lines at the top-level of the operator->Rembrandt message.
    Only reads keys we care about, to avoid accidental capture.
    """
    directives: dict[str, str] = {}
    msg = message or ""
    for key in CONTRACT_REQUIRED_DIRECTIVES:
        m = re.search(rf"(?im)^\s*{re.escape(key)}\s*=\s*([^\n\r]+)\s*$", msg)
        if m:
            directives[key] = m.group(1).strip().lower()
    return directives


def _resolve_contract(message: str) -> ContractResolution:
    directives = _parse_contract_directives(message)
    strict_requested = directives.get("strict_overhaul_contract", "") == "true"
    return ContractResolution(strict_requested=strict_requested, directives=directives)


def _resolve_scribe_principles_source() -> ScribeSourceResolution:
    searched = [str(p) for p in SCRIBE_CANON_CANDIDATES]

    pidx = SCRIBE_CANON_CANDIDATES[0]
    if pidx.exists() and pidx.stat().st_size > 0:
        # require at least one "accepted" entry if JSONL
        for line in pidx.read_text(encoding="utf-8", errors="replace").splitlines():
            t = line.strip()
            if not t:
                continue
            try:
                rec = json.loads(t)
            except json.JSONDecodeError:
                continue
            if rec.get("accepted") is False:
                continue
            return ScribeSourceResolution(True, str(pidx), searched, "principles_index_has_accepted_entries")

    citations = SCRIBE_CANON_CANDIDATES[1]
    if citations.exists() and citations.stat().st_size > 0:
        return ScribeSourceResolution(True, str(citations), searched, "fallback_citations_non_empty")

    canon_index = SCRIBE_CANON_CANDIDATES[2]
    if canon_index.exists() and canon_index.stat().st_size > 0:
        return ScribeSourceResolution(True, str(canon_index), searched, "fallback_canon_index_non_empty")

    return ScribeSourceResolution(False, "", searched, "missing_or_empty_scribe_principles_source")


def _dashboard_pages() -> list[str]:
    root = WORKSPACE / "ui" / "dashboard" / "templates"
    pages: list[str] = []
    if not root.exists():
        return pages
    for p in sorted(root.rglob("*.html")):
        rel = p.relative_to(WORKSPACE).as_posix()
        if "/partials/" in rel:
            continue
        if rel.endswith("/base.html"):
            continue
        pages.append(rel)
    return pages


def _is_style_only_change_set(changed_files: list[str]) -> bool:
    """
    Strictly enforce:
    - all files under ui/dashboard/
    - only .css .scss .html
    """
    for f in changed_files:
        f = (f or "").strip()
        if not f.startswith(ALLOWED_PREFIX):
            return False
        if not f.endswith(ALLOWED_SUFFIXES):
            return False
    return True


def _git_changed_files(base_ref: str = "HEAD") -> list[str]:
    """
    Get changed files using base...HEAD (triple-dot) plus working-tree/index deltas.
    This keeps verify robust whether task changes are committed or still in working tree.
    """
    files: set[str] = set()

    def collect(args: list[str]) -> None:
        code, out = _run(args)
        if code != 0:
            return
        for ln in out.splitlines():
            txt = ln.strip()
            if txt:
                files.add(txt)

    if base_ref:
        collect(["git", "diff", "--name-only", f"{base_ref}...HEAD"])
    collect(["git", "diff", "--name-only", "--cached"])
    collect(["git", "diff", "--name-only"])
    return sorted(files)


def _contract_directives_ok(directives: dict[str, str]) -> bool:
    return all(str(directives.get(k, "")).lower() == v for k, v in CONTRACT_REQUIRED_DIRECTIVES.items())


def _compile_css() -> tuple[bool, str]:
    """
    Optional build check; if pnpm script exists, run it.
    Non-fatal if dashboard package not installed, but in strict mode we treat failure as failure.
    """
    dash = WORKSPACE / "ui" / "dashboard"
    if not dash.exists():
        return False, "ui/dashboard missing"
    code, out = _run(["pnpm", "-C", str(dash), "run", "build:css"])
    return code == 0, (out.splitlines()[-1] if out else "ok" if code == 0 else "build failed")


def _write_report(report_path: Path, report: dict[str, Any]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


def run_rembrandt_task(
    task_id: str,
    message: str,
    report_dir: Path | None = None,
    diff_base: str = "HEAD",
    base_sha: str | None = None,
    require_css_build: bool = True,
    mode: str = "verify",
) -> dict[str, Any]:
    """
    Main entrypoint.
    This function assumes some other code performs the actual UI mutation.
    It enforces the contract gates and returns a machine-readable result payload.
    """

    report_dir = report_dir or (WORKSPACE / ".openclaw" / "runtime" / "reports" / "rembrandt")
    report_path = report_dir / f"{task_id}.json"

    contract = _resolve_contract(message)
    scribe = _resolve_scribe_principles_source()
    pages = _dashboard_pages()

    run_mode = (mode or "verify").strip().lower()
    if run_mode not in {"preflight", "verify"}:
        run_mode = "verify"

    diff_base_used = (base_sha or "").strip() or diff_base
    # In preflight mode, no mutation is expected yet.
    changed_files = [] if run_mode == "preflight" else _git_changed_files(diff_base_used)

    checks: dict[str, Any] = {
        "contract_directives_ok": _contract_directives_ok(contract.directives) if contract.strict_requested else True,
        "scribe_source_ok": scribe.ok if contract.strict_requested else True,
        "scribe_source_reason": scribe.reason,
        "scribe_source_path": scribe.path or "none",
        "scribe_source_searched": scribe.searched,
        "dashboard_pages_found": len(pages),
        "style_only_change_set_ok": (
            True
            if run_mode == "preflight"
            else (_is_style_only_change_set(changed_files) if contract.strict_requested else True)
        ),
        "run_mode": run_mode,
    }

    # Strict requirements for dashboard-wide tasks
    if contract.strict_requested:
        checks["mode_is_implementation"] = contract.directives.get("mode", "") == "implementation"
        checks["scope_is_dashboard_wide"] = contract.directives.get("scope", "") == "dashboard-wide"
        checks["type_is_style_only"] = contract.directives.get("type", "") == "style-only"

    build_ok, build_reason = (True, "skipped")
    if run_mode == "verify" and require_css_build and contract.strict_requested:
        build_ok, build_reason = _compile_css()
    checks["build_css_ok"] = build_ok if contract.strict_requested else True
    checks["build_css_reason"] = build_reason

    # Completion decision
    strict_ok = True
    if contract.strict_requested:
        strict_ok = bool(
            checks["contract_directives_ok"]
            and checks["scribe_source_ok"]
            and checks.get("mode_is_implementation", False)
            and checks.get("scope_is_dashboard_wide", False)
            and checks.get("type_is_style_only", False)
            and checks["style_only_change_set_ok"]
            and (checks["dashboard_pages_found"] > 0)
            and (True if run_mode == "preflight" else checks["build_css_ok"])
        )

    state = "complete" if strict_ok else "error"

    fail_reason = ""
    if state != "complete":
        # Priority-ordered reasons
        if contract.strict_requested and not checks["contract_directives_ok"]:
            fail_reason = "contract_directives_gate"
        elif contract.strict_requested and not checks["scribe_source_ok"]:
            fail_reason = f"scribe_source_gate:{checks['scribe_source_reason']}"
        elif contract.strict_requested and not checks.get("scope_is_dashboard_wide", True):
            fail_reason = "scope_gate:not_dashboard_wide"
        elif run_mode != "preflight" and contract.strict_requested and not checks["style_only_change_set_ok"]:
            fail_reason = "style_only_gate:changed_files_out_of_scope"
        elif contract.strict_requested and checks["dashboard_pages_found"] <= 0:
            fail_reason = "dashboard_pages_gate:none_found"
        elif run_mode != "preflight" and contract.strict_requested and not checks["build_css_ok"]:
            fail_reason = f"css_build_gate:{checks['build_css_reason']}"
        else:
            fail_reason = "unknown_gate"

    result: dict[str, Any] = {
        "task_id": task_id,
        "state": state,
        "fail_reason": fail_reason,
        "strict_contract_requested": contract.strict_requested,
        "run_mode": run_mode,
        "diff_base_used": diff_base_used,
        "received_directives": contract.directives,
        "changed_files": changed_files,
        "checks": checks,
        "report_path": str(report_path),
    }

    _write_report(report_path, result)
    return result


def main() -> int:
    """
    Minimal CLI for manual testing:
      python3 ops/scripts/agents/rembrandt_worker.py --task-id T1 --message-file /tmp/msg.txt
    """
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--task-id", required=True)
    ap.add_argument("--message-file", required=True)
    ap.add_argument("--diff-base", default="HEAD")
    ap.add_argument("--base-sha", default="")
    ap.add_argument("--mode", choices=["preflight", "verify"], default="verify")
    args = ap.parse_args()

    msg = Path(args.message_file).read_text(encoding="utf-8", errors="replace")
    res = run_rembrandt_task(
        task_id=args.task_id,
        message=msg,
        diff_base=args.diff_base,
        base_sha=(args.base_sha or "").strip() or None,
        mode=args.mode,
    )
    print(json.dumps(res, indent=2, sort_keys=True))
    return 0 if res.get("state") == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
