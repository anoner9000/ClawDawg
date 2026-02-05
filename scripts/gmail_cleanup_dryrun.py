#!/usr/bin/env python3
import os
import sys
import runpy

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(BASE, "modules", "gmail", "scripts", "gmail_cleanup_dryrun.py")

if not os.path.exists(TARGET):
    print(f"wrapper_error: target missing: {TARGET}", file=sys.stderr)
    sys.exit(2)

sys.argv[0] = TARGET
runpy.run_path(TARGET, run_name="__main__")
