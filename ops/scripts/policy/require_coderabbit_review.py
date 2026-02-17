#!/usr/bin/env python3
import json, os, sys, time, urllib.request

BOT_LOGINS = {"coderabbitai[bot]", "coderabbitai"}  # be tolerant

def gh_api(url: str):
    token = os.environ["GITHUB_TOKEN"]
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode("utf-8"))

def main():
    repo = os.environ["GITHUB_REPOSITORY"]  # owner/name
    head_sha = os.environ["HEAD_SHA"]
    timeout_minutes = int(os.environ.get("TIMEOUT_MINUTES", "20"))
    deadline = time.time() + timeout_minutes * 60

    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path or not os.path.exists(event_path):
        print("ERROR: GITHUB_EVENT_PATH missing; must run in GitHub Actions PR context", file=sys.stderr)
        sys.exit(2)

    ev = json.load(open(event_path, "r", encoding="utf-8"))
    pr = ev.get("pull_request") or {}
    pr_number = pr.get("number")
    if not pr_number:
        print("ERROR: not a pull_request event (missing pull_request.number)", file=sys.stderr)
        sys.exit(2)

    # We'll accept evidence if we see a bot comment that references the head SHA,
    # or (fallback) a bot comment created after the latest commit timestamp.
    commits_url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/commits?per_page=250"
    comments_url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments?per_page=250"

    # Get PR commits to learn latest commit time
    commits = gh_api(commits_url)
    latest = commits[-1] if commits else None
    latest_sha = latest.get("sha") if latest else None
    latest_time = (latest.get("commit") or {}).get("committer", {}).get("date") if latest else None

    if latest_sha and latest_sha != head_sha:
        print(f"ERROR: HEAD_SHA mismatch: env={head_sha} api_latest={latest_sha}", file=sys.stderr)
        sys.exit(2)

    def is_after(a_iso: str, b_iso: str) -> bool:
        # ISO strings compare lexicographically in UTC Z form
        if not a_iso or not b_iso:
            return False
        return a_iso > b_iso

    last_state = None
    while time.time() < deadline:
        comments = gh_api(comments_url)

        matched_strong = None
        matched_weak = None

        for c in comments:
            user = (c.get("user") or {}).get("login", "")
            body = (c.get("body") or "")
            created = c.get("created_at") or ""

            if user not in BOT_LOGINS and "coderabbit" not in user.lower():
                continue

            # Strong: comment contains the head SHA
            if head_sha in body:
                matched_strong = {"user": user, "created_at": created}
                break

            # Weak: comment indicates CodeRabbit summary and is after last commit time
            if "Summary by CodeRabbit" in body and latest_time and is_after(created, latest_time):
                matched_weak = {"user": user, "created_at": created}

        state = {
            "pr": pr_number,
            "head_sha": head_sha,
            "latest_commit_time": latest_time,
            "strong": bool(matched_strong),
            "weak": bool(matched_weak),
        }
        if state != last_state:
            print("poll:", json.dumps(state, indent=2))
            last_state = state

        if matched_strong:
            print("OK: CodeRabbit comment references current head SHA:", json.dumps(matched_strong))
            return
        if matched_weak:
            print("OK: CodeRabbit summary comment posted after latest commit:", json.dumps(matched_weak))
            return

        time.sleep(10)

    print(f"FAIL: no CodeRabbit review evidence for current head SHA within {timeout_minutes} minutes", file=sys.stderr)
    print("Last state:", json.dumps(last_state, indent=2), file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
    main()
