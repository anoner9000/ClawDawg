#!/usr/bin/env python3
"""
Canonical CodeRabbit rerun requester with SHA dedupe.

Behavior:
- If CodeRabbit evidence is already success on HEAD_SHA: do nothing.
- Else: check PR issue comments for marker + sha:<HEAD_SHA>.
  - If already present: do nothing.
  - Else: post a single rerun request comment.

Requires env:
- GITHUB_TOKEN
- GITHUB_REPOSITORY (owner/repo)
- PR_NUMBER
- HEAD_SHA
Optional:
- CODERABBIT_MENTION (default: @coderabbitai)
- TIMEOUT_MINUTES (unused here; waiting is handled elsewhere)
"""

import json
import os
import socket
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse


MARKER = "<!-- coderabbit-auto-rerun -->"


def die(msg: str, code: int = 2) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def gh_api(
    method: str,
    url: str,
    token: str,
    body: dict | None = None,
    timeout_secs: int = 15,
) -> dict:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        die(f"{method} {url} failed: unsupported URL scheme {parsed.scheme!r}", code=3)

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "clawdawg-code-factory",
    }
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout_secs) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except HTTPError as e:
        raw = e.read().decode("utf-8") if e.fp else ""
        die(f"{method} {url} failed: HTTP {e.code} {raw}", code=3)
    except socket.timeout:
        die(f"{method} {url} failed: timeout after {timeout_secs}s", code=3)
    except URLError as e:
        # Some timeouts surface as URLError(reason=timeout/TimeoutError)
        reason = getattr(e, "reason", None)
        if isinstance(reason, (socket.timeout, TimeoutError)):
            die(f"{method} {url} failed: timeout after {timeout_secs}s", code=3)
        die(f"{method} {url} failed: {e}", code=3)


def coderabbit_evidence_ok(token: str, repo: str, sha: str) -> bool:
    api = "https://api.github.com"
    # 1) Commit status contexts (what you observed earlier)
    status = gh_api("GET", f"{api}/repos/{repo}/commits/{sha}/status", token)
    for st in status.get("statuses", []):
        if (st.get("context") or "") == "CodeRabbit" and st.get("state") == "success":
            return True

    # 2) Check-runs (some installs use check-runs instead)
    checks = gh_api("GET", f"{api}/repos/{repo}/commits/{sha}/check-runs", token)
    for cr in checks.get("check_runs", []):
        name = (cr.get("name") or "").lower()
        app = ((cr.get("app") or {}).get("slug") or "").lower()
        if "coderabbit" in name or app in ("coderabbitai", "coderabbit"):
            if cr.get("status") == "completed" and cr.get("conclusion") == "success":
                return True

    return False


def list_issue_comments(token: str, repo: str, pr_number: str) -> list[dict]:
    api = "https://api.github.com"
    comments: list[dict] = []
    page = 1
    while True:
        url = f"{api}/repos/{repo}/issues/{pr_number}/comments?per_page=100&page={page}"
        batch = gh_api("GET", url, token)
        if not isinstance(batch, list):
            break
        comments.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return comments


def post_comment(token: str, repo: str, pr_number: str, body: str) -> None:
    api = "https://api.github.com"
    gh_api("POST", f"{api}/repos/{repo}/issues/{pr_number}/comments", token, {"body": body})


def main() -> None:
    token = os.environ.get("GITHUB_TOKEN") or ""
    repo = os.environ.get("GITHUB_REPOSITORY") or ""
    pr_number = os.environ.get("PR_NUMBER") or ""
    head_sha = os.environ.get("HEAD_SHA") or ""
    mention = os.environ.get("CODERABBIT_MENTION") or "@coderabbitai"

    if not token:
        die("GITHUB_TOKEN is required", 2)
    if not repo:
        die("GITHUB_REPOSITORY is required", 2)
    if not pr_number:
        die("PR_NUMBER is required", 2)
    if not head_sha:
        die("HEAD_SHA is required", 2)

    # If evidence already good, do nothing.
    if coderabbit_evidence_ok(token, repo, head_sha):
        print("OK: CodeRabbit evidence already present on HEAD_SHA; no rerun needed.")
        return

    trigger = f"sha:{head_sha}"
    comments = list_issue_comments(token, repo, pr_number)

    already = False
    for c in comments:
        body = c.get("body") or ""
        if MARKER in body and trigger in body:
            already = True
            break

    if already:
        print("OK: rerun already requested for this HEAD_SHA (dedup hit).")
        return

    # Canonical rerun request comment.
    body = (
        f"{MARKER}\n"
        f"{mention} please re-review this PR head.\n"
        f"{trigger}\n"
    )
    post_comment(token, repo, pr_number, body)
    print("OK: posted canonical CodeRabbit rerun request.")


if __name__ == "__main__":
    main()
