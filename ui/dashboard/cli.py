from __future__ import annotations

import subprocess
from dataclasses import dataclass

from .config import CLI_MAX_CHARS, CLI_TIMEOUT_SECS, QUERY_STATUS_CLI


@dataclass
class CliResult:
    ok: bool
    stdout: str
    stderr: str
    code: int
    cmd: list[str]


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
        out = (proc.stdout or "")[:CLI_MAX_CHARS]
        err = (proc.stderr or "")[:CLI_MAX_CHARS]
        return CliResult(proc.returncode == 0, out, err, proc.returncode, cmd)
    except subprocess.TimeoutExpired as exc:
        out = ((exc.stdout or "") if isinstance(exc.stdout, str) else "")[:CLI_MAX_CHARS]
        err = ((exc.stderr or "") if isinstance(exc.stderr, str) else "")[:CLI_MAX_CHARS]
        if not err:
            err = f"Command timed out after {CLI_TIMEOUT_SECS}s"
        return CliResult(False, out, err, 124, cmd)
