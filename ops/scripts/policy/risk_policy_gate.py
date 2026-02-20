#!/usr/bin/env python3
import json, os, subprocess, sys
from pathlib import Path
from fnmatch import fnmatch
import yaml

POLICY_PATH = Path("ops/policy/risk_policy.yml")

def die(msg: str, code: int = 2) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)

def sh(*args: str) -> str:
    return subprocess.check_output(args, text=True).strip()

def list_changed(base: str, head: str) -> list[str]:
    out = sh("git", "diff", "--name-only", f"{base}..{head}")
    return [l for l in out.splitlines() if l.strip()]

def load_policy() -> dict:
    if not POLICY_PATH.exists():
        die("risk_policy.yml not found; policy contract required.", code=2)
    try:
        with POLICY_PATH.open("r", encoding="utf-8") as f:
            policy = yaml.safe_load(f)
    except yaml.YAMLError as e:
        die(f"invalid policy contract YAML: {e}", code=2)
    if not isinstance(policy, dict):
        die("invalid policy contract: expected top-level mapping", code=2)
    tiers = policy.get("tiers")
    if not isinstance(tiers, dict) or not tiers:
        die("invalid policy contract: missing or invalid 'tiers'", code=2)
    return policy

def match_any(path: str, globs: list[str]) -> bool:
    # Support ** by using fnmatch (works fine for typical patterns)
    return any(fnmatch(path, g) for g in globs)

def compute_risk(changed: list[str], control_plane_patterns: list[str]) -> str:
    if control_plane_changed(changed, control_plane_patterns):
        return "high"
    return "low"

def docs_updated(changed_files: list[str], required_doc: str) -> bool:
    """
    Returns True if canonical control-plane docs were updated.
    """
    return required_doc in changed_files

def control_plane_changed(changed_files: list[str], control_plane_patterns: list[str]) -> bool:
    """
    Returns True if control-plane paths were modified.
    """
    return any(match_any(path, control_plane_patterns) for path in changed_files)

def enforce_review_agent(require_coderabbit_head: bool, head: str) -> bool:
    if not require_coderabbit_head:
        return False
    if os.environ.get("GITHUB_EVENT_NAME") != "pull_request":
        # Review-agent evidence is PR-comment based, so skip outside PRs.
        return False

    script = Path("ops/scripts/policy/require_coderabbit_review.py")
    if not script.exists():
        die(f"missing {script}", code=2)
    if not os.environ.get("GITHUB_TOKEN"):
        die("GITHUB_TOKEN is required to enforce coderabbit head review in PR context", code=2)

    env = os.environ.copy()
    env["HEAD_SHA"] = head
    env["TIMEOUT_MINUTES"] = str(env.get("TIMEOUT_MINUTES", "20"))
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
    control_plane_patterns = policy.get("control_plane_paths", [])
    if not isinstance(control_plane_patterns, list):
        die("invalid policy contract: 'control_plane_paths' must be a list", code=2)
    docs_cfg = policy.get("docs", {})
    docs_required = "docs/control-plane.md"
    if isinstance(docs_cfg, dict):
        docs_required = docs_cfg.get("required_on_control_plane_change", docs_required)

    changed = list_changed(base, head)
    risk = compute_risk(changed, control_plane_patterns) if changed else "low"
    tiers = policy.get("tiers", {})
    tier_config = tiers.get(risk)
    if not isinstance(tier_config, dict):
        die(f"invalid policy contract: missing tier config for '{risk}'", code=2)
    checks = tier_config.get("required_checks")
    if not isinstance(checks, list):
        die(f"invalid policy contract: tiers.{risk}.required_checks must be a list", code=2)
    risk_label = tier_config.get("label") if isinstance(tier_config.get("label"), str) else f"risk:{risk}"

    if not changed:
        result = {
            "baseSha": base,
            "headSha": head,
            "riskTier": "low",
            "riskLabel": risk_label,
            "requiredChecks": checks,
            "touchedPaths": [],
            "policyVersion": policy.get("version"),
            "policy": {
                "controlPlanePaths": control_plane_patterns,
                "tiers": tiers,
                "docs": docs_cfg if isinstance(docs_cfg, dict) else {},
            },
            "reviewAgentEnforced": False
        }
        with open("gate.json", "w", encoding="utf-8") as jf:
            json.dump(result, jf, indent=2)
        write_github_output(
            riskTier=result["riskTier"],
            riskLabel=result["riskLabel"],
            requiredChecks=result["requiredChecks"],
            touchedPaths=result["touchedPaths"],
        )
        print(json.dumps(result, indent=2))
        return

    changed_files = changed
    cp_changed = control_plane_changed(changed_files, control_plane_patterns)
    docs_changed = docs_updated(changed_files, docs_required)

    if cp_changed and not docs_changed:
        if risk == "low":
            print(
                f"WARNING: control-plane paths changed but no {docs_required} update found; "
                "allowing because riskTier=low.",
                file=sys.stderr,
            )
        else:
            print(f"FAIL: control-plane paths changed but no {docs_required} update found.")
            print("Changed files:")
            for f in changed_files:
                print(f"  - {f}")
            sys.exit(1)

    review_agent_enforced = enforce_review_agent(bool(tier_config.get("require_coderabbit_head")), head)
    result = {
        "baseSha": base,
        "headSha": head,
        "riskTier": risk,
        "riskLabel": risk_label,
        "requiredChecks": checks,
        "touchedPaths": changed,
        "policyVersion": policy.get("version"),
        "policy": {
            "controlPlanePaths": control_plane_patterns,
            "tiers": tiers,
            "docs": docs_cfg if isinstance(docs_cfg, dict) else {},
        },
        "reviewAgentEnforced": review_agent_enforced
    }
    with open("gate.json", "w", encoding="utf-8") as jf:
        json.dump(result, jf, indent=2)
    write_github_output(
        riskTier=result["riskTier"],
        riskLabel=result["riskLabel"],
        requiredChecks=result["requiredChecks"],
        touchedPaths=result["touchedPaths"],
    )
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
