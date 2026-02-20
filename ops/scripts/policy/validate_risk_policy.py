#!/usr/bin/env python3
"""
validate_risk_policy.py

Validates ops/policy/risk_policy.yml has the required shape/fields.
Fails fast with clear messages so policy changes cannot silently weaken governance.

Exit codes:
- 0: OK
- 2: invalid/missing contract
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml  # type: ignore
except Exception as e:
    print(f"ERROR: PyYAML is required to validate policy contract: {e}", file=sys.stderr)
    raise SystemExit(2)

POLICY_PATH = Path("ops/policy/risk_policy.yml")
ALLOWED_TIERS = ("low", "medium", "high")


def die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(2)


def require(cond: bool, msg: str) -> None:
    if not cond:
        die(msg)


def require_key(d: dict, key: str, ctx: str) -> object:
    if key not in d:
        die(f"{ctx}: missing required key '{key}'")
    return d[key]


def require_str(v: object, ctx: str) -> str:
    require(isinstance(v, str) and v.strip() != "", f"{ctx}: must be a non-empty string")
    return str(v)


def require_int(v: object, ctx: str) -> int:
    require(isinstance(v, int), f"{ctx}: must be an integer")
    return int(v)


def require_bool(v: object, ctx: str) -> bool:
    require(isinstance(v, bool), f"{ctx}: must be a boolean")
    return bool(v)


def require_list_of_str(v: object, ctx: str, non_empty: bool = True) -> list[str]:
    require(isinstance(v, list), f"{ctx}: must be a list")
    xs = v
    require(all(isinstance(x, str) and x.strip() for x in xs), f"{ctx}: must be a list of non-empty strings")
    if non_empty:
        require(len(xs) > 0, f"{ctx}: must be non-empty")
    return [str(x) for x in xs]


def main() -> None:
    require(POLICY_PATH.exists(), f"policy contract not found at {POLICY_PATH}")

    try:
        policy = yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        die(f"failed to parse {POLICY_PATH}: {e}")

    require(isinstance(policy, dict), f"{POLICY_PATH}: root must be a mapping/object")

    version = require_key(policy, "version", "root")
    require_int(version, "root.version")

    control_plane_paths = require_key(policy, "control_plane_paths", "root")
    require_list_of_str(control_plane_paths, "root.control_plane_paths", non_empty=True)

    docs = require_key(policy, "docs", "root")
    require(isinstance(docs, dict), "root.docs: must be an object")
    required_on_cp = require_key(docs, "required_on_control_plane_change", "root.docs")
    require_str(required_on_cp, "root.docs.required_on_control_plane_change")

    tiers = require_key(policy, "tiers", "root")
    require(isinstance(tiers, dict), "root.tiers: must be an object")
    for tier in ALLOWED_TIERS:
        t = tiers.get(tier)
        require(isinstance(t, dict), f"root.tiers.{tier}: must be an object")
        required_checks = require_key(t, "required_checks", f"root.tiers.{tier}")
        require_list_of_str(required_checks, f"root.tiers.{tier}.required_checks", non_empty=True)
        # Optional but common
        if "require_coderabbit_head" in t:
            require_bool(t["require_coderabbit_head"], f"root.tiers.{tier}.require_coderabbit_head")

    # Optional: sanity check no unknown tier keys (helps catch typos like "medum")
    unknown = sorted([k for k in tiers.keys() if k not in ALLOWED_TIERS])
    if unknown:
        die(f"root.tiers: unknown tier(s) {unknown}; allowed: {list(ALLOWED_TIERS)}")

    print(f"OK: {POLICY_PATH} valid (policyVersion={int(version)})")


if __name__ == "__main__":
    main()
