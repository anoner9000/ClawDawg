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
}
CONTRACT_ALLOWED_TYPES = {"style-only", "implementation"}

ALLOWED_SUFFIXES = (".css", ".scss", ".html")
ALLOWED_PREFIX = "ui/dashboard/"
THEME_SOURCE_FILES = {
    "ui/dashboard/src/styles.scss",
    "ui/dashboard/src/theme.scss",
    "ui/dashboard/src/tokens.scss",
    "ui/dashboard/templates/base.html",
}
COMPILED_CSS_CANDIDATES = [
    "ui/dashboard/static/app.bundle.css",
    "ui/dashboard/static/app.css",
]
COMPONENT_PATTERNS = {
    "navigation": [r"\bnav\b", r"\.site-header\b", r"\.site-nav\b", r"\[data-nav\]"],
    "buttons": [r"\bbutton\b", r"\.action-btn\b", r"\.theme-toggle\b", r"\.btn\b"],
    "cards_panels": [".panel-section", ".overview-card", ".agent-card", ".task-drawer", ".card"],
    "tables": [r"\btable\b", r"\.task-table\b", r"\.table\b"],
    "forms_inputs": [r"\binput\b", r"\bselect\b", r"\btextarea\b", r"\.field\b"],
    "badges_tags": [".badge", ".tag", ".pill", ".status"],
    "charts": [r"\.chart\b", r"\.sparkline\b", r"\bsvg\b"],
}


@dataclass
class ContractResolution:
    strict_requested: bool
    directives: dict[str, str]
    contract_type: str


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
    for key in [*CONTRACT_REQUIRED_DIRECTIVES.keys(), "type"]:
        m = re.search(rf"(?im)^\s*{re.escape(key)}\s*=\s*([^\n\r]+)\s*$", msg)
        if m:
            directives[key] = m.group(1).strip().lower()
    return directives


def _resolve_contract(message: str) -> ContractResolution:
    directives = _parse_contract_directives(message)
    strict_requested = directives.get("strict_overhaul_contract", "") == "true"
    contract_type = directives.get("type", "style-only").strip().lower() or "style-only"
    return ContractResolution(strict_requested=strict_requested, directives=directives, contract_type=contract_type)


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


def _is_dashboard_change_set(changed_files: list[str]) -> bool:
    for f in changed_files:
        txt = (f or "").strip()
        if not txt.startswith(ALLOWED_PREFIX):
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


def _normalize_changed_files_for_gates(changed_files: list[str]) -> list[str]:
    ignored = {
        p.strip()
        for p in (os.environ.get("OPENCLAW_REM_IGNORE_CHANGED", "") or "").split(";")
        if p.strip()
    }
    out: list[str] = []
    for f in changed_files:
        rel = (f or "").strip()
        if not rel:
            continue
        if rel in ignored and not rel.startswith(ALLOWED_PREFIX):
            continue
        if rel.endswith(".map"):
            continue
        out.append(rel)
    return out


def _theme_source_changed(changed_files: list[str]) -> bool:
    return any((f or "").strip() in THEME_SOURCE_FILES for f in changed_files)


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _read_compiled_css_current() -> tuple[str, str]:
    for rel in COMPILED_CSS_CANDIDATES:
        p = WORKSPACE / rel
        txt = _read_text(p)
        if txt:
            return rel, txt
    return "", ""


def _read_compiled_css_at_base(base_ref: str) -> tuple[str, str]:
    if not base_ref:
        return "", ""
    for rel in COMPILED_CSS_CANDIDATES:
        code, out = _run(["git", "show", f"{base_ref}:{rel}"])
        if code == 0 and out.strip():
            return rel, out
    return "", ""


def _component_coverage(css_text: str) -> dict[str, bool]:
    txt = css_text or ""
    out: dict[str, bool] = {}
    for target, pats in COMPONENT_PATTERNS.items():
        out[target] = any(bool(re.search(p, txt, flags=re.I)) for p in pats)
    return out


def _parse_rm_vars(css_text: str) -> dict[str, str]:
    pairs = re.findall(r"--(rm-[a-z0-9_-]+)\s*:\s*([^;]+);", css_text or "", flags=re.I)
    out: dict[str, str] = {}
    for k, v in pairs:
        out[k.strip().lower()] = v.strip()
    return out


def _parse_float_token(val: str) -> float | None:
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)", val or "")
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _contract_directives_ok(directives: dict[str, str]) -> bool:
    req_ok = all(str(directives.get(k, "")).lower() == v for k, v in CONTRACT_REQUIRED_DIRECTIVES.items())
    ctype = str(directives.get("type", "style-only")).strip().lower() or "style-only"
    return req_ok and ctype in CONTRACT_ALLOWED_TYPES


def _apply_minimal_dashboard_overhaul(task_id: str) -> tuple[bool, str, list[str]]:
    styles = WORKSPACE / "ui" / "dashboard" / "src" / "styles.scss"
    if not styles.exists():
        return False, f"missing style source: {styles}", []

    start = "/* REMBRANDT_AUTOGEN_START */"
    end = "/* REMBRANDT_AUTOGEN_END */"
    block = f"""{start}
:root {{
  --rm-font-scale: 1.24;
  --rm-panel-radius: 14px;
  --rm-day-bg: #f4f6f8;
  --rm-night-bg: #0f171f;
  --rm-day-accent: #0f766e;
  --rm-night-accent: #6ee7d8;
}}

html[data-theme="light"] body {{
  background: var(--rm-day-bg);
}}

html[data-theme="dark"] body {{
  background: var(--rm-night-bg);
}}

body {{
  font-size: calc(16px * var(--rm-font-scale));
}}

.panel-section,
.agent-card,
.overview-card,
.task-drawer {{
  border-radius: var(--rm-panel-radius);
}}

.action-btn,
button,
.badge {{
  border-color: var(--rm-day-accent);
}}

html[data-theme="dark"] .action-btn,
html[data-theme="dark"] button,
html[data-theme="dark"] .badge {{
  border-color: var(--rm-night-accent);
}}
{end}
"""
    try:
        current = styles.read_text(encoding="utf-8", errors="replace")
        pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), flags=re.S)
        if pattern.search(current):
            updated = pattern.sub(block, current)
        else:
            updated = current.rstrip() + "\n\n" + block + "\n"
        if updated == current:
            return False, "implementation_noop:no_source_diff", [styles.relative_to(WORKSPACE).as_posix()]
        styles.write_text(updated, encoding="utf-8")
        return True, f"applied managed style block for task {task_id}", [styles.relative_to(WORKSPACE).as_posix()]
    except OSError as e:
        return False, str(e), []


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


def _collect_failed_checks(run_mode: str, strict_requested: bool, checks: dict[str, Any]) -> list[str]:
    """
    Return all failing strict verify gates for debugging.
    Keep fail_reason ladder semantics separate.
    """
    if run_mode != "verify" or not strict_requested:
        return []

    failed: list[str] = []
    contract_type = str(checks.get("contract_type") or "style-only")

    if not checks.get("dashboard_change_set_ok", True):
        failed.append("dashboard_scope_gate:changed_files_out_of_scope")

    if contract_type == "style-only" and not checks.get("style_only_change_set_ok", True):
        failed.append("style_only_gate:changed_files_out_of_scope")

    if not checks.get("theme_source_changed_ok", True):
        failed.append("theme_source_gate:no_theme_source_changes")

    if contract_type == "style-only" and not checks.get("component_coverage_ok", True):
        miss = checks.get("component_coverage_missing") or []
        if isinstance(miss, list) and miss:
            failed.append(f"coverage_gate:missing_components:{','.join(str(x) for x in miss)}")
        else:
            failed.append("coverage_gate:missing_components")

    if contract_type == "style-only" and not checks.get("base_css_source_ok", True):
        failed.append("radical_delta_gate:missing_base_css")

    if contract_type == "style-only" and not checks.get("token_var_presence_ok", True):
        failed.append("radical_delta_gate:missing_token_vars")

    if contract_type == "style-only" and not checks.get("base_token_var_presence_ok", True):
        failed.append("radical_delta_gate:missing_base_token_vars")

    if contract_type == "style-only" and not checks.get("font_scale_delta_ok", True):
        failed.append("radical_delta_gate:font_scale")

    if contract_type == "style-only" and not checks.get("radii_changed_ok", True):
        failed.append("radical_delta_gate:radii")

    if contract_type == "style-only" and not checks.get("accent_changed_ok", True):
        failed.append("radical_delta_gate:accent")

    if contract_type == "style-only" and not checks.get("bg_changed_ok", True):
        failed.append("radical_delta_gate:backgrounds")

    if checks.get("dashboard_pages_found", 1) <= 0:
        failed.append("dashboard_pages_gate:none_found")

    if not checks.get("build_css_ok", True):
        failed.append(f"css_build_gate:{checks.get('build_css_reason', 'build_failed')}")

    return failed


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
    if run_mode not in {"preflight", "implementation", "verify"}:
        run_mode = "verify"

    diff_base_used = (base_sha or "").strip() or diff_base
    impl_ok = True
    impl_reason = "skipped"
    impl_files: list[str] = []
    if run_mode == "implementation":
        impl_ok, impl_reason, impl_files = _apply_minimal_dashboard_overhaul(task_id)
    # In preflight mode, no mutation is expected yet.
    changed_files_raw = [] if run_mode == "preflight" else _git_changed_files(diff_base_used)
    changed_files = _normalize_changed_files_for_gates(changed_files_raw)
    contract_type = contract.contract_type

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
        "dashboard_change_set_ok": (
            True
            if run_mode == "preflight"
            else (_is_dashboard_change_set(changed_files) if contract.strict_requested else True)
        ),
        "contract_type": contract_type,
        "run_mode": run_mode,
        "implementation_write_ok": impl_ok,
        "implementation_write_reason": impl_reason,
        "implementation_touched_files": impl_files,
    }
    enforce_style_only_gates = run_mode == "verify" and contract.strict_requested and contract_type == "style-only"
    if run_mode == "verify" and contract.strict_requested:
        checks["theme_source_changed_ok"] = _theme_source_changed(changed_files)
        if enforce_style_only_gates:
            css_rel, css_txt = _read_compiled_css_current()
            checks["compiled_css_source"] = css_rel or "none"
            coverage = _component_coverage(css_txt)
            required_targets = ["navigation", "buttons", "cards_panels", "tables", "forms_inputs", "badges_tags"]
            missing = [t for t in required_targets if not coverage.get(t, False)]
            checks["component_coverage"] = coverage
            checks["component_coverage_missing"] = missing
            checks["component_coverage_ok"] = len(missing) == 0

            base_rel, base_css = _read_compiled_css_at_base(diff_base_used)
            checks["base_css_source"] = base_rel or "none"
            checks["base_css_source_ok"] = bool(base_rel)
            curr_vars = _parse_rm_vars(css_txt)
            base_vars = _parse_rm_vars(base_css)
            required_var_keys = [
                "rm-font-scale",
                "rm-panel-radius",
                "rm-day-bg",
                "rm-night-bg",
                "rm-day-accent",
                "rm-night-accent",
            ]
            checks["token_var_presence_ok"] = all(k in curr_vars for k in required_var_keys)
            checks["base_token_var_presence_ok"] = all(k in base_vars for k in required_var_keys)
            fs_cur = _parse_float_token(curr_vars.get("rm-font-scale", ""))
            fs_base = _parse_float_token(base_vars.get("rm-font-scale", ""))
            checks["font_scale_delta_ok"] = bool(
                checks["base_token_var_presence_ok"]
                and fs_cur is not None and fs_base is not None and fs_cur >= (fs_base * 1.2)
            )
            rad_cur = _parse_float_token(curr_vars.get("rm-panel-radius", ""))
            rad_base = _parse_float_token(base_vars.get("rm-panel-radius", ""))
            checks["radii_changed_ok"] = bool(
                checks["base_token_var_presence_ok"]
                and rad_cur is not None and rad_base is not None and abs(rad_cur - rad_base) >= 2.0
            )
            checks["accent_changed_ok"] = bool(
                checks["base_token_var_presence_ok"]
                and
                curr_vars.get("rm-day-accent", "") != base_vars.get("rm-day-accent", "")
                and curr_vars.get("rm-night-accent", "") != base_vars.get("rm-night-accent", "")
            )
            checks["bg_changed_ok"] = bool(
                checks["base_token_var_presence_ok"]
                and
                curr_vars.get("rm-day-bg", "") != base_vars.get("rm-day-bg", "")
                and curr_vars.get("rm-night-bg", "") != base_vars.get("rm-night-bg", "")
            )
        else:
            checks["compiled_css_source"] = "not_required_for_type_implementation"
            checks["base_css_source"] = "not_required_for_type_implementation"
            checks["base_css_source_ok"] = True
            checks["component_coverage"] = {}
            checks["component_coverage_missing"] = []
            checks["component_coverage_ok"] = True
            checks["token_var_presence_ok"] = True
            checks["base_token_var_presence_ok"] = True
            checks["font_scale_delta_ok"] = True
            checks["radii_changed_ok"] = True
            checks["accent_changed_ok"] = True
            checks["bg_changed_ok"] = True
    else:
        checks["theme_source_changed_ok"] = True
        checks["compiled_css_source"] = "none"
        checks["base_css_source"] = "none"
        checks["base_css_source_ok"] = True
        checks["component_coverage"] = {}
        checks["component_coverage_missing"] = []
        checks["component_coverage_ok"] = True
        checks["token_var_presence_ok"] = True
        checks["base_token_var_presence_ok"] = True
        checks["font_scale_delta_ok"] = True
        checks["radii_changed_ok"] = True
        checks["accent_changed_ok"] = True
        checks["bg_changed_ok"] = True

    # Strict requirements for dashboard-wide tasks
    if contract.strict_requested:
        checks["mode_is_implementation"] = contract.directives.get("mode", "") == "implementation"
        checks["scope_is_dashboard_wide"] = contract.directives.get("scope", "") == "dashboard-wide"
        checks["type_is_valid"] = contract_type in CONTRACT_ALLOWED_TYPES

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
            and checks.get("type_is_valid", False)
            and checks["dashboard_change_set_ok"]
            and (True if contract_type != "style-only" else checks["style_only_change_set_ok"])
            and (checks["dashboard_pages_found"] > 0)
            and (True if run_mode in {"preflight", "implementation"} else checks["build_css_ok"])
            and (True if run_mode != "implementation" else checks["implementation_write_ok"])
            and (True if run_mode == "preflight" else checks["theme_source_changed_ok"])
            and (True if run_mode == "preflight" or contract_type != "style-only" else checks["component_coverage_ok"])
            and (True if run_mode == "preflight" or contract_type != "style-only" else checks["base_css_source_ok"])
            and (True if run_mode == "preflight" or contract_type != "style-only" else checks["token_var_presence_ok"])
            and (True if run_mode == "preflight" or contract_type != "style-only" else checks["font_scale_delta_ok"])
            and (True if run_mode == "preflight" or contract_type != "style-only" else checks["radii_changed_ok"])
            and (True if run_mode == "preflight" or contract_type != "style-only" else checks["accent_changed_ok"])
            and (True if run_mode == "preflight" or contract_type != "style-only" else checks["bg_changed_ok"])
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
        elif run_mode != "preflight" and contract.strict_requested and not checks["dashboard_change_set_ok"]:
            fail_reason = "dashboard_scope_gate:changed_files_out_of_scope"
        elif run_mode != "preflight" and contract.strict_requested and contract_type == "style-only" and not checks["style_only_change_set_ok"]:
            fail_reason = "style_only_gate:changed_files_out_of_scope"
        elif run_mode == "implementation" and contract.strict_requested and not checks["implementation_write_ok"]:
            fail_reason = f"implementation_gate:{checks.get('implementation_write_reason', 'write_failed')}"
        elif run_mode != "preflight" and contract.strict_requested and not checks["theme_source_changed_ok"]:
            fail_reason = "theme_source_gate:no_theme_source_changes"
        elif run_mode != "preflight" and contract.strict_requested and contract_type == "style-only" and not checks["component_coverage_ok"]:
            miss = ",".join(checks.get("component_coverage_missing", []))
            fail_reason = f"coverage_gate:missing_components:{miss}"
        elif run_mode != "preflight" and contract.strict_requested and contract_type == "style-only" and not checks["base_css_source_ok"]:
            fail_reason = "radical_delta_gate:missing_base_css"
        elif run_mode != "preflight" and contract.strict_requested and contract_type == "style-only" and not checks["token_var_presence_ok"]:
            fail_reason = "radical_delta_gate:missing_token_vars"
        elif run_mode != "preflight" and contract.strict_requested and contract_type == "style-only" and not checks["base_token_var_presence_ok"]:
            fail_reason = "radical_delta_gate:missing_base_token_vars"
        elif run_mode != "preflight" and contract.strict_requested and contract_type == "style-only" and not checks["font_scale_delta_ok"]:
            fail_reason = "radical_delta_gate:font_scale"
        elif run_mode != "preflight" and contract.strict_requested and contract_type == "style-only" and not checks["radii_changed_ok"]:
            fail_reason = "radical_delta_gate:radii"
        elif run_mode != "preflight" and contract.strict_requested and contract_type == "style-only" and not checks["accent_changed_ok"]:
            fail_reason = "radical_delta_gate:accent"
        elif run_mode != "preflight" and contract.strict_requested and contract_type == "style-only" and not checks["bg_changed_ok"]:
            fail_reason = "radical_delta_gate:backgrounds"
        elif contract.strict_requested and checks["dashboard_pages_found"] <= 0:
            fail_reason = "dashboard_pages_gate:none_found"
        elif run_mode != "preflight" and contract.strict_requested and not checks["build_css_ok"]:
            fail_reason = f"css_build_gate:{checks['build_css_reason']}"
        else:
            fail_reason = "unknown_gate"

    failed_checks = _collect_failed_checks(run_mode, contract.strict_requested, checks)

    result: dict[str, Any] = {
        "task_id": task_id,
        "state": state,
        "fail_reason": fail_reason,
        "failed_checks": failed_checks,
        "strict_contract_requested": contract.strict_requested,
        "run_mode": run_mode,
        "diff_base_used": diff_base_used,
        "received_directives": contract.directives,
        "changed_files": changed_files,
        "changed_files_raw": changed_files_raw,
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
    ap.add_argument("--mode", choices=["preflight", "implementation", "verify"], default="verify")
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
