#!/usr/bin/env python3
import json
import sys
from jsonschema import Draft7Validator

schema = json.load(open("schemas/team_bus.v1.json", "r", encoding="utf-8"))
validator = Draft7Validator(schema)

if len(sys.argv) < 2:
    print("usage: validate_team_bus_jsonl.py <events.jsonl>", file=sys.stderr)
    sys.exit(2)

bad = 0
with open(sys.argv[1], "r", encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except Exception as e:
            print(f"Line {i}: JSON parse error: {e}")
            bad += 1
            continue
        errors = sorted(validator.iter_errors(obj), key=lambda e: e.path)
        if errors:
            bad += 1
            for e in errors:
                path = ".".join([str(p) for p in e.path]) or "<root>"
                print(f"Line {i} {path}: {e.message}")

sys.exit(1 if bad else 0)
