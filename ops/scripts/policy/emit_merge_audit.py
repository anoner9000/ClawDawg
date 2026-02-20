#!/usr/bin/env python3
"""
emit_merge_audit.py

Writes a structured "merge audit" record (JSON + optional JSONL append) for Code Factory.
Intended to run in GitHub Actions.

Inputs are taken from env vars (preferred) and CLI flags.

Typical fields:
- timestamp (UTC)
- repo
- pr_number
- head_sha
- riskTier
- policyVersion
- actor
- workflow/run identifiers
- mergeMethod (what we requested)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def die(msg: str, code: int = 2) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def _getenv(name: str, default: str = "") -> str:
    v = os.environ.get(name)
    return v if v is not None else default


def utc_now_iso() -> str:
    # RFC3339-ish with Z suffix
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def append_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(content)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=_getenv("GITHUB_REPOSITORY"))
    ap.add_argument("--pr-number", default=_getenv("PR_NUMBER") or _getenv("GITHUB_PR_NUMBER"))
    ap.add_argument("--head-sha", default=_getenv("HEAD_SHA") or _getenv("GITHUB_SHA"))
    ap.add_argument("--risk-tier", default=_getenv("RISK_TIER"))
    ap.add_argument("--policy-version", default=_getenv("POLICY_VERSION"))
    ap.add_argument("--merge-method", default=_getenv("MERGE_METHOD", "SQUASH"))
    ap.add_argument("--actor", default=_getenv("GITHUB_ACTOR"))
    ap.add_argument("--run-id", default=_getenv("GITHUB_RUN_ID"))
    ap.add_argument("--run-attempt", default=_getenv("GITHUB_RUN_ATTEMPT"))
    ap.add_argument("--workflow", default=_getenv("GITHUB_WORKFLOW"))
    ap.add_argument("--event-name", default=_getenv("GITHUB_EVENT_NAME"))

    ap.add_argument("--out-json", default="")
    ap.add_argument("--append-jsonl", default="")
    ap.add_argument("--out-summary", default="")

    args = ap.parse_args()

    if not args.repo:
        die("repo is required (set GITHUB_REPOSITORY or pass --repo)")
    if not args.pr_number:
        die("pr-number is required (set PR_NUMBER or pass --pr-number)")
    if not args.head_sha:
        die("head-sha is required (set HEAD_SHA/GITHUB_SHA or pass --head-sha)")
    if not args.risk_tier:
        die("risk-tier is required (set RISK_TIER or pass --risk-tier)")
    if args.policy_version == "":
        # allow unknown policyVersion, but keep it explicit
        args.policy_version = "unknown"

    record: dict[str, Any] = {
        "timestamp": utc_now_iso(),
        "repo": args.repo,
        "prNumber": int(args.pr_number),
        "headSha": args.head_sha,
        "riskTier": args.risk_tier,
        "policyVersion": args.policy_version if args.policy_version == "unknown" else int(args.policy_version),
        "actor": args.actor or "unknown",
        "mergeMethod": args.merge_method,
        "workflow": args.workflow or "unknown",
        "eventName": args.event_name or "unknown",
        "runId": args.run_id or "unknown",
        "runAttempt": args.run_attempt or "unknown",
    }

    payload = json.dumps(record, sort_keys=True)

    if args.out_json:
        write_text(Path(args.out_json), payload + "\n")

    if args.append_jsonl:
        append_text(Path(args.append_jsonl), payload + "\n")

    if args.out_summary:
        # Markdown summary
        md = (
            "### Code Factory — Merge audit record\n\n"
            f"- repo: `{record['repo']}`\n"
            f"- PR: `#{record['prNumber']}`\n"
            f"- headSha: `{record['headSha']}`\n"
            f"- riskTier: `{record['riskTier']}`\n"
            f"- policyVersion: `{record['policyVersion']}`\n"
            f"- mergeMethod: `{record['mergeMethod']}`\n"
            f"- actor: `{record['actor']}`\n"
            f"- run: `{record['runId']}` (attempt `{record['runAttempt']}`)\n"
            f"- timestamp: `{record['timestamp']}`\n"
        )
        append_text(Path(args.out_summary), md)

    print(payload)


if __name__ == "__main__":
    main()
