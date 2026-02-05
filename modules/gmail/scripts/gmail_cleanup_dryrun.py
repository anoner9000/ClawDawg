#!/usr/bin/env python3
"""
gmail_cleanup_dryrun.py

Dry-run: list Gmail messages from specified senders older than N days.

Writes:
 - ~/.openclaw/runtime/logs/mail_cleanup_manifest_YYYY-MM-DD_HHMM.jsonl
 - ~/.openclaw/runtime/logs/mail_cleanup_samples_YYYY-MM-DD_HHMM.txt

Non-destructive: does not modify mailbox or labels.
"""
import os
import json
import argparse
import datetime
import pathlib

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
HOME = os.path.expanduser("~")
RUNTIME = os.path.join(HOME, ".openclaw", "runtime")
LOG_DIR = os.path.join(RUNTIME, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

RUN_STAMP = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d_%H%M")
CREDS_PATH = os.path.join(RUNTIME, "config", "credentials.json")
TOKEN_PATH = pathlib.Path(os.path.join(RUNTIME, "config", "token_readonly.json"))


def auth(debug: bool = False):
    """Gmail API auth with token caching."""
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            if debug:
                print(f"[auth] refreshing token={TOKEN_PATH.name} scopes={SCOPES}")
            creds.refresh(Request())
        else:
            if debug:
                print(f"[auth] starting oauth flow token={TOKEN_PATH.name} scopes={SCOPES}")
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)

        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(creds.to_json())
        try:
            TOKEN_PATH.chmod(0o600)
        except Exception:
            pass

    if debug:
        print(f"[auth] using token={TOKEN_PATH.name} scopes={SCOPES} token_exists={TOKEN_PATH.exists()}")

    return build("gmail", "v1", credentials=creds)


def build_query(senders, days):
    # messages older than N days: before YYYY/MM/DD where date = today - days
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).strftime("%Y/%m/%d")
    senders = [s.strip() for s in senders if s.strip()]
    # Prefer grouped OR: (from:a OR from:b) before:date
    q_senders = " OR ".join([f"from:{s}" for s in senders])
    return f"({q_senders}) before:{cutoff}"


def page_messages(service, user_id, query):
    page_token = None
    while True:
        resp = (
            service.users()
            .messages()
            .list(userId=user_id, q=query, pageToken=page_token, maxResults=500)
            .execute()
        )
        for m in resp.get("messages", []):
            yield m
        page_token = resp.get("nextPageToken")
        if not page_token:
            break


def get_meta(service, user_id, msg_id):
    m = (
        service.users()
        .messages()
        .get(
            userId=user_id,
            id=msg_id,
            format="metadata",
            metadataHeaders=["From", "Subject", "Date"],
        )
        .execute()
    )
    headers = {h["name"]: h["value"] for h in m.get("payload", {}).get("headers", [])}
    return headers


def get_snippet(service, user_id, msg_id):
    m = service.users().messages().get(userId=user_id, id=msg_id, format="full").execute()
    return m.get("snippet", "")


def main():
    p = argparse.ArgumentParser(description="Gmail cleanup dry-run.")
    p.add_argument("--senders", required=True, help="comma-separated senders")
    p.add_argument("--days", type=int, default=180)
    p.add_argument("--samples", type=int, default=20)
    p.add_argument("--debug-auth", action="store_true", help="Print token file + scopes used for auth")
    args = p.parse_args()

    if not os.path.exists(CREDS_PATH):
        raise SystemExit(
            f"credentials.json not found at {CREDS_PATH}; create OAuth client and save it there"
        )

    senders = [s.strip() for s in args.senders.split(",") if s.strip()]
    if not senders:
        raise SystemExit("No senders provided")

    svc = auth(debug=args.debug_auth)
    q = build_query(senders, args.days)

    if args.debug_auth:
        print(f"[query] {q}")
        print(f"[run] stamp={RUN_STAMP} log_dir={LOG_DIR}")

    manifest_path = os.path.join(LOG_DIR, f"mail_cleanup_manifest_{RUN_STAMP}.jsonl")
    samples_path = os.path.join(LOG_DIR, f"mail_cleanup_samples_{RUN_STAMP}.txt")

    count = 0
    samples = []

    with open(manifest_path, "w", encoding="utf-8") as mf:
        for m in page_messages(svc, "me", q):
            hdr = get_meta(svc, "me", m["id"])
            rec = {
                "id": m["id"],
                "from": hdr.get("From", ""),
                "subject": hdr.get("Subject", ""),
                "date": hdr.get("Date", ""),
            }
            mf.write(json.dumps(rec) + "\n")
            count += 1
            if len(samples) < args.samples:
                sn = get_snippet(svc, "me", m["id"])
                samples.append(
                    {"id": m["id"], "from": rec["from"], "subject": rec["subject"], "snippet": sn}
                )

    with open(samples_path, "w", encoding="utf-8") as sf:
        for s in samples:
            sf.write(json.dumps(s) + "\n")

    print(f"dryrun_done rows={count} manifest={manifest_path} samples={samples_path}")


if __name__ == "__main__":
    main()
