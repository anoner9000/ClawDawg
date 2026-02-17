#!/usr/bin/env python3
import json, os, subprocess, sys
from pathlib import Path
from fnmatch import fnmatch

def sh(*args: str) -> str:
    return subprocess.check_output(args, text=True).strip()

def list_changed(base: str, head: str) -> list[str]:
    out = sh("git", "diff", "--name-only", f"{base}..{head}")
    return [l for l in out.splitlines() if l.strip()]

def load_policy() -> dict:
    p = Path("policy/risk_policy.json")
    if not p.exists():
        print("ERROR: missing policy/risk_policy.json", file=sys.stderr)
        sys.exit(2)
    return json.loads(p.read_text(encoding="utf-8"))

def match_any(path: str, globs: list[str]) -> bool:
    # Support ** by using fnmatch (works fine for typical patterns)
    return any(fnmatch(path, g) for g in globs)

def compute_risk(changed: list[str], rules: dict) -> str:
    high = rules.get("high", [])
    low  = rules.get("low",  ["**"])
    # If any file matches high, treat as high.
    for f in changed:
        if match_any(f, high):
            return "high"
    # Otherwise low if all match low
    if all(match_any(f, low) for f in changed):
        return "low"
    return "high"

def docs_drift_ok(changed: list[str], docs_rules: dict) -> bool:
    require_docs_for = docs_rules.get("requireDocsForPaths", [])
    docs_globs = docs_rules.get("docsGlobs", [])
    touches_control_plane = any(match_any(f, require_docs_for) for f in changed)
    touches_docs = any(match_any(f, docs_globs) for f in changed)
    # If control-plane touched, require at least one docs file in same PR.
    return (not touches_control_plane) or touches_docs

def main():
    base = os.environ.get("BASE_SHA") or (sys.argv[1] if len(sys.argv) > 1 else "")
    head = os.environ.get("HEAD_SHA") or (sys.argv[2] if len(sys.argv) > 2 else "HEAD")
    if not base:
        # In CI for PRs we’ll set BASE_SHA; locally allow base=origin/master
        base = "origin/master"
    policy = load_policy()
    changed = list_changed(base, head)
    if not changed:
        print("OK: no changed files")
        return

    risk = compute_risk(changed, policy.get("riskTierRules", {}))
    if not docs_drift_ok(changed, policy.get("docsDriftRules", {})):
        print("FAIL: control-plane paths changed but no docs updates found.", file=sys.stderr)
        print("Changed files:", *changed, sep="\n  - ", file=sys.stderr)
        sys.exit(1)

    checks = policy["mergePolicy"][risk]["requiredChecks"]
    print(json.dumps({
        "riskTier": risk,
        "base": base,
        "head": head,
        "changedFiles": changed,
        "requiredChecks": checks
    }, indent=2))

if __name__ == "__main__":
    main()
