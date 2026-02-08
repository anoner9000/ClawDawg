#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path

HOME = os.path.expanduser("~")
WORKSPACE = Path(HOME) / ".openclaw" / "workspace"
TARGET = WORKSPACE / "modules" / "gmail" / "scripts" / "gmail_cleanup_manage_senders.py"

def main() -> int:
    py = Path(HOME) / ".openclaw" / "venv" / "bin" / "python3"
    cmd = [str(py if py.exists() else "python3"), "-u", str(TARGET), *sys.argv[1:]]
    return subprocess.call(cmd)

if __name__ == "__main__":
    raise SystemExit(main())
