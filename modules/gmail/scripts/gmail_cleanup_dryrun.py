#!/usr/bin/env python3
"""
gmail_cleanup_dryrun.py

Dry-run: list Gmail messages from specified senders older than N days.

Behavior (INTENTIONAL):
- Searches in:anywhere so messages are found regardless of location
- EXCLUDES Trash to avoid infinite reprocessing loops
- EXCLUDES messages already labeled quarantine/cleanup
- READ-ONLY access only (gmail.readonly)

Writes:
 - ~/.openclaw/runtime/logs/mail_cleanup_manifest_YYYY-MM-DD_HHMM.jsonl
 - ~/.openclaw/runtime/logs/mail_cleanup_samples_YYYY-MM-DD_HHMM.txt
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


# --------------------
# Config
# --------------------

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

HOME = os.path.expanduser("~")
RUNTIME = os.path.join(HOME, ".openclaw", "runtime")
LOG_DIR = os.path.join(RUNTIME, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

CREDS_PATH = os.path.join(RUNTIME, "config", "credentials.json")
TOKEN_PATH = pathlib.Path(os.path.join(RUNTIME, "config", "token_readonly.json"))

RUN_STAMP = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d_%H%M")


# --------------------
# Auth
# --------------------

def auth():
    creds = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)

        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(creds.to_json())
        try:
            TOKEN_PATH.chmod(0o600)
        except Exception:
            pass

    return build("gmail", "v1", credentials=creds)


# --------------------
# Query construction
# --------------------

def build_query(senders, days):
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).strftime("%Y/%m/%d")
    senders = [s.strip() for s in senders if s.strip()]

    sender_clause = " OR ".join([f"from:{s}" for s in senders])

    # IMPORTANT:
    # - in:anywhere catches Inbox / All Mail / Archive
    # - -in:trash prevents infinite loops
    # - -label:quarantine/cleanup prevents reprocessing
    return (
        f"({sender_clause}) "
        f"in:anywhere "
        f"-in:trash "
        f"-label:quarantine/cleanup "
        f"before:{cutoff}"
    )


# --------------------
# Gmail helpers
# --------------------

def page_messages(service, user_id, query):
    page_token = None
    while True:
        resp = (
            service.users()
            .messages()
            .list(
                userId=user_id,
                q=query,
                pageToken=page_token,
                maxResults=500,
            )
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
    m = service.users().messages().get(
        userId=user_id,
        id=msg_id,
        format="full",
    ).execute()
    return m.get("snippet", "")


# --------------------
# Main
# --------------------

def main():
    p = argparse.ArgumentParser(description="Gmail cleanup dry-run")
    p.add_argument("--senders", required=True, help="comma-separated senders")
    p.add_argument("--days", type=int, default=180)
    p.add_argument("--samples", type=int, default=20)
    args = p.parse_args()

    if not os.path.exists(CREDS_PATH):
        raise SystemExit(f"credentials.json not found at {CREDS_PATH}")

    senders = [s.strip() for s in args.senders.split(",") if s.strip()]
    if not senders:
        raise SystemExit("No senders provided")

    svc = auth()
    query = build_query(senders, args.days)

    manifest_path = os.path.join(
        LOG_DIR, f"mail_cleanup_manifest_{RUN_STAMP}.jsonl"
    )
    samples_path = os.path.join(
        LOG_DIR, f"mail_cleanup_samples_{RUN_STAMP}.txt"
    )

    count = 0
    samples = []

    with open(manifest_path, "w", encoding="utf-8") as mf:
        for m in page_messages(svc, "me", query):
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
                    {
                        "id": m["id"],
                        "from": rec["from"],
                        "subject": rec["subject"],
                        "snippet": sn,
                    }
                )

    with open(samples_path, "w", encoding="utf-8") as sf:
        for s in samples:
            sf.write(json.dumps(s) + "\n")

    print(
        f"dryrun_done rows={count} "
        f"manifest={manifest_path} "
        f"samples={samples_path}"
    )


if __name__ == "__main__":
    main()
