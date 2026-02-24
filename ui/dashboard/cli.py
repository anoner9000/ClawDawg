from __future__ import annotations

import subprocess
from dataclasses import dataclass

from .config import CLI_MAX_BYTES, CLI_TIMEOUT_SECS, QUERY_STATUS_CLI


@dataclass
class CliResult:
    ok: bool
    stdout: str
    stderr: str
    code: int
    cmd: list[str]
    timed_out: bool
    truncated_stdout: bool
    truncated_stderr: bool

    @property
    def truncated(self) -> bool:
        return self.truncated_stdout or self.truncated_stderr


def _truncate_utf8(text: str, max_bytes: int) -> tuple[str, bool]:
    raw = text.encode("utf-8", errors="replace")
    if len(raw) <= max_bytes:
        return text, False
    return raw[:max_bytes].decode("utf-8", errors="ignore"), True


def run_query_status(*args: str) -> CliResult:
    cmd = ["python3", str(QUERY_STATUS_CLI), *args]
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=CLI_TIMEOUT_SECS,
        )
        out, out_trunc = _truncate_utf8(proc.stdout or "", CLI_MAX_BYTES)
        err, err_trunc = _truncate_utf8(proc.stderr or "", CLI_MAX_BYTES)
        return CliResult(proc.returncode == 0, out, err, proc.returncode, cmd, False, out_trunc, err_trunc)
    except subprocess.TimeoutExpired as exc:
        raw_out = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        raw_err = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
        out, out_trunc = _truncate_utf8(raw_out, CLI_MAX_BYTES)
        err, err_trunc = _truncate_utf8(raw_err, CLI_MAX_BYTES)
        if not err:
            err = f"Command timed out after {CLI_TIMEOUT_SECS}s"
        return CliResult(False, out, err, 124, cmd, True, out_trunc, err_trunc)


def list_agents(base_dir: str | None = None) -> dict:
    """
    Enumerate agents under ./agents/* and return a JSON-serializable dict.
    """
    from pathlib import Path

    root = Path(base_dir or ".").resolve()
    agents_dir = root / "agents"
    out = {"base": str(root), "agents_dir": str(agents_dir), "agents": []}

    if not agents_dir.is_dir():
        out["note"] = "agents/ directory not found"
        return out

    for d in sorted([p for p in agents_dir.iterdir() if p.is_dir()], key=lambda p: p.name.lower()):
        out["agents"].append({
            "name": d.name,
            "path": str(d),
            "has_SOUL_md": (d / "SOUL.md").is_file(),
            "has_RUNBOOK_md": (d / "RUNBOOK.md").is_file(),
            "has_MANAGER_RUNBOOK_md": (d / "MANAGER_RUNBOOK.md").is_file(),
        })

    return out


# --- Runnable CLI entrypoint (added) ---
def main(argv=None) -> int:
    """
    Lightweight CLI wrapper around this module's helper functions.

    Usage:
      python -m ui.dashboard.cli --help
      python -m ui.dashboard status
    """
    import argparse

    parser = argparse.ArgumentParser(prog="openclaw-ui", add_help=True)
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("status", help="Query dashboard status (prints text/JSON)")

    p_agents = sub.add_parser("agents", help="Agent-related commands")
    agents_sub = p_agents.add_subparsers(dest="agents_cmd")
    agents_sub.add_parser("list", help="List filesystem-backed agents under ./agents")

    args = parser.parse_args(argv)

    if args.cmd is None:
        parser.print_help()
        return 0

    if args.cmd == "status":
        # uses existing helper in this module
        res = run_query_status()
        out = getattr(res, "output", None)
        if out:
            print(out, end="" if out.endswith("\n") else "\n")
            return int(getattr(res, "exit_code", 0) or 0)

        # Fallback: emit useful local JSON status so this is never silent.
        import json, os, subprocess, sys
        from datetime import datetime, timezone

        def sh(cmd):
            try:
                cp = subprocess.run(cmd, capture_output=True, text=True, check=False)
                return (cp.returncode, (cp.stdout or "").strip(), (cp.stderr or "").strip())
            except Exception as e:
                return (127, "", repr(e))

        def read_tail(path, n=1):
            try:
                txt = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
                return txt[-n:] if txt else []
            except Exception:
                return []

        # repo / git info
        rc, head, _ = sh(["git", "rev-parse", "--short", "HEAD"])
        git_head = head if rc == 0 else None
        rc, branch, _ = sh(["git", "rev-parse", "--abbrev-ref", "HEAD"])
        git_branch = branch if rc == 0 else None
        rc, stat, _ = sh(["git", "status", "-sb"])
        git_status = stat if rc == 0 else None

        # heartbeat hint (best-effort)
        hb_log = os.path.expanduser("~/.openclaw/runtime/logs/heartbeat_aggregator.log")
        hb_tail = read_tail(hb_log, n=3)

        payload = {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "cwd": os.getcwd(),
            "python": {
                "executable": sys.executable,
                "version": sys.version.split()[0],
            },
            "git": {
                "branch": git_branch,
                "head": git_head,
                "status": git_status,
            },
            "openclaw": {
                "note": "ui.dashboard status fallback (run_query_status returned empty output)"
            },
            "heartbeat_log_tail": hb_tail,
        }

        print(json.dumps(payload, indent=2, sort_keys=True))
        return int(getattr(res, "exit_code", 0) or 0)


    if args.cmd == "agents":
        import json
        if getattr(args, "agents_cmd", None) == "list":
            print(json.dumps(list_agents(), indent=2, sort_keys=True))
            return 0
        p_agents.print_help()
        return 2

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
