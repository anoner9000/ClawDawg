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

def compute_required_checks(policy: dict, risk: str) -> list[str]:
    merge_policy = policy.get("mergePolicy", {})
    raw_checks = merge_policy.get(risk, {}).get("requiredChecks", [])
    # Normalize historical check names into branch-protection contexts.
    normalize = {
        "CI Pipeline": "ci",
        "risk-policy-gate": "gate",
    }
    checks: list[str] = []
    for check in raw_checks:
        checks.append(normalize.get(check, check))

    review_cfg = policy.get("reviewAgent", {})
    if risk == "high" and review_cfg.get("enabled", False):
        checks.append("code-review-head")

    # Stable de-dup preserving order.
    seen: set[str] = set()
    out: list[str] = []
    for check in checks:
        if check in seen:
            continue
        seen.add(check)
        out.append(check)
    return out

def docs_updated(changed_files: list[str]) -> bool:
    """
    Returns True if canonical control-plane docs were updated.
    """
    for path in changed_files:
        if path == "docs/control-plane.md":
            return True
    return False

def control_plane_changed(changed_files: list[str]) -> bool:
    """
    Returns True if control-plane paths were modified.
    """
    for path in changed_files:
        if path.startswith(".github/workflows/"):
            return True
        if path.startswith("ops/scripts/policy/"):
            return True
    return False

def enforce_review_agent(policy: dict, risk: str, head: str) -> bool:
    cfg = policy.get("reviewAgent", {})
    if risk != "high" or not cfg.get("enabled", False):
        return False
    if os.environ.get("GITHUB_EVENT_NAME") != "pull_request":
        # Review-agent evidence is PR-comment based, so skip outside PRs.
        return False

    script = Path("ops/scripts/policy/require_review_agent.py")
    if not script.exists():
        print(f"ERROR: missing {script}", file=sys.stderr)
        sys.exit(2)
    if not os.environ.get("GITHUB_TOKEN"):
        print("ERROR: GITHUB_TOKEN is required to enforce reviewAgent in PR context", file=sys.stderr)
        sys.exit(2)

    env = os.environ.copy()
    env["HEAD_SHA"] = head
    env["TIMEOUT_MINUTES"] = str(cfg.get("timeoutMinutes", 20))
    try:
        subprocess.run([sys.executable, str(script)], env=env, check=True)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode or 1)
    return True

def write_github_output(**kwargs):
    """
    Write key=value lines to GITHUB_OUTPUT for GitHub Actions.
    """
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as f:
        for key, val in kwargs.items():
            # JSON-encode complex values
            if isinstance(val, (dict, list, bool)):
                val = json.dumps(val)
            f.write(f"{key}={val}\n")

def main():
    base = os.environ.get("BASE_SHA") or (sys.argv[1] if len(sys.argv) > 1 else "")
    head = os.environ.get("HEAD_SHA") or (sys.argv[2] if len(sys.argv) > 2 else "HEAD")
    if not base:
        # In CI for PRs we’ll set BASE_SHA; locally allow base=origin/master
        base = "origin/master"
    policy = load_policy()
    changed = list_changed(base, head)
    risk = compute_risk(changed, policy.get("riskTierRules", {})) if changed else "low"
    checks = compute_required_checks(policy, risk)
    if not changed:
        result = {
            "baseSha": base,
            "headSha": head,
            "riskTier": "low",
            "requiredChecks": checks,
            "touchedPaths": [],
            "policy": {
                "tierRules": policy.get("riskTierRules", {}),
                "mergePolicy": policy.get("mergePolicy", {}),
            },
            "reviewAgentEnforced": False
        }
        with open("gate.json", "w", encoding="utf-8") as jf:
            json.dump(result, jf, indent=2)
        write_github_output(
            riskTier=result.get("riskTier"),
            requiredChecks=result.get("requiredChecks", []),
            touchedPaths=result.get("touchedPaths", []),
        )
        print(json.dumps(result, indent=2))
        return

    changed_files = changed
    cp_changed = control_plane_changed(changed_files)
    docs_changed = docs_updated(changed_files)

    if cp_changed and not docs_changed:
        print("FAIL: control-plane paths changed but no docs/control-plane.md update found.")
        print("Changed files:")
        for f in changed_files:
            print(f"  - {f}")
        sys.exit(1)

    review_agent_enforced = enforce_review_agent(policy, risk, head)
    result = {
        "baseSha": base,
        "headSha": head,
        "riskTier": risk,
        "requiredChecks": checks,
        "touchedPaths": changed,
        "policy": {
            "tierRules": policy.get("riskTierRules", {}),
            "mergePolicy": policy.get("mergePolicy", {}),
        },
        "reviewAgentEnforced": review_agent_enforced
    }
    with open("gate.json", "w", encoding="utf-8") as jf:
        json.dump(result, jf, indent=2)
    write_github_output(
        riskTier=result.get("riskTier"),
        requiredChecks=result.get("requiredChecks", []),
        touchedPaths=result.get("touchedPaths", []),
    )
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
