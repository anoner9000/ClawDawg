#!/usr/bin/env python3
"""Agent status responder and status event emitter."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import subprocess
from datetime import datetime, timezone
from pathlib import Path

BUS_DEFAULT = Path("~/.openclaw/runtime/logs/team_bus.jsonl").expanduser()
PERSIST_SCRIPT = Path("~/.openclaw/workspace/ops/scripts/agents/persist_status.sh").expanduser()
REMBRANDT_WORKER = Path(__file__).with_name("rembrandt_worker.py")
WORKSPACE_BASE = Path(os.environ.get("OPENCLAW_WORKSPACE", "~/.openclaw/workspace")).expanduser().resolve()
REMBRANDT_TASK_META_DIR = Path("~/.openclaw/runtime/tasks/rembrandt").expanduser()


def ts_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_bus_event(bus: Path, event: dict) -> None:
    bus.parent.mkdir(parents=True, exist_ok=True)
    with bus.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def persist(event: dict) -> None:
    if not PERSIST_SCRIPT.exists():
        return
    subprocess.run([str(PERSIST_SCRIPT), "--event-json", json.dumps(event, ensure_ascii=False)], check=True)


def build_base(agent: str, ev_type: str, task_id: str | None, summary: str, dry_run: bool) -> dict:
    return {
        "schema_version": "team_bus.v1.1",
        "ts": ts_utc(),
        "task_id": task_id,
        "agent": agent,
        "actor": agent,
        "type": ev_type,
        "summary": summary,
        "dry_run": dry_run,
    }


def _lookup_task_message(bus: Path, task_id: str, agent: str) -> str:
    if not bus.exists():
        return ""
    lines = [ln for ln in bus.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
    for line in reversed(lines):
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(ev.get("task_id") or "") != task_id:
            continue
        et = str(ev.get("type") or "")
        if et == "FORMAL_COMMAND_ISSUED" and str(ev.get("target_agent") or "") == agent:
            return str(ev.get("message") or "")
        if et == "CHAT" and str(ev.get("target_agent") or "") == agent and str(ev.get("actor") or "") == "operator":
            return str(ev.get("message") or "")
    return ""


def _strict_contract_message(message: str) -> bool:
    return "strict_overhaul_contract=true" in (message or "").lower()


def _task_meta_path(task_id: str) -> Path:
    return REMBRANDT_TASK_META_DIR / f"{task_id}.json"


def _git_head_sha() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(WORKSPACE_BASE),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return ""
    return (proc.stdout or "").strip()


def _load_task_meta(task_id: str) -> dict:
    p = _task_meta_path(task_id)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def _save_task_meta(task_id: str, meta: dict) -> None:
    p = _task_meta_path(task_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _ensure_task_base_sha(task_id: str, message: str) -> str:
    if not _strict_contract_message(message):
        return ""
    meta = _load_task_meta(task_id)
    base_sha = str(meta.get("base_sha") or "").strip()
    if base_sha:
        return base_sha
    head = _git_head_sha()
    if not head:
        return ""
    _save_task_meta(
        task_id,
        {
            "task_id": task_id,
            "base_sha": head,
            "created_at": ts_utc(),
            "mode": "strict_contract",
        },
    )
    return head


def _run_rembrandt_verify(task_id: str, message: str, base_sha: str = "") -> tuple[bool, str, str]:
    if not REMBRANDT_WORKER.exists():
        return False, "", f"missing worker script: {REMBRANDT_WORKER}"
    msg_file: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, prefix="rembrandt-verify-", suffix=".txt") as tf:
            tf.write(message or "")
            msg_file = Path(tf.name)
        cmd = [
            "python3",
            str(REMBRANDT_WORKER),
            "--task-id",
            task_id,
            "--message-file",
            str(msg_file),
            "--mode",
            "verify",
        ]
        if base_sha:
            cmd.extend(["--base-sha", base_sha])
        else:
            cmd.extend(["--diff-base", "HEAD"])
        proc = subprocess.run(
            cmd,
            cwd=str(WORKSPACE_BASE),
            env={**os.environ, "OPENCLAW_WORKSPACE": str(WORKSPACE_BASE)},
            capture_output=True,
            text=True,
            check=False,
        )
        out = (proc.stdout or proc.stderr or "").strip()
        report_path = ""
        fail_reason = ""
        for line in reversed(out.splitlines()):
            txt = line.strip()
            if not txt.startswith("{"):
                continue
            try:
                obj = json.loads(txt)
            except json.JSONDecodeError:
                continue
            fail_reason = str(obj.get("fail_reason") or "").strip()
            rp = obj.get("report_path")
            if isinstance(rp, str) and rp.strip():
                report_path = rp.strip()
            break
        if not report_path:
            ws = WORKSPACE_BASE
            guess = ws / ".openclaw" / "runtime" / "reports" / "rembrandt" / f"{task_id}.json"
            report_path = str(guess)
        detail = fail_reason or (out.splitlines()[-1] if out else "")
        return proc.returncode == 0, report_path, detail
    except Exception as e:
        return False, "", str(e)
    finally:
        if msg_file is not None:
            try:
                msg_file.unlink(missing_ok=True)
            except OSError:
                pass


def _verify_failure_context(report_path: str) -> str:
    if not report_path:
        return ""
    p = Path(report_path)
    if not p.exists():
        return ""
    try:
        rep = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return ""
    checks = rep.get("checks") or {}
    if not isinstance(checks, dict):
        return ""
    base_css_source = str(checks.get("base_css_source") or "").strip()
    compiled_css_source = str(checks.get("compiled_css_source") or "").strip()
    if not base_css_source and not compiled_css_source:
        return ""
    parts: list[str] = []
    if base_css_source:
        parts.append(f"base_css_source={base_css_source}")
    if compiled_css_source:
        parts.append(f"compiled_css_source={compiled_css_source}")
    return " ".join(parts)


def cmd_status(args: argparse.Namespace) -> int:
    event = build_base(args.agent, "STATUS", args.task_id, args.summary, not args.live)
    event["status"] = args.status
    if args.progress is not None:
        event["progress"] = args.progress
    if args.details_path:
        event["details_path"] = args.details_path
    write_bus_event(args.bus, event)
    persist(event)
    print(json.dumps(event, ensure_ascii=False))
    return 0


def cmd_ack(args: argparse.Namespace) -> int:
    event = build_base(args.agent, "TASK_ACK", args.task_id, args.summary, not args.live)
    event["assigned_by"] = args.assigned_by
    event["owner"] = args.owner or args.agent
    if args.agent == "rembrandt":
        task_message = _lookup_task_message(args.bus, args.task_id, "rembrandt")
        _ensure_task_base_sha(args.task_id, task_message)
    if args.eta:
        event["ETA"] = args.eta
    write_bus_event(args.bus, event)
    persist(event)
    print(json.dumps(event, ensure_ascii=False))
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    event = build_base(args.agent, "TASK_UPDATE", args.task_id, args.summary, not args.live)
    event["state"] = args.state
    if args.agent == "rembrandt":
        task_message = _lookup_task_message(args.bus, args.task_id, "rembrandt")
        base_sha = _ensure_task_base_sha(args.task_id, task_message)
    else:
        task_message = ""
        base_sha = ""
    if args.agent == "rembrandt" and args.state == "complete":
        if _strict_contract_message(task_message):
            ok, report_path, detail = _run_rembrandt_verify(args.task_id, task_message, base_sha=base_sha)
            if not ok:
                event["state"] = "error"
                fail_ctx = ""
                try:
                    fail_ctx = _verify_failure_context(report_path)
                except Exception:
                    fail_ctx = ""
                suffix = f" {fail_ctx}" if fail_ctx else ""
                event["summary"] = f"completion_blocked_by_verify_gate:{detail or 'verify_failed'}{suffix}"
                if report_path:
                    event["details_path"] = report_path
            else:
                if report_path:
                    event["details_path"] = report_path
    if args.details_path and not event.get("details_path"):
        event["details_path"] = args.details_path
    if args.error_code:
        event["error_code"] = args.error_code
    write_bus_event(args.bus, event)
    persist(event)
    print(json.dumps(event, ensure_ascii=False))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    event = build_base(args.agent, "STATUS_REPORT", args.task_id, args.summary, not args.live)
    event["report_path"] = args.report_path
    write_bus_event(args.bus, event)
    persist(event)
    print(json.dumps(event, ensure_ascii=False))
    return 0


def _scope_matches(scope: str, agent: str, task_id: str | None) -> bool:
    if scope == "all":
        return True
    if scope.startswith("agent:"):
        return scope.split(":", 1)[1] == agent
    if scope.startswith("task:") and task_id:
        return scope.split(":", 1)[1] == task_id
    return False


def cmd_respond_check(args: argparse.Namespace) -> int:
    if not args.bus.exists():
        raise SystemExit(f"bus not found: {args.bus}")
    lines = [ln for ln in args.bus.read_text(encoding="utf-8").splitlines() if ln.strip()]
    latest = None
    for line in reversed(lines):
        ev = json.loads(line)
        if ev.get("type") == "STATUS_CHECK" and _scope_matches(str(ev.get("scope", "all")), args.agent, args.task_id):
            latest = ev
            break
    if latest is None:
        print("No matching STATUS_CHECK found.")
        return 1

    summary = args.summary or f"{args.agent} status reply"
    event = build_base(args.agent, "STATUS", args.task_id, summary, not args.live)
    event["status"] = args.status
    event["progress"] = args.progress
    event["in_reply_to_ts"] = latest.get("ts")
    write_bus_event(args.bus, event)
    persist(event)
    print(json.dumps(event, ensure_ascii=False))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bus", type=Path, default=BUS_DEFAULT)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("status")
    sp.add_argument("--agent", required=True)
    sp.add_argument("--task-id")
    sp.add_argument("--status", choices=["idle", "in_process", "error", "complete"], default="idle")
    sp.add_argument("--progress", type=int)
    sp.add_argument("--summary", default="Status update")
    sp.add_argument("--details-path")
    sp.add_argument("--live", action="store_true")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("ack")
    sp.add_argument("--agent", required=True)
    sp.add_argument("--task-id", required=True)
    sp.add_argument("--assigned-by", default="deiphobe")
    sp.add_argument("--owner")
    sp.add_argument("--eta")
    sp.add_argument("--summary", default="Task acknowledged")
    sp.add_argument("--live", action="store_true")
    sp.set_defaults(func=cmd_ack)

    sp = sub.add_parser("update")
    sp.add_argument("--agent", required=True)
    sp.add_argument("--task-id", required=True)
    sp.add_argument("--state", choices=["in_process", "error", "complete"], required=True)
    sp.add_argument("--summary", default="Task state update")
    sp.add_argument("--details-path")
    sp.add_argument("--error-code")
    sp.add_argument("--live", action="store_true")
    sp.set_defaults(func=cmd_update)

    sp = sub.add_parser("report")
    sp.add_argument("--agent", required=True)
    sp.add_argument("--task-id", required=True)
    sp.add_argument("--report-path", required=True)
    sp.add_argument("--summary", required=True)
    sp.add_argument("--live", action="store_true")
    sp.set_defaults(func=cmd_report)

    sp = sub.add_parser("respond-check")
    sp.add_argument("--agent", required=True)
    sp.add_argument("--task-id")
    sp.add_argument("--status", choices=["idle", "in_process", "error", "complete"], default="idle")
    sp.add_argument("--progress", type=int, default=0)
    sp.add_argument("--summary", default="")
    sp.add_argument("--live", action="store_true")
    sp.set_defaults(func=cmd_respond_check)

    args = ap.parse_args()
    args.bus = args.bus.expanduser()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
