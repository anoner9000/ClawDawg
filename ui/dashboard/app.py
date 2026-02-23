from __future__ import annotations

from datetime import datetime, timezone
import csv
import io
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any
import uuid
import urllib.error
import urllib.request

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .cli import run_query_status
from .config import ATTENTION_TYPES, POLL_AGENTS_SECS, POLL_TASKS_SECS, QUERY_STATUS_CLI, RUNTIME_BASE, STATUS_AGENTS_DIR, STATUS_TASKS_DIR, TEAM_BUS, WORKSPACE_BASE
from .parsers import parse_agent_output, parse_task_output, read_receipt

app = FastAPI(title="OpenClaw Control Plane UI")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

AGENT_ROLE_MAP = {
    "deiphobe": "Primary Operator",
    "custodian": "System Integrity",
    "scribe": "Documentation Flow",
    "minion": "Automation Runner",
    "peabody": "Policy Steward",
    "rembrandt": "Design Specialist",
}

AGENT_ICON_MAP = {
    "deiphobe": "brain-circuit",
    "custodian": "shield-check",
    "scribe": "notebook-pen",
    "minion": "bot",
    "peabody": "scale",
    "rembrandt": "palette",
}

AGENT_PERSONA_MAP = {
    "deiphobe": {"name": "shepherd", "relation": "Role Persona"},
}

AGENT_DESCRIPTION_MAP = {
    "deiphobe": "Deiphobe is the primary operator. It turns priorities into execution, coordinates other agents, and drives tasks from plan to completion.",
    "custodian": "Custodian is the system-integrity monitor. It validates facts, checks policy/safety boundaries, and reports operational drift or risk.",
    "scribe": "Scribe handles documentation flow. It captures decisions, status, and handoffs so context stays consistent across sessions.",
    "minion": "Minion is the automation runner. It executes scripted operations, routes repeatable jobs, and reports machine-level outcomes.",
    "peabody": "Peabody is the policy steward. It focuses on process compliance, review gates, and ensuring execution aligns with operating rules.",
    "rembrandt": "Rembrandt is the design specialist. It shapes visual systems, layout, typography, color, and motion to produce aesthetically strong, readable UI.",
}
TASK_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
SECRET_LIKE_RE = re.compile(r"\b(?:sk-[A-Za-z0-9_-]{10,}|[0-9]{6,12}:[A-Za-z0-9_-]{12,})\b")
FEED_TOKEN_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
FEED_SEVERITY_SET = {"info", "warn", "err"}
SCOPE_TOKEN_RE = re.compile(r"^[A-Za-z0-9_.:/-]{1,64}$")
UI_AUDIT_LOG = RUNTIME_BASE / "logs" / "ui_audit.jsonl"
TRUTHY = {"1", "true", "yes", "on"}


def _auto_reply_text(agent: str, message: str) -> str:
    msg = (message or "").strip()
    short = msg if len(msg) <= 180 else (msg[:177] + "...")
    templates = {
        "deiphobe": f"[auto] Deiphobe received your message: \"{short}\". I can route this into a task or orchestration event if you want.",
        "custodian": f"[auto] Custodian logged your message: \"{short}\". I can run a quick facts/compliance check path next.",
        "scribe": f"[auto] Scribe captured your note: \"{short}\". I can format this into a handoff-ready summary.",
        "minion": f"[auto] Minion queued your request: \"{short}\". I can convert this into an executable wrapper task.",
        "peabody": f"[auto] Peabody received: \"{short}\". I can map this against policy gates and approval flow.",
        "rembrandt": f"[auto] Rembrandt received your message: \"{short}\". I can turn this into a concrete UI design direction and styling pass.",
    }
    return templates.get(agent, f"[auto] {agent} received your message: \"{short}\".")


def _load_openai_api_key() -> str:
    env_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if env_key:
        return env_key
    key_file = Path.home() / ".openclaw" / "runtime" / "credentials" / "openai_api_key"
    if key_file.exists():
        try:
            return key_file.read_text(encoding="utf-8").strip()
        except OSError:
            return ""
    return ""


def _agent_context(agent: str, max_chars: int = 18_000) -> str:
    root = WORKSPACE_BASE / "agents" / agent
    parts: list[str] = []
    for name in ("SOUL.md", "RUNBOOK.md", "NOTES.md"):
        p = root / name
        if not p.exists():
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        if txt:
            parts.append(f"===== {name} =====\n{txt}\n")
    if agent == "rembrandt":
        canon_idx = WORKSPACE_BASE / "docs" / "design" / "CANON_INDEX.md"
        if canon_idx.exists():
            try:
                ci_txt = canon_idx.read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                ci_txt = ""
            if ci_txt:
                parts.append(f"===== CANON_INDEX.md =====\n{ci_txt}\n")

        design_kb = WORKSPACE_BASE / "docs" / "design" / "REMBRANDT_UI_KNOWLEDGE.md"
        if design_kb.exists():
            try:
                kb_txt = design_kb.read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                kb_txt = ""
            if kb_txt:
                parts.append(f"===== REMBRANDT_UI_KNOWLEDGE.md =====\n{kb_txt}\n")

        corpus_snapshot = WORKSPACE_BASE / "docs" / "design" / "corpus" / "LATEST_SNAPSHOT.md"
        if corpus_snapshot.exists():
            try:
                snap_txt = corpus_snapshot.read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                snap_txt = ""
            if snap_txt:
                parts.append(f"===== LATEST_SNAPSHOT.md =====\n{snap_txt}\n")

        principles_snapshot = WORKSPACE_BASE / "docs" / "design" / "corpus" / "PRINCIPLES_SNAPSHOT.md"
        if principles_snapshot.exists():
            try:
                ps_txt = principles_snapshot.read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                ps_txt = ""
            if ps_txt:
                parts.append(f"===== PRINCIPLES_SNAPSHOT.md =====\n{ps_txt}\n")

        principles_index = WORKSPACE_BASE / "docs" / "design" / "corpus" / "principles_index.jsonl"
        if principles_index.exists():
            refs: list[str] = []
            try:
                for line in principles_index.read_text(encoding="utf-8", errors="replace").splitlines():
                    txt = line.strip()
                    if not txt:
                        continue
                    try:
                        row = json.loads(txt)
                    except json.JSONDecodeError:
                        continue
                    if row.get("accepted") is False:
                        continue
                    refs.append(
                        f"- {row.get('id','source')} [{row.get('topic','')}]: {row.get('principles_path','')}"
                    )
                    if len(refs) >= 30:
                        break
            except OSError:
                refs = []
            if refs:
                parts.append("===== PRINCIPLES_INDEX =====\n" + "\n".join(refs) + "\n")
    combined = "\n".join(parts).strip()
    if not combined:
        return ""
    if len(combined) <= max_chars:
        return combined
    return combined[: max_chars - 64] + "\n\n[truncated for chat context]"


def _extract_response_text(obj: object) -> str:
    chunks: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            ot = node.get("output_text")
            if isinstance(ot, str) and ot.strip():
                chunks.append(ot.strip())
            t = node.get("text")
            if isinstance(t, str) and t.strip():
                chunks.append(t.strip())
            for v in node.values():
                walk(v)
            return
        if isinstance(node, list):
            for item in node:
                walk(item)

    walk(obj)
    if not chunks:
        return ""
    # Preserve first-seen order while de-duplicating exact repeats.
    seen: set[str] = set()
    out: list[str] = []
    for c in chunks:
        if c in seen:
            continue
        seen.add(c)
        out.append(c)
    return "\n\n".join(out).strip()


def _live_agent_reply(agent: str, message: str) -> tuple[bool, str, str]:
    """
    Return (ok, text, error_detail).
    """
    api_key = _load_openai_api_key()
    if not api_key:
        return False, "", "OPENAI_API_KEY missing"

    model = (os.environ.get("OPENCLAW_UI_CHAT_MODEL") or "gpt-5-mini").strip()
    context = _agent_context(agent)
    instructions = (
        f"You are the OpenClaw agent '{agent}'. "
        "Answer as that agent in a concise, action-oriented way. "
        "If unsure, state uncertainty and propose a concrete next step."
    )
    if context:
        instructions += "\n\nUse this agent context:\n" + context

    payload = {
        "model": model,
        "instructions": instructions,
        "input": message,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        err_code = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
            obj = json.loads(body)
            err_code = str((obj.get("error") or {}).get("code") or "").strip()
        except Exception:
            err_code = ""
        if err_code:
            return False, "", f"HTTP {e.code} ({err_code})"
        return False, "", f"HTTP {e.code}"
    except Exception as e:
        return False, "", str(e)

    try:
        body = json.loads(raw)
    except json.JSONDecodeError:
        return False, "", "non-JSON response from API"

    text = _extract_response_text(body)
    if not text:
        return False, "", "empty model output"
    return True, text, ""


def asset_version(name: str) -> int:
    p = Path(__file__).parent / "static" / name
    try:
        return int(p.stat().st_mtime)
    except OSError:
        return 0


templates.env.globals["asset_version"] = asset_version


def runtime_ready() -> bool:
    return STATUS_AGENTS_DIR.exists() or STATUS_TASKS_DIR.exists() or QUERY_STATUS_CLI.exists()


def discover_agents() -> list[str]:
    agents_root = WORKSPACE_BASE / "agents"
    if not agents_root.exists():
        return []
    names: list[str] = []
    for d in sorted(agents_root.iterdir()):
        if not d.is_dir():
            continue
        if not (d / "SOUL.md").is_file():
            continue
        if not (d / "RUNBOOK.md").is_file():
            continue
        names.append(d.name)
    return names


def discover_tasks() -> list[str]:
    if not STATUS_TASKS_DIR.exists():
        return []
    return sorted([p.name for p in STATUS_TASKS_DIR.iterdir() if p.is_dir()])


def _format_ts(ts: float | None) -> str:
    if ts is None:
        return "n/a"
    return datetime.fromtimestamp(ts).strftime("%m/%d/%Y")


def _format_date_value(value: object) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value)).strftime("%m/%d/%Y")
        except Exception:
            return str(value)

    txt = str(value).strip()
    if not txt:
        return txt

    # Epoch-like string
    if txt.isdigit():
        try:
            return datetime.fromtimestamp(float(txt)).strftime("%m/%d/%Y")
        except Exception:
            pass

    # ISO-like strings
    try:
        return datetime.fromisoformat(txt.replace("Z", "+00:00")).strftime("%m/%d/%Y")
    except Exception:
        pass

    # Common fallback layouts
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y"):
        try:
            return datetime.strptime(txt, fmt).strftime("%m/%d/%Y")
        except ValueError:
            continue
    return txt


def _task_time_bounds(task_id: str) -> tuple[float | None, float | None]:
    task_dir = STATUS_TASKS_DIR / task_id
    if not task_dir.exists():
        return None, None
    mtimes: list[float] = []
    for p in task_dir.rglob("*"):
        if p.is_file():
            try:
                mtimes.append(p.stat().st_mtime)
            except OSError:
                continue
    if not mtimes:
        try:
            ts = task_dir.stat().st_mtime
            return ts, ts
        except OSError:
            return None, None
    return min(mtimes), max(mtimes)


def _humanize_agent_update(line: str) -> dict[str, str]:
    """
    Convert a raw latest_by_agent line like:
      'peabody: in_process | Reviewing ops/scripts/telemetry'
    into a human-friendly structure for rendering.
    """
    txt = (line or "").strip()
    if not txt:
        return {"agent": "Unknown", "state": "unknown", "message": "No recent update."}

    m = re.match(r"^([^:]+):\s*([^|]+?)(?:\s*\|\s*(.*))?$", txt)
    if not m:
        return {"agent": "Agent", "state": "update", "message": txt}

    agent = m.group(1).strip()
    raw_state = m.group(2).strip().lower().replace(" ", "_")
    summary = (m.group(3) or "").strip()

    state_msg = {
        "complete": "marked this task complete.",
        "completed": "marked this task complete.",
        "done": "marked this task complete.",
        "in_process": "is actively working on this task.",
        "running": "is actively working on this task.",
        "queued": "is queued to run this task.",
        "pending": "is waiting to start this task.",
        "blocked": "is blocked on this task.",
        "error": "reported an error on this task.",
    }.get(raw_state, f"reported state '{raw_state}'.")

    if summary:
        message = f"{state_msg} {summary}"
    else:
        message = state_msg

    return {"agent": agent, "state": raw_state, "message": message}


def _is_valid_task_id(task_id: str) -> bool:
    return bool(TASK_ID_RE.fullmatch((task_id or "").strip()))


def _sanitize_text(value: object, max_len: int = 220) -> str:
    txt = str(value or "").strip()
    if not txt:
        return ""
    txt = SECRET_LIKE_RE.sub("[redacted]", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    if len(txt) > max_len:
        return txt[: max_len - 3] + "..."
    return txt


def _safe_token(value: object, fallback: str = "") -> str:
    txt = str(value or "").strip()
    if not txt:
        return fallback
    if FEED_TOKEN_RE.fullmatch(txt):
        return txt
    return fallback


def _event_severity(ev_type: str) -> str:
    t = (ev_type or "").upper()
    if t in {"ERROR", "FAILED", "BLOCKED"} or "ERROR" in t or "FAILED" in t:
        return "err"
    if t in {"WARN", "WARNING", "ESCALATE", "REVIEW_REQUEST"} or "WARN" in t:
        return "warn"
    return "info"


def _is_truthy_env(name: str, default: str = "0") -> bool:
    return (os.environ.get(name, default).strip().lower() in TRUTHY)


def _governed_actions_enabled() -> bool:
    return _is_truthy_env("OPENCLAW_UI_ENABLE_GOVERNED_ACTIONS", "0")


def _required_governed_scope() -> str:
    scope = (os.environ.get("OPENCLAW_UI_REQUIRED_SCOPE") or "ui:governed_actions").strip()
    if scope and SCOPE_TOKEN_RE.fullmatch(scope):
        return scope
    return "ui:governed_actions"


def _request_scopes(request: Request | None = None) -> list[str]:
    items: set[str] = set()
    env_scopes = str(os.environ.get("OPENCLAW_UI_SCOPES") or "")
    for raw in re.split(r"[\s,]+", env_scopes):
        tok = raw.strip()
        if tok and SCOPE_TOKEN_RE.fullmatch(tok):
            items.add(tok)

    if request is not None:
        header = str(request.headers.get("x-openclaw-scopes", "") or "")
        for raw in re.split(r"[\s,]+", header):
            tok = raw.strip()
            if tok and SCOPE_TOKEN_RE.fullmatch(tok):
                items.add(tok)
    return sorted(items)


def _governance_status(request: Request | None = None) -> dict[str, Any]:
    enabled = _governed_actions_enabled()
    required_scope = _required_governed_scope()
    scopes = _request_scopes(request)
    has_scope = required_scope in scopes
    return {
        "enabled": enabled,
        "required_scope": required_scope,
        "scopes": scopes,
        "has_required_scope": has_scope,
        "actions_allowed": bool(enabled and has_scope),
        "audit_sink": str(UI_AUDIT_LOG),
    }


def _write_ui_audit(
    event_type: str,
    *,
    result: str = "ok",
    reason: str = "",
    detail: str = "",
    action_id: str = "",
    run_id: str = "",
    request: Request | None = None,
) -> bool:
    et = _safe_token(event_type.upper(), fallback="")
    if not et:
        return False
    out = {
        "ts": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "type": et,
        "result": _safe_token(result.lower(), fallback="ok"),
        "reason": _safe_token(reason.lower(), fallback=""),
        "detail": _sanitize_text(detail, max_len=320),
        "action_id": _safe_token(action_id, fallback=""),
        "run_id": _safe_token(run_id, fallback=""),
        "path": request.url.path if request is not None else "",
        "scopes": _request_scopes(request),
    }
    if request is not None:
        out["client_ip"] = _sanitize_text(getattr(request.client, "host", "") or "", max_len=80)
        out["ua"] = _sanitize_text(request.headers.get("user-agent", ""), max_len=160)
    try:
        UI_AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with UI_AUDIT_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(out, ensure_ascii=False) + "\n")
    except OSError:
        return False
    return True


def _notify_custodian_governed_action(
    *,
    outcome: str,
    reason: str,
    detail: str,
    run_id: str = "",
    request: Request | None = None,
) -> bool:
    TEAM_BUS.parent.mkdir(parents=True, exist_ok=True)
    ev = {
        "schema_version": "team_bus.v1.1",
        "ts": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "type": "GOVERNED_ACTION_AUDIT",
        "actor": "ui_dashboard",
        "target_agent": "custodian",
        "task_id": None,
        "summary": f"close_placebo_tasks {outcome}: {reason}",
        "message": _sanitize_text(detail, max_len=420),
        "result": _safe_token(outcome, fallback="unknown"),
        "reason": _safe_token(reason, fallback=""),
        "run_id": _safe_token(run_id, fallback=""),
        "path": request.url.path if request is not None else "/actions/close-placebo-tasks",
        "dry_run": True,
    }
    if request is not None:
        ev["client_ip"] = _sanitize_text(getattr(request.client, "host", "") or "", max_len=80)
    try:
        with TEAM_BUS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
    except OSError:
        return False
    return True


def _read_recent_ui_audit_events(limit: int = 800) -> list[dict]:
    if not UI_AUDIT_LOG.exists():
        return []
    lines: list[str] = []
    try:
        with UI_AUDIT_LOG.open("r", encoding="utf-8") as f:
            for line in f:
                txt = line.strip()
                if txt:
                    lines.append(txt)
    except OSError:
        return []

    rows: list[dict] = []
    for txt in lines[-limit:]:
        try:
            ev = json.loads(txt)
        except json.JSONDecodeError:
            continue
        if isinstance(ev, dict):
            rows.append(ev)
    return rows


def _collect_governed_history(
    *,
    bus_events: list[dict],
    limit: int = 50,
) -> tuple[list[dict], list[str], list[str]]:
    ack_by_run: dict[str, dict[str, str]] = {}
    for ev in bus_events[-800:]:
        if str(ev.get("type", "")).strip().upper() != "CUSTODIAN_AUDIT_ACK":
            continue
        rid = _safe_token(ev.get("run_id", ""), fallback="")
        if not rid:
            continue
        ts_dt = _parse_iso_dt(ev.get("ts"))
        rec = {
            "ack_ts": _format_mmddyyyy_hhmm(ts_dt),
            "ack_actor": _safe_token(ev.get("actor", ""), fallback="custodian"),
        }
        # keep latest ack seen for this run id
        ack_by_run[rid] = rec

    governed_history: list[dict] = []
    reason_set: set[str] = set()
    result_set: set[str] = set()
    for ev in reversed(_read_recent_ui_audit_events(limit=1200)):
        ev_type = str(ev.get("type", "")).strip().upper()
        if ev_type not in {"UI_GOVERNED_ACTION_EXECUTED", "UI_GOVERNED_ACTION_DENIED"}:
            continue
        action_id = _safe_token(ev.get("action_id", ""), fallback="")
        if action_id != "close_placebo_tasks":
            continue
        ts_dt = _parse_iso_dt(ev.get("ts"))
        result = _safe_token(ev.get("result", ""), fallback="unknown")
        reason = _safe_token(ev.get("reason", ""), fallback="")
        run_id = _safe_token(ev.get("run_id", ""), fallback="")
        ack_rec = ack_by_run.get(run_id, {})
        result_set.add(result)
        if reason:
            reason_set.add(reason)
        governed_history.append(
            {
                "ts": _format_mmddyyyy_hhmm(ts_dt),
                "type": ev_type,
                "result": result,
                "reason": reason,
                "detail": _sanitize_text(ev.get("detail", ""), max_len=180),
                "run_id": run_id,
                "acked": bool(run_id and run_id in ack_by_run),
                "ack_ts": ack_rec.get("ack_ts", ""),
                "ack_actor": ack_rec.get("ack_actor", ""),
            }
        )
        if len(governed_history) >= max(1, min(limit, 200)):
            break

    return governed_history, sorted(reason_set), sorted(result_set)


def _validate_feed_filters(
    *,
    event_type: str | None,
    actor: str | None,
    severity: str | None,
    task_id: str | None,
    limit: int | None,
) -> tuple[dict | None, str | None]:
    out: dict[str, object] = {}

    et = (event_type or "").strip()
    if et:
        if not FEED_TOKEN_RE.fullmatch(et):
            return None, "Invalid event type filter."
        out["event_type"] = et.upper()

    ac = (actor or "").strip()
    if ac:
        if not FEED_TOKEN_RE.fullmatch(ac):
            return None, "Invalid actor filter."
        out["actor"] = ac

    sev = (severity or "").strip().lower()
    if sev:
        if sev not in FEED_SEVERITY_SET:
            return None, "Invalid severity filter."
        out["severity"] = sev

    tid = (task_id or "").strip()
    if tid:
        if not _is_valid_task_id(tid):
            return None, "Invalid task id filter."
        out["task_id"] = tid

    lim = 20 if limit is None else int(limit)
    lim = max(1, min(lim, 50))
    out["limit"] = lim
    return out, None


def _parse_iso_dt(value: object) -> datetime | None:
    txt = str(value or "").strip()
    if not txt:
        return None
    try:
        dt = datetime.fromisoformat(txt.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _format_mmddyyyy_hhmm(dt: datetime | None) -> str:
    if dt is None:
        return "n/a"
    return dt.astimezone().strftime("%m/%d/%Y %H:%M")


def _read_recent_bus_events(limit: int = 400) -> list[dict]:
    if not TEAM_BUS.exists():
        return []
    lines: list[str] = []
    try:
        with TEAM_BUS.open("r", encoding="utf-8") as f:
            for line in f:
                txt = line.strip()
                if txt:
                    lines.append(txt)
    except OSError:
        return []

    rows: list[dict] = []
    for txt in lines[-limit:]:
        try:
            ev = json.loads(txt)
        except json.JSONDecodeError:
            continue
        if not isinstance(ev, dict):
            continue
        rows.append(ev)
    return rows


def collect_home_intel(
    agent_cards: list[dict],
    task_rows: list[dict],
    feed_filters: dict | None = None,
    governance_status: dict[str, Any] | None = None,
) -> dict:
    now = datetime.now(timezone.utc)
    bus_events = _read_recent_bus_events()

    last_chat_req: dict[str, datetime] = {}
    last_chat_latency: dict[str, int] = {}
    for ev in bus_events:
        ev_type = str(ev.get("type", ""))
        actor = str(ev.get("actor", "")).strip()
        target = str(ev.get("target_agent", "")).strip()
        ev_dt = _parse_iso_dt(ev.get("ts"))
        if ev_dt is None:
            continue
        if ev_type == "CHAT_MESSAGE" and target:
            last_chat_req[target] = ev_dt
        elif ev_type == "CHAT_REPLY" and actor:
            req_dt = last_chat_req.get(actor)
            if req_dt:
                sec = int((ev_dt - req_dt).total_seconds())
                if sec >= 0:
                    last_chat_latency[actor] = sec

    sla_rows: list[dict] = []
    for c in agent_cards:
        agent = c.get("agent", "")
        snapshot = (c.get("parsed") and c["parsed"].snapshot) or {}
        ts_dt = _parse_iso_dt(snapshot.get("ts"))
        age_min: int | None = None
        if ts_dt is not None:
            age_min = int((now - ts_dt).total_seconds() // 60)
        stale = bool(age_min is None or age_min >= 15)
        latency = last_chat_latency.get(agent)
        sla_rows.append(
            {
                "agent": agent,
                "status": c.get("profile", {}).get("status", "unknown"),
                "last_seen": _format_mmddyyyy_hhmm(ts_dt),
                "age_min": age_min if age_min is not None else "n/a",
                "latency_s": latency if latency is not None else "n/a",
                "stale": stale,
            }
        )

    activity: list[dict] = []
    ff = feed_filters or {}
    filter_type = str(ff.get("event_type", "")).strip().upper()
    filter_actor = str(ff.get("actor", "")).strip()
    filter_severity = str(ff.get("severity", "")).strip().lower()
    filter_task_id = str(ff.get("task_id", "")).strip()
    max_items = int(ff.get("limit", 20))
    for ev in reversed(bus_events[-80:]):
        ts_dt = _parse_iso_dt(ev.get("ts"))
        ev_type = str(ev.get("type", "event")).strip() or "event"
        actor = str(ev.get("actor", "system")).strip() or "system"
        target = str(ev.get("target_agent", "")).strip()
        task_id = str(ev.get("task_id", "")).strip()
        severity = _event_severity(ev_type)
        if filter_type and ev_type.upper() != filter_type:
            continue
        if filter_actor and actor != filter_actor:
            continue
        if filter_severity and severity != filter_severity:
            continue
        if filter_task_id and task_id != filter_task_id:
            continue
        summary = _sanitize_text(ev.get("summary") or ev.get("message") or "", max_len=240)
        if not summary:
            summary = f"{actor} emitted {ev_type}"
        activity.append(
            {
                "ts": _format_mmddyyyy_hhmm(ts_dt),
                "type": ev_type,
                "actor": actor,
                "target": target,
                "task_id": task_id or "",
                "severity": severity,
                "summary": _sanitize_text(summary, max_len=240),
                "source": "team_bus",
            }
        )
    activity = activity[:max_items]

    alerts: list[dict] = []
    for row in sla_rows:
        if row["stale"]:
            alerts.append(
                {
                    "id": f"stale:{row['agent']}",
                    "level": "warn",
                    "title": _sanitize_text(f"{row['agent']} stale", max_len=80),
                    "detail": _sanitize_text(f"No fresh heartbeat within 15m. Last seen: {row['last_seen']}", max_len=180),
                    "source": "sla",
                    "rule_id": "stale_agent",
                }
            )
    for t in task_rows:
        state = str((t.get("parsed") and t["parsed"].state) or "").lower()
        if state in {"blocked", "error", "failed"}:
            alerts.append(
                {
                    "id": f"task:{t['task_id']}",
                    "level": "err",
                    "title": _sanitize_text(f"Task issue: {t['task_id']}", max_len=80),
                    "detail": _sanitize_text(f"Task state is {state}.", max_len=180),
                    "source": "task",
                    "rule_id": "task_blocked_or_error",
                }
            )
    # Deduplicate by alert id and order by severity then recency of creation order.
    uniq: dict[str, dict] = {}
    for a in alerts:
        uniq[a["id"]] = a
    sev_rank = {"err": 0, "warn": 1, "info": 2}
    alerts = sorted(uniq.values(), key=lambda a: sev_rank.get(str(a.get("level", "info")), 3))[:12]

    edge_map: dict[tuple[str, str], int] = {}
    for ev in bus_events[-200:]:
        actor = _safe_token(ev.get("actor", ""))
        target = _safe_token(ev.get("target_agent", ""))
        if not actor or not target or actor == target:
            continue
        key = (actor, target)
        edge_map[key] = min(edge_map.get(key, 0) + 1, 999)
    graph_edges = [
        {"source": src, "target": dst, "count": cnt}
        for (src, dst), cnt in sorted(edge_map.items(), key=lambda item: item[1], reverse=True)[:24]
    ]

    metrics = {
        "agents": len(agent_cards),
        "tasks": len(task_rows),
        "events": len(bus_events),
        "alerts": len(alerts),
    }

    governed_history, reason_options, result_options = _collect_governed_history(bus_events=bus_events, limit=50)

    custodian_audit_inbox: list[dict] = []
    for ev in reversed(bus_events[-240:]):
        ev_type = str(ev.get("type", "")).strip().upper()
        target = str(ev.get("target_agent", "")).strip().lower()
        if ev_type != "GOVERNED_ACTION_AUDIT" or target != "custodian":
            continue
        ts_dt = _parse_iso_dt(ev.get("ts"))
        custodian_audit_inbox.append(
            {
                "ts": _format_mmddyyyy_hhmm(ts_dt),
                "summary": _sanitize_text(ev.get("summary") or "governed action audit", max_len=160),
                "message": _sanitize_text(ev.get("message") or "", max_len=220),
                "result": _safe_token(ev.get("result", ""), fallback="unknown"),
                "reason": _safe_token(ev.get("reason", ""), fallback=""),
                "actor": _safe_token(ev.get("actor", ""), fallback="system"),
            }
        )
        if len(custodian_audit_inbox) >= 10:
            break

    return {
        "sla_rows": sla_rows,
        "activity": activity,
        "alerts": alerts,
        "graph_edges": graph_edges,
        "metrics": metrics,
        "governed_history": governed_history,
        "governed_reason_options": reason_options,
        "governed_result_options": result_options,
        "custodian_audit_inbox": custodian_audit_inbox,
        "governance": governance_status or _governance_status(None),
    }


def discover_receipts(task_id: str | None = None) -> list[dict]:
    base = STATUS_TASKS_DIR
    if not base.exists():
        return []
    pattern = f"{task_id}/*-report.md" if task_id else "*/*-report.md"
    receipts = [read_receipt(p) for p in base.glob(pattern)]
    return sorted(receipts, key=lambda r: r["mtime"], reverse=True)


def read_chat_messages(agent: str, limit: int = 200) -> list[dict]:
    if not agent or not TEAM_BUS.exists():
        return []
    rows: list[dict] = []
    try:
        with TEAM_BUS.open("r", encoding="utf-8") as f:
            for line in f:
                txt = line.strip()
                if not txt:
                    continue
                try:
                    ev = json.loads(txt)
                except json.JSONDecodeError:
                    continue
                ev_type = str(ev.get("type", ""))
                if ev_type not in {"CHAT_MESSAGE", "CHAT_REPLY"}:
                    continue
                target = str(ev.get("target_agent", "")).strip()
                actor = str(ev.get("actor", "")).strip()
                if target != agent and actor != agent:
                    continue
                body = str(ev.get("message") or ev.get("summary") or "").strip()
                if not body:
                    continue
                rows.append(
                    {
                        "ts": _format_date_value(ev.get("ts", "")),
                        "actor": actor or "unknown",
                        "target_agent": target or "",
                        "body": _sanitize_text(body, max_len=600),
                        "mine": actor != agent,
                    }
                )
    except OSError:
        return []
    return rows[-limit:]


def post_chat_message(agent: str, message: str, sender: str = "operator") -> None:
    TEAM_BUS.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    ev = {
        "schema_version": "team_bus.v1.1",
        "ts": now,
        "type": "CHAT_MESSAGE",
        "task_id": None,
        "actor": sender,
        "target_agent": agent,
        "summary": message,
        "message": message,
        "channel": "ui_chat",
        "dry_run": True,
    }
    with TEAM_BUS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(ev, ensure_ascii=False) + "\n")


def post_chat_reply(agent: str, message: str) -> None:
    TEAM_BUS.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    reply = {
        "schema_version": "team_bus.v1.1",
        "ts": now,
        "type": "CHAT_REPLY",
        "task_id": None,
        "actor": agent,
        "target_agent": "operator",
        "summary": _auto_reply_text(agent, message),
        "message": _auto_reply_text(agent, message),
        "channel": "ui_chat",
        "dry_run": True,
    }
    with TEAM_BUS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(reply, ensure_ascii=False) + "\n")


def post_chat_reply_live(agent: str, message: str, model: str | None = None) -> None:
    TEAM_BUS.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    model_name = model or (os.environ.get("OPENCLAW_UI_CHAT_MODEL") or "gpt-5-mini")
    reply = {
        "schema_version": "team_bus.v1.1",
        "ts": now,
        "type": "CHAT_REPLY",
        "task_id": None,
        "actor": agent,
        "target_agent": "operator",
        "summary": message,
        "message": message,
        "channel": "ui_chat",
        "model": model_name,
        "dry_run": False,
    }
    with TEAM_BUS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(reply, ensure_ascii=False) + "\n")


def post_chat_reply_system(agent: str, message: str) -> None:
    TEAM_BUS.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    reply = {
        "schema_version": "team_bus.v1.1",
        "ts": now,
        "type": "CHAT_REPLY",
        "task_id": None,
        "actor": agent,
        "target_agent": "operator",
        "summary": message,
        "message": message,
        "channel": "ui_chat",
        "dry_run": True,
    }
    with TEAM_BUS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(reply, ensure_ascii=False) + "\n")


def agent_profile_for(agent: str) -> dict:
    return {
        "role": AGENT_ROLE_MAP.get(agent, "General Agent"),
        "icon": AGENT_ICON_MAP.get(agent, "sparkles"),
        "persona": AGENT_PERSONA_MAP.get(agent),
        "description": AGENT_DESCRIPTION_MAP.get(
            agent,
            "This agent contributes to the OpenClaw workflow and reports status through the control plane.",
        ),
    }


def collect_agent_views() -> list[dict]:
    cards = []
    for agent in discover_agents():
        res = run_query_status("--agent", agent)
        parsed = parse_agent_output(agent, res.stdout)
        snapshot = parsed.snapshot or {}
        status = str(snapshot.get("status", "")).lower()
        typ = str(snapshot.get("type", ""))
        profile_base = agent_profile_for(agent)
        flagged = status in {"error", "blocked"} or typ in ATTENTION_TYPES
        cards.append(
            {
                "agent": agent,
                "result": res,
                "parsed": parsed,
                "flagged": flagged,
                "profile": {
                    "role": profile_base["role"],
                    "icon": profile_base["icon"],
                    "status": status or "unknown",
                    "last_update": _format_date_value(snapshot.get("ts", "n/a")),
                    "summary": snapshot.get("summary", "No summary provided."),
                    "persona": profile_base.get("persona"),
                },
            }
        )
    return cards


def collect_task_views() -> list[dict]:
    rows = []
    for task_id in discover_tasks():
        res = run_query_status("--task-id", task_id)
        parsed = parse_task_output(task_id, res.stdout)
        start_ts, end_ts = _task_time_bounds(task_id)
        state = (parsed.state or "").strip().lower()
        is_closed = state in {"complete", "completed", "done", "ok"}
        rows.append(
            {
                "task_id": task_id,
                "result": res,
                "parsed": parsed,
                "latest_by_agent_human": [_humanize_agent_update(item) for item in parsed.latest_by_agent],
                "task_start": _format_ts(start_ts),
                "task_end": _format_ts(end_ts) if is_closed else "—",
                "task_start_ts": start_ts,
                "task_end_ts": end_ts,
            }
        )
    return rows


def summarize_dashboard(agent_cards: list[dict], task_rows: list[dict]) -> dict:
    agent_total = len(agent_cards)
    agent_attention = sum(1 for c in agent_cards if c.get("flagged"))
    agent_healthy = max(agent_total - agent_attention, 0)
    agent_health_pct = round((agent_healthy * 100) / agent_total) if agent_total else 0

    done_states = {"complete", "completed", "done", "ok"}
    active_states = {"running", "in_process", "in-progress", "pending", "queued"}
    blocked_states = {"blocked", "error", "failed"}

    task_total = len(task_rows)
    task_done = 0
    task_active = 0
    task_blocked = 0
    task_other = 0

    for row in task_rows:
        state = str(row["parsed"].state or "").strip().lower().replace(" ", "_")
        if state in done_states:
            task_done += 1
        elif state in active_states:
            task_active += 1
        elif state in blocked_states:
            task_blocked += 1
        else:
            task_other += 1

    task_done_pct = round((task_done * 100) / task_total) if task_total else 0

    def _pct(val: int) -> int:
        return round((val * 100) / task_total) if task_total else 0

    state_bars = [
        {"label": "Completed", "value": task_done, "pct": _pct(task_done), "tone": "ok"},
        {"label": "In Progress", "value": task_active, "pct": _pct(task_active), "tone": "warn"},
        {"label": "Blocked/Error", "value": task_blocked, "pct": _pct(task_blocked), "tone": "err"},
        {"label": "Other", "value": task_other, "pct": _pct(task_other), "tone": "muted"},
    ]

    # Build a simple 24h activity trend from task lifecycle timestamps.
    bins = 8
    step_s = 3 * 60 * 60
    now_s = datetime.now().timestamp()
    start_s = now_s - (bins * step_s)
    trend_values = [0 for _ in range(bins)]
    trend_labels = []
    for i in range(bins):
        bucket_ts = start_s + ((i + 1) * step_s)
        trend_labels.append(datetime.fromtimestamp(bucket_ts).strftime("%H:%M"))

    for row in task_rows:
        ref_ts = row.get("task_end_ts") or row.get("task_start_ts")
        if ref_ts is None or ref_ts < start_s:
            continue
        idx = int((ref_ts - start_s) // step_s)
        idx = max(0, min(bins - 1, idx))
        trend_values[idx] += 1

    trend_max = max(trend_values) if trend_values else 0
    trend_scale = trend_max if trend_max > 0 else 1
    trend_points = []
    for i, label in enumerate(trend_labels):
        value = trend_values[i]
        trend_points.append(
            {
                "label": label,
                "value": value,
                "pct": round((value * 100) / trend_scale),
            }
        )

    return {
        "agent_total": agent_total,
        "agent_attention": agent_attention,
        "agent_healthy": agent_healthy,
        "agent_health_pct": agent_health_pct,
        "task_total": task_total,
        "task_done": task_done,
        "task_active": task_active,
        "task_blocked": task_blocked,
        "task_other": task_other,
        "task_done_pct": task_done_pct,
        "state_bars": state_bars,
        "trend_labels": trend_labels,
        "trend_values": trend_values,
        "trend_points": trend_points,
    }


def close_placebo_tasks() -> dict:
    responder = QUERY_STATUS_CLI.parent / "agent_status_responder.py"
    if not responder.exists():
        return {"closed": 0, "tasks": 0, "errors": [f"Missing responder script: {responder}"]}

    closed = 0
    tasks_seen = 0
    errors: list[str] = []

    for task_dir in sorted(STATUS_TASKS_DIR.glob("placebo-*")):
        if not task_dir.is_dir():
            continue
        tasks_seen += 1
        for p in sorted(task_dir.glob("*.jsonl")):
            agent = p.stem
            if agent == "latest":
                continue
            cmd = [
                "python3",
                str(responder),
                "update",
                "--agent",
                agent,
                "--task-id",
                task_dir.name,
                "--state",
                "complete",
                "--summary",
                "Placebo task closed from dashboard action",
            ]
            proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
            if proc.returncode == 0:
                closed += 1
            else:
                err = (proc.stderr or proc.stdout or "unknown error").strip().splitlines()[-1]
                errors.append(f"{task_dir.name}/{agent}: {err}")

    return {"closed": closed, "tasks": tasks_seen, "errors": errors}


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    cards = collect_agent_views()
    all_tasks = collect_task_views()
    tasks = all_tasks[:15]
    governance = _governance_status(request)
    home_intel = collect_home_intel(cards, all_tasks, governance_status=governance)
    chat_agents = discover_agents()
    requested_chat_agent = (request.query_params.get("chat_agent") or "").strip()
    selected_chat_agent = (
        requested_chat_agent if requested_chat_agent in chat_agents else (chat_agents[0] if chat_agents else "")
    )
    chat_messages = read_chat_messages(selected_chat_agent)
    attention = any(c["flagged"] for c in cards)
    summary = summarize_dashboard(cards, all_tasks)
    enable_governed_actions = governance["actions_allowed"]
    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "runtime_ready": runtime_ready(),
            "attention": attention,
            "agent_cards": cards,
            "tasks": tasks,
            "summary": summary,
            "home_intel": home_intel,
            "chat_agents": chat_agents,
            "selected_chat_agent": selected_chat_agent,
            "chat_messages": chat_messages,
            "poll_agents_s": POLL_AGENTS_SECS,
            "poll_tasks_s": POLL_TASKS_SECS,
            "enable_governed_actions": enable_governed_actions,
            "governance": governance,
        },
    )


@app.get("/agents", response_class=HTMLResponse)
def agents(request: Request):
    return templates.TemplateResponse(
        "agents.html",
        {"request": request, "agent_cards": collect_agent_views(), "poll_agents_s": POLL_AGENTS_SECS},
    )


@app.get("/agents/{agent}", response_class=HTMLResponse)
def agent_detail(request: Request, agent: str):
    res = run_query_status("--agent", agent)
    parsed = parse_agent_output(agent, res.stdout)
    snapshot = parsed.snapshot or {}
    profile = agent_profile_for(agent)
    status = str(snapshot.get("status", "unknown")).lower()
    state_class = status.replace(" ", "-")
    info_keys = ["status", "type", "task_id", "ts", "summary", "dry_run", "persisted_ts"]
    info_rows = []
    for k in info_keys:
        if k in snapshot:
            val = snapshot.get(k)
            if k in {"ts", "persisted_ts"}:
                val = _format_date_value(val)
            info_rows.append({"key": k, "value": val})
    return templates.TemplateResponse(
        "agent_detail.html",
        {
            "request": request,
            "agent": agent,
            "result": res,
            "parsed": parsed,
            "profile": profile,
            "agent_description": profile["description"],
            "state_class": state_class,
            "info_rows": info_rows,
        },
    )


@app.get("/tasks", response_class=HTMLResponse)
def tasks(request: Request):
    return templates.TemplateResponse("tasks.html", {"request": request, "tasks": collect_task_views(), "poll_tasks_s": POLL_TASKS_SECS})


@app.get("/tasks/{task_id}", response_class=HTMLResponse)
def task_detail(request: Request, task_id: str):
    res = run_query_status("--task-id", task_id)
    parsed = parse_task_output(task_id, res.stdout)
    latest_human = [_humanize_agent_update(item) for item in parsed.latest_by_agent]
    receipts = discover_receipts(task_id)
    return templates.TemplateResponse(
        "task_detail.html",
        {
            "request": request,
            "task_id": task_id,
            "result": res,
            "parsed": parsed,
            "latest_human": latest_human,
            "receipts": receipts,
        },
    )


@app.get("/receipts", response_class=HTMLResponse)
def receipts(request: Request):
    return templates.TemplateResponse(
        "receipts.html",
        {"request": request, "receipts": discover_receipts(), "poll_tasks_s": POLL_TASKS_SECS},
    )


@app.get("/chat", response_class=HTMLResponse)
def chat(request: Request, agent: str | None = None):
    agents = discover_agents()
    selected = agent if agent in agents else (agents[0] if agents else "")
    messages = read_chat_messages(selected)
    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request,
            "agents": agents,
            "selected_agent": selected,
            "messages": messages,
            "poll_agents_s": POLL_AGENTS_SECS,
        },
    )


@app.get("/partials/banner", response_class=HTMLResponse)
def banner_partial(request: Request):
    attention = any(c["flagged"] for c in collect_agent_views())
    return templates.TemplateResponse("partials/banner.html", {"request": request, "attention": attention, "runtime_ready": runtime_ready()})


@app.get("/partials/agent-cards", response_class=HTMLResponse)
def agent_cards_partial(request: Request):
    return templates.TemplateResponse("partials/agent_cards.html", {"request": request, "agent_cards": collect_agent_views()})


@app.get("/partials/task-table", response_class=HTMLResponse)
def task_table_partial(request: Request):
    return templates.TemplateResponse("partials/task_table.html", {"request": request, "tasks": collect_task_views()})


@app.get("/partials/receipts-list", response_class=HTMLResponse)
def receipts_list_partial(request: Request):
    return templates.TemplateResponse("partials/receipts_list.html", {"request": request, "receipts": discover_receipts()})


@app.get("/partials/overview-gauges", response_class=HTMLResponse)
def overview_gauges_partial(request: Request):
    cards = collect_agent_views()
    tasks = collect_task_views()
    summary = summarize_dashboard(cards, tasks)
    return templates.TemplateResponse("partials/overview_gauges.html", {"request": request, "summary": summary})


@app.get("/partials/home-intel", response_class=HTMLResponse)
def home_intel_partial(
    request: Request,
    event_type: str | None = None,
    actor: str | None = None,
    severity: str | None = None,
    task_id: str | None = None,
    limit: int | None = None,
):
    filters, err = _validate_feed_filters(
        event_type=event_type,
        actor=actor,
        severity=severity,
        task_id=task_id,
        limit=limit,
    )
    if err:
        return HTMLResponse(f"<div class='warn'>{err}</div>", status_code=400)
    cards = collect_agent_views()
    tasks = collect_task_views()
    intel = collect_home_intel(cards, tasks, feed_filters=filters, governance_status=_governance_status(request))
    return templates.TemplateResponse("partials/home_intel.html", {"request": request, "intel": intel})


@app.get("/api/home-intel/feed")
def home_intel_feed_api(
    event_type: str | None = None,
    actor: str | None = None,
    severity: str | None = None,
    task_id: str | None = None,
    limit: int | None = None,
):
    filters, err = _validate_feed_filters(
        event_type=event_type,
        actor=actor,
        severity=severity,
        task_id=task_id,
        limit=limit,
    )
    if err:
        return {"ok": False, "error": err}
    cards = collect_agent_views()
    tasks = collect_task_views()
    intel = collect_home_intel(cards, tasks, feed_filters=filters)
    feed_rows = []
    for row in intel["activity"]:
        feed_rows.append(
            {
                "ts": row.get("ts", "n/a"),
                "type": row.get("type", "event"),
                "actor": row.get("actor", "system"),
                "target": row.get("target", ""),
                "task_id": row.get("task_id", ""),
                "severity": row.get("severity", "info"),
                "summary": row.get("summary", ""),
                "source": row.get("source", "team_bus"),
            }
        )
    return {"ok": True, "count": len(feed_rows), "filters": filters, "items": feed_rows}


@app.get("/api/audit/governed-actions.csv", response_class=PlainTextResponse)
def governed_actions_csv(
    result: str | None = None,
    reason: str | None = None,
    limit: int | None = None,
):
    rr = (result or "").strip()
    rk = (reason or "").strip()
    if rr and rr != _safe_token(rr, fallback=""):
        return PlainTextResponse("invalid result filter\n", status_code=400)
    if rk and rk != _safe_token(rk, fallback=""):
        return PlainTextResponse("invalid reason filter\n", status_code=400)
    lim = max(1, min(int(limit or 200), 500))

    bus_events = _read_recent_bus_events(limit=1200)
    history, _, _ = _collect_governed_history(bus_events=bus_events, limit=lim)
    if rr:
        history = [h for h in history if h.get("result", "") == rr]
    if rk:
        history = [h for h in history if h.get("reason", "") == rk]

    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["ts", "type", "result", "reason", "run_id", "detail", "acked", "ack_ts", "ack_actor"])
    for row in history:
        w.writerow(
            [
                row.get("ts", ""),
                row.get("type", ""),
                row.get("result", ""),
                row.get("reason", ""),
                row.get("run_id", ""),
                row.get("detail", ""),
                "1" if row.get("acked") else "0",
                row.get("ack_ts", ""),
                row.get("ack_actor", ""),
            ]
        )
    return PlainTextResponse(out.getvalue(), media_type="text/csv")


@app.get("/partials/chat-thread", response_class=HTMLResponse)
def chat_thread_partial(request: Request, agent: str):
    return templates.TemplateResponse(
        "partials/chat_thread.html",
        {"request": request, "selected_agent": agent, "messages": read_chat_messages(agent)},
    )


@app.get("/partials/task-drawer", response_class=HTMLResponse)
def task_drawer_partial(request: Request, task_id: str):
    task_id = (task_id or "").strip()
    if not _is_valid_task_id(task_id):
        return HTMLResponse("<div class='warn'>Invalid task id.</div>", status_code=400)
    task_dir = STATUS_TASKS_DIR / task_id
    if not task_dir.exists() or not task_dir.is_dir():
        return HTMLResponse("<div class='warn'>Task not found.</div>", status_code=404)

    res = run_query_status("--task-id", task_id)
    parsed = parse_task_output(task_id, res.stdout)
    latest_human = []
    for item in parsed.latest_by_agent[:6]:
        row = _humanize_agent_update(item)
        msg = str(row.get("message", ""))
        if len(msg) > 220:
            row["message"] = msg[:217] + "..."
        latest_human.append(row)

    drawer = {
        "state": parsed.state or "unknown",
        "bus_events": parsed.bus_events if parsed.bus_events is not None else "n/a",
        "timed_out": bool(res.timed_out),
        "truncated": bool(res.truncated),
        "cli_error": bool((not res.ok) and (not res.timed_out)),
    }
    return templates.TemplateResponse(
        "partials/task_drawer.html",
        {
            "request": request,
            "task_id": task_id,
            "drawer": drawer,
            "latest_human": latest_human,
        },
    )


@app.post("/actions/close-placebo-tasks", response_class=HTMLResponse)
def close_placebo_tasks_action(request: Request):
    executed_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id = f"gact-{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    gov = _governance_status(request)
    if not gov["enabled"]:
        _write_ui_audit(
            "UI_GOVERNED_ACTION_DENIED",
            result="denied",
            reason="policy_disabled",
            action_id="close_placebo_tasks",
            run_id=run_id,
            request=request,
        )
        _notify_custodian_governed_action(
            outcome="denied",
            reason="policy_disabled",
            detail="close_placebo_tasks denied because OPENCLAW_UI_ENABLE_GOVERNED_ACTIONS is disabled.",
            run_id=run_id,
            request=request,
        )
        return HTMLResponse(
            (
                "<div class='warn'>Close Placebo is disabled by governance policy.</div>"
                f"<div class='muted'>Audit: UI_GOVERNED_ACTION_DENIED at {executed_at}</div>"
                f"<div class='muted'>Run ID: {run_id}</div>"
            ),
            status_code=403,
        )
    if not gov["has_required_scope"]:
        _write_ui_audit(
            "UI_GOVERNED_ACTION_DENIED",
            result="denied",
            reason="missing_scope",
            detail=f"required_scope={gov['required_scope']}",
            action_id="close_placebo_tasks",
            run_id=run_id,
            request=request,
        )
        _notify_custodian_governed_action(
            outcome="denied",
            reason="missing_scope",
            detail=f"close_placebo_tasks denied. required_scope={gov['required_scope']} provided_scopes={','.join(gov['scopes']) or 'none'}",
            run_id=run_id,
            request=request,
        )
        return HTMLResponse(
            (
                f"<div class='warn'>Missing scope: {gov['required_scope']}</div>"
                f"<div class='muted'>Audit: UI_GOVERNED_ACTION_DENIED at {executed_at}</div>"
                f"<div class='muted'>Run ID: {run_id}</div>"
            ),
            status_code=403,
        )

    result = close_placebo_tasks()
    if result["errors"]:
        _write_ui_audit(
            "UI_GOVERNED_ACTION_EXECUTED",
            result="err",
            reason="partial_failure",
            detail=f"closed={result['closed']} tasks={result['tasks']} errors={len(result['errors'])}",
            action_id="close_placebo_tasks",
            run_id=run_id,
            request=request,
        )
        _notify_custodian_governed_action(
            outcome="executed_err",
            reason="partial_failure",
            detail=f"close_placebo_tasks executed with partial failures. closed={result['closed']} tasks={result['tasks']} errors={len(result['errors'])}",
            run_id=run_id,
            request=request,
        )
        msg = (
            f"<div class='warn'>Closed {result['closed']} agent lanes across {result['tasks']} placebo tasks. "
            f"Some updates failed.</div>"
        )
        details = "".join(f"<li>{e}</li>" for e in result["errors"][:8])
        audit = (
            f"<div class='muted'>Audit: UI_GOVERNED_ACTION_EXECUTED at {executed_at}</div>"
            f"<div class='muted'>Run ID: {run_id}</div>"
        )
        return HTMLResponse(msg + audit + f"<ul class='action-errors'>{details}</ul>")
    _write_ui_audit(
        "UI_GOVERNED_ACTION_EXECUTED",
        result="ok",
        detail=f"closed={result['closed']} tasks={result['tasks']}",
        action_id="close_placebo_tasks",
        run_id=run_id,
        request=request,
    )
    _notify_custodian_governed_action(
        outcome="executed_ok",
        reason="success",
        detail=f"close_placebo_tasks executed successfully. closed={result['closed']} tasks={result['tasks']}",
        run_id=run_id,
        request=request,
    )
    return HTMLResponse(
        (
            f"<div class='ok'>Closed {result['closed']} agent lanes across {result['tasks']} placebo tasks.</div>"
            f"<div class='muted'>Audit: UI_GOVERNED_ACTION_EXECUTED at {executed_at}</div>"
            f"<div class='muted'>Run ID: {run_id}</div>"
        )
    )


@app.post("/actions/ui-audit")
async def ui_audit_action(request: Request):
    try:
        payload = await request.json()
    except Exception:
        return {"ok": False, "error": "invalid_json"}
    if not isinstance(payload, dict):
        return {"ok": False, "error": "invalid_payload"}

    event_type = _safe_token(str(payload.get("event_type", "")).upper(), fallback="")
    if not event_type:
        return {"ok": False, "error": "invalid_event_type"}

    ok = _write_ui_audit(
        event_type,
        result=_safe_token(payload.get("result", "ok"), fallback="ok"),
        reason=_safe_token(payload.get("reason", ""), fallback=""),
        detail=str(payload.get("detail", "")),
        action_id=_safe_token(payload.get("action_id", ""), fallback=""),
        run_id=_safe_token(payload.get("run_id", ""), fallback=""),
        request=request,
    )
    return {"ok": ok}


@app.post("/actions/custodian-ack", response_class=HTMLResponse)
def custodian_ack_action(request: Request, run_id: str = Form(...), note: str = Form("Acked from dashboard")):
    rid = _safe_token((run_id or "").strip(), fallback="")
    if not rid:
        return HTMLResponse("<span class='warn'>Invalid run id.</span>", status_code=400)

    TEAM_BUS.parent.mkdir(parents=True, exist_ok=True)
    ack_ev = {
        "schema_version": "team_bus.v1.1",
        "ts": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "type": "CUSTODIAN_AUDIT_ACK",
        "actor": "custodian",
        "target_agent": "ui_dashboard",
        "task_id": None,
        "run_id": rid,
        "summary": f"Custodian acknowledged governed action run {rid}",
        "message": _sanitize_text(note, max_len=200),
        "dry_run": True,
    }
    try:
        with TEAM_BUS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ack_ev, ensure_ascii=False) + "\n")
    except OSError:
        return HTMLResponse("<span class='warn'>Failed to write ACK event.</span>", status_code=500)

    _write_ui_audit(
        "UI_CUSTODIAN_ACK",
        result="ok",
        reason="manual_ack",
        detail=f"run_id={rid}",
        action_id="custodian_ack",
        run_id=rid,
        request=request,
    )
    return HTMLResponse("<span class='ok'>ACK recorded</span>")


@app.post("/actions/chat-send", response_class=HTMLResponse)
def chat_send_action(request: Request, agent: str = Form(...), message: str = Form(...), sender: str = Form("operator")):
    target = (agent or "").strip()
    body = (message or "").strip()
    if not target:
        return HTMLResponse("<div class='warn'>Choose an agent first.</div>")
    if not body:
        return HTMLResponse("<div class='warn'>Message is empty.</div>")
    post_chat_message(target, body, sender=(sender.strip() or "operator"))
    live_enabled = (os.environ.get("OPENCLAW_UI_CHAT_LIVE", "1").strip().lower() not in {"0", "false", "no"})
    if live_enabled:
        ok, reply_text, err = _live_agent_reply(target, body)
        if ok:
            post_chat_reply_live(target, reply_text)
        else:
            post_chat_reply_system(
                target,
                f"[system] Live reply unavailable ({err}). Using fallback mode.",
            )
            post_chat_reply(target, body)
    else:
        post_chat_reply(target, body)
    return templates.TemplateResponse(
        "partials/chat_thread.html",
        {"request": request, "selected_agent": target, "messages": read_chat_messages(target)},
    )
