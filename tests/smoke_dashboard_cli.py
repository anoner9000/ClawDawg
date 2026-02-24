#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def run_module(args):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    p = subprocess.run(
        [sys.executable, "-m", "ui.dashboard", *args],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    if p.returncode != 0:
        print("STDOUT:\n", p.stdout)
        print("STDERR:\n", p.stderr)
        raise SystemExit(p.returncode)
    return p.stdout.strip()

def main():
    out = run_module(["status"])
    obj = json.loads(out)
    assert isinstance(obj, dict), "status must return a JSON object"
    assert "cwd" in obj, "status JSON should include cwd"

    out = run_module(["agents", "list"])
    obj = json.loads(out)
    assert isinstance(obj, dict), "agents list must return a JSON object"
    assert "agents" in obj and isinstance(obj["agents"], list), "agents list JSON must include agents[]"

    print("OK: dashboard CLI smoke passed")

if __name__ == "__main__":
    main()
