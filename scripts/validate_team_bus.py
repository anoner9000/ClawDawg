#!/usr/bin/env python3
"""
validate_team_bus.py

Validate an OpenClaw agent team bus JSONL file against the team_bus.v1 schema.

Features
- Validates each JSON line as an independent event.
- Prints a compact summary + per-line errors.
- Optional: writes a cleaned JSONL containing only valid events.
- Optional: strict mode to fail if any unknown fields appear (schema already forbids them at top level).

Usage
  python3 validate_team_bus.py /path/to/team_bus.jsonl

Options
  --schema /path/to/team_bus.v1.schema.json
      If omitted, uses the embedded schema below.

  --clean-out /path/to/clean.jsonl
      Write only valid events to this file (append-only overwrite).

  --max-errors N
      Stop after reporting N line-errors (default: 200).

  --quiet
      Only print summary (no per-line errors).

Exit codes
  0 = all events valid
  1 = at least one invalid line
  2 = file I/O error
  3 = schema/validator error
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from jsonschema import Draft7Validator
except Exception as e:
    print("ERROR: Missing dependency 'jsonschema'. Install with: pip install jsonschema", file=sys.stderr)
    raise


EMBEDDED_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "https://openclaw.local/schemas/team_bus.v1.json",
    "title": "OpenClaw Agent Team Bus Event (team_bus.v1)",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version",
        "ts",
        "task_id",
        "agent",
        "type",
        "summary",
        "details",
        "next",
    ],
    "properties": {
        "schema_version": {"const": "team_bus.v1"},
        "ts": {
            "type": "string",
            "description": "ISO-8601 UTC timestamp (recommended Z suffix).",
            "pattern": r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,9})?Z$",
        },
        "task_id": {
            "type": "string",
            "minLength": 3,
            "maxLength": 200,
            "pattern": r"^[A-Za-z0-9][A-Za-z0-9._:-]{1,199}$",
        },
        "agent": {
            "type": "string",
            "enum": ["deiphobe", "planner", "executor", "auditor", "watcher", "specialist"],
        },
        "type": {
            "type": "string",
            "enum": [
                "INTENT",
                "PLAN",
                "REVIEW",
                "APPROVAL",
                "UPDATE",
                "RESULT",
                "VERIFIED",
                "RISK",
                "BLOCKED",
                "CLOSED",
            ],
        },
        "summary": {"type": "string", "minLength": 3, "maxLength": 500},
        "details": {
            "type": "object",
            "description": "Structured details. Do not include secrets or massive raw logs.",
            "additionalProperties": True,
        },
        "next": {"type": "string", "minLength": 1, "maxLength": 300},
        "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
        "evidence": {"type": "object", "additionalProperties": True},
    },
    "allOf": [
        {
            "if": {"properties": {"type": {"const": "RISK"}}, "required": ["type"]},
            "then": {"required": ["severity"]},
        },
        {
            "if": {"properties": {"type": {"const": "APPROVAL"}}, "required": ["type"]},
            "then": {"properties": {"agent": {"const": "deiphobe"}}},
        },
        {
            "if": {"properties": {"type": {"const": "RESULT"}}, "required": ["type"]},
            "then": {"properties": {"agent": {"const": "executor"}}},
        },
        {
            "if": {"properties": {"type": {"const": "VERIFIED"}}, "required": ["type"]},
            "then": {"properties": {"agent": {"const": "auditor"}}},
        },
        {
            "if": {"properties": {"type": {"const": "CLOSED"}}, "required": ["type"]},
            "then": {"properties": {"agent": {"const": "deiphobe"}}},
        },
    ],
}


def _load_schema(schema_path: Optional[str]) -> Dict[str, Any]:
    if not schema_path:
        return EMBEDDED_SCHEMA
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _format_path(path_parts: Iterable[Any]) -> str:
    parts = list(path_parts)
    if not parts:
        return "<root>"
    # Use dotted path; bracket for ints
    out = []
    for p in parts:
        if isinstance(p, int):
            out.append(f"[{p}]")
        else:
            if out and not out[-1].endswith("]"):
                out.append(".")
            out.append(str(p))
    return "".join(out).replace(".[", "[")


def validate_jsonl(
    jsonl_path: str,
    validator: Draft7Validator,
    max_errors: int = 200,
    quiet: bool = False,
    clean_out: Optional[str] = None,
) -> Tuple[int, int, int]:
    """
    Returns: (total_lines_with_content, valid_events, invalid_events)
    """
    total = 0
    valid = 0
    invalid = 0

    clean_f = None
    if clean_out:
        os.makedirs(os.path.dirname(os.path.abspath(clean_out)) or ".", exist_ok=True)
        clean_f = open(clean_out, "w", encoding="utf-8")

    try:
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line_no, raw in enumerate(f, 1):
                if not raw.strip():
                    continue
                total += 1

                # Parse JSON
                try:
                    obj = json.loads(raw)
                except Exception as e:
                    invalid += 1
                    if not quiet:
                        print(f"Line {line_no}: JSON parse error: {e}", file=sys.stderr)
                    if invalid >= max_errors:
                        break
                    continue

                # Validate
                errors = sorted(validator.iter_errors(obj), key=lambda e: list(e.path))
                if errors:
                    invalid += 1
                    if not quiet:
                        for e in errors:
                            path = _format_path(e.path)
                            print(f"Line {line_no} {path}: {e.message}", file=sys.stderr)
                    if invalid >= max_errors:
                        break
                    continue

                # Valid
                valid += 1
                if clean_f is not None:
                    clean_f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    finally:
        if clean_f is not None:
            clean_f.close()

    return total, valid, invalid


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate team_bus.jsonl against team_bus.v1 schema.")
    ap.add_argument("jsonl", help="Path to team bus JSONL file")
    ap.add_argument("--schema", default=None, help="Optional path to a JSON schema file")
    ap.add_argument("--clean-out", default=None, help="Write only valid events to this JSONL path")
    ap.add_argument("--max-errors", type=int, default=200, help="Stop after reporting this many invalid lines")
    ap.add_argument("--quiet", action="store_true", help="Only print summary (no per-line errors)")
    args = ap.parse_args()

    try:
        schema = _load_schema(args.schema)
        validator = Draft7Validator(schema)
    except Exception as e:
        print(f"ERROR: Failed to load/compile schema: {e}", file=sys.stderr)
        return 3

    try:
        total, valid, invalid = validate_jsonl(
            jsonl_path=args.jsonl,
            validator=validator,
            max_errors=args.max_errors,
            quiet=args.quiet,
            clean_out=args.clean_out,
        )
    except FileNotFoundError:
        print(f"ERROR: File not found: {args.jsonl}", file=sys.stderr)
        return 2
    except PermissionError:
        print(f"ERROR: Permission denied reading: {args.jsonl}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"ERROR: Validation failed: {e}", file=sys.stderr)
        return 2

    # Summary (always printed)
    print(
        f"team_bus validation: file={args.jsonl} events={total} valid={valid} invalid={invalid}"
        + (f" clean_out={args.clean_out}" if args.clean_out else "")
    )

    return 0 if invalid == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
