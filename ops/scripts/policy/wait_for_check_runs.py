#!/usr/bin/env python3
import json, os, sys, time, urllib.request, urllib.error

def gh_api(path: str):
    repo = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GITHUB_TOKEN"]
    url = f"https://api.github.com/repos/{repo}/{path.lstrip('/')}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode("utf-8"))

def get_check_runs_for_sha(sha: str):
    # List check-runs for a specific commit SHA
    return gh_api(f"commits/{sha}/check-runs?per_page=100")

def summarize(cr):
    return {
        "name": cr.get("name"),
        "status": cr.get("status"),
        "conclusion": cr.get("conclusion"),
        "started_at": cr.get("started_at"),
        "completed_at": cr.get("completed_at"),
        "details_url": cr.get("details_url"),
        "head_sha": cr.get("head_sha"),
    }

def main():
    head_sha = os.environ.get("HEAD_SHA")
    if not head_sha:
        print("ERROR: HEAD_SHA env var required", file=sys.stderr)
        sys.exit(2)

    required = os.environ.get("REQUIRED_CHECKS", "").strip()
    if not required:
        print("OK: no REQUIRED_CHECKS specified")
        return
    required_names = [x.strip() for x in required.split(",") if x.strip()]

    timeout_minutes = int(os.environ.get("TIMEOUT_MINUTES", "20"))
    deadline = time.time() + timeout_minutes * 60

    # Names to ignore (avoid self-deadlock if included by mistake)
    ignore = {os.environ.get("GATE_CHECK_NAME", "risk-policy-gate").strip()}

    required_names = [n for n in required_names if n not in ignore]

    if not required_names:
        print("OK: only gate check present; nothing to wait for")
        return

    last_seen = None
    while time.time() < deadline:
        data = get_check_runs_for_sha(head_sha)
        runs = data.get("check_runs", [])
        by_name = {}
        for r in runs:
            by_name.setdefault(r.get("name"), []).append(r)

        missing = []
        not_done = []
        failed = []

        for name in required_names:
            candidates = by_name.get(name, [])
            if not candidates:
                missing.append(name)
                continue

            # pick newest run (completed_at if present, else started_at)
            def key(r):
                return r.get("completed_at") or r.get("started_at") or ""
            cand = sorted(candidates, key=key)[-1]

            # Enforce current-head SHA match (should always match because we query by commit,
            # but keep the invariant explicit)
            if cand.get("head_sha") != head_sha:
                failed.append((name, "stale_head_sha", summarize(cand)))
                continue

            status = cand.get("status")
            conc = cand.get("conclusion")

            if status != "completed":
                not_done.append((name, summarize(cand)))
                continue
            if conc not in ("success", "neutral", "skipped"):
                failed.append((name, conc, summarize(cand)))

        snapshot = {
            "head_sha": head_sha,
            "required": required_names,
            "missing": missing,
            "not_done": [x[0] for x in not_done],
            "failed": [(x[0], x[1]) for x in failed],
        }

        if snapshot != last_seen:
            print("poll:", json.dumps(snapshot, indent=2))
            last_seen = snapshot

        if not missing and not not_done and not failed:
            print("OK: all required check-runs completed successfully on head SHA")
            return

        time.sleep(10)

    print(f"FAIL: timed out waiting for required checks on head SHA after {timeout_minutes} minutes", file=sys.stderr)
    print("Last state:", json.dumps(last_seen, indent=2), file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
    main()
