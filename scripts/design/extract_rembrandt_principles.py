#!/usr/bin/env python3
from pathlib import Path
import runpy
import sys


def main() -> int:
    target = Path(__file__).resolve().parents[2] / "ops" / "scripts" / "design" / "extract_rembrandt_principles.py"
    if not target.exists():
        print(f"missing target script: {target}", file=sys.stderr)
        return 1
    runpy.run_path(str(target), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
