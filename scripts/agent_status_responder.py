#!/usr/bin/env python3
"""Compatibility forwarder to canonical responder."""

from __future__ import annotations

from pathlib import Path
import runpy


TARGET = Path(__file__).resolve().parents[1] / "ops" / "scripts" / "agents" / "agent_status_responder.py"

if not TARGET.exists():
    raise SystemExit(f"missing canonical responder: {TARGET}")

runpy.run_path(str(TARGET), run_name="__main__")

