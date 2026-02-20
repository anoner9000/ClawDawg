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
