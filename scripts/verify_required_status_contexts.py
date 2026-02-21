#!/usr/bin/env python3
import json
import os
import subprocess
import sys

REPO = os.environ.get("GITHUB_REPOSITORY")
PR_NUMBER = os.environ.get("PR_NUMBER")
RULESET_ID = os.environ.get("RULESET_ID")


def gh_json(args):
    r = subprocess.run(
        ["gh"] + args,
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        sys.exit(r.returncode)
    return json.loads(r.stdout)


if not REPO or not PR_NUMBER or not RULESET_ID:
    print("Missing required environment variables.")
    sys.exit(1)

# Fetch required contexts from ruleset
ruleset = gh_json(["api", f"repos/{REPO}/rulesets/{RULESET_ID}"])
required = []

for rule in ruleset.get("rules", []):
    if rule.get("type") == "required_status_checks":
        required = [c["context"] for c in rule["parameters"]["required_status_checks"]]

# Fetch actual PR status contexts
pr = gh_json([
    "pr", "view", PR_NUMBER,
    "--repo", REPO,
    "--json", "statusCheckRollup"
])

emitted = []
for check in pr.get("statusCheckRollup", []):
    if check.get("name"):
        emitted.append(check["name"])

missing = [ctx for ctx in required if ctx not in emitted]

if missing:
    print("ERROR: Required status contexts missing from PR:")
    for m in missing:
        print(f"  - {m}")
    sys.exit(2)

print("OK: Required status contexts match emitted checks.")
