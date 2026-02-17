#!/usr/bin/env python3
import json
import os
import sys
import time
import urllib.error
import urllib.request

BOT_LOGINS = {"coderabbitai[bot]", "coderabbitai"}


def fail(msg: str, code: int = 2) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def env_required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        fail(f"missing required env var: {name}")
    return value


def gh_api(url: str, token: str):
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        fail(f"GitHub API {e.code} for {url}: {body[:3000]}")

def iso_ge(a: str, b: str) -> bool:
    # ISO-8601 UTC strings compare lexicographically safely when both are Zulu.
    return (a or "") >= (b or "")


def main() -> None:
    token = env_required("GITHUB_TOKEN")
    repo = env_required("GITHUB_REPOSITORY")
    head_sha = env_required("HEAD_SHA")
    event_path = env_required("GITHUB_EVENT_PATH")
    timeout_minutes = int(os.environ.get("TIMEOUT_MINUTES", "20"))
    deadline = time.time() + timeout_minutes * 60

    if not os.path.exists(event_path):
        fail(f"GITHUB_EVENT_PATH does not exist: {event_path}")

    with open(event_path, "r", encoding="utf-8") as f:
        event = json.load(f)
    pr = event.get("pull_request") or {}
    pr_number = pr.get("number")
    if not pr_number:
        fail("not a pull_request event (missing pull_request.number)")

    commits_url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/commits?per_page=250"
    comments_url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments?per_page=250"

    commits = gh_api(commits_url, token)
    latest = commits[-1] if commits else None
    latest_sha = (latest or {}).get("sha")
    if latest_sha and latest_sha != head_sha:
        fail(f"HEAD_SHA mismatch: env={head_sha} api_latest={latest_sha}")
    latest_time = (
        (latest or {}).get("commit", {}).get("committer", {}).get("date")
        or (latest or {}).get("commit", {}).get("author", {}).get("date")
        or ""
    )
    if not latest_time:
        fail("could not determine latest commit timestamp from PR commits API")

    last_state = None
    while time.time() < deadline:
        comments = gh_api(comments_url, token)
        match = None

        for c in comments:
            user = ((c.get("user") or {}).get("login") or "").strip()
            body = c.get("body") or ""
            updated = c.get("updated_at") or c.get("created_at") or ""
            if user not in BOT_LOGINS and "coderabbit" not in user.lower():
                continue
            if "Summary by CodeRabbit" not in body and "coderabbit" not in body.lower():
                continue
            if iso_ge(updated, latest_time):
                match = {"user": user, "updated_at": updated, "latest_commit_at": latest_time}
                break

        state = {
            "pr": pr_number,
            "head_sha": head_sha,
            "latest_commit_at": latest_time,
            "evidence_found": bool(match),
        }
        if state != last_state:
            print("poll:", json.dumps(state, indent=2))
            last_state = state

        if match:
            print("OK: review-agent evidence is current-head aligned:", json.dumps(match))
            return

        time.sleep(10)

    print(
        f"FAIL: no review-agent evidence for current HEAD_SHA within {timeout_minutes} minutes",
        file=sys.stderr,
    )
    print("Last state:", json.dumps(last_state, indent=2), file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
