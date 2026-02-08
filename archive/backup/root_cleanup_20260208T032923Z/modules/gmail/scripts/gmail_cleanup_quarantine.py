#!/usr/bin/env python3
"""
gmail_cleanup_quarantine.py

Reads a manifest JSONL and applies label 'quarantine/cleanup' to each message id listed.

Behavior (INTENTIONAL):
- No caps / no buffers
- Without --apply it prints what it WOULD do (first 20) and exits
- With --apply it:
  - ensures label exists
  - applies the label to every message id in the manifest
  - writes <manifest>.quarantine_log (one JSON per line)

Uses MODIFY token only:
- token file: ~/.openclaw/runtime/config/token_modify.json
- scope: gmail.modify
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


HOME = os.path.expanduser("~")
RUNTIME = os.path.join(HOME, ".openclaw", "runtime")
CREDS_PATH = os.path.join(RUNTIME, "config", "credentials.json")
TOKEN_PATH = pathlib.Path(os.path.join(RUNTIME, "config", "token_modify.json"))

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
LABEL_NAME = "quarantine/cleanup"


def utc_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


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


def ensure_label(service, user_id, label_name):
    resp = service.users().labels().list(userId=user_id).execute()
    for l in resp.get("labels", []):
        if l.get("name", "").lower() == label_name.lower():
            return l["id"]

    body = {
        "name": label_name,
        "labelListVisibility": "labelShow",
        "messageListVisibility": "show",
    }
    lab = service.users().labels().create(userId=user_id, body=body).execute()
    return lab["id"]


def iter_manifest(path):
    with open(path, "r", encoding="utf-8") as mf:
        for line in mf:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True)
    p.add_argument("--apply", action="store_true", help="Actually apply quarantine label")
    args = p.parse_args()

    if not os.path.exists(CREDS_PATH):
        raise SystemExit(f"credentials.json not found at {CREDS_PATH}")

    out_log = args.manifest + ".quarantine_log"

    # ensure output dir exists
    os.makedirs(os.path.dirname(out_log) or ".", exist_ok=True)

    # Dry-run preview
    if not args.apply:
        preview = []
        total = 0
        for obj in iter_manifest(args.manifest):
            total += 1
            if len(preview) < 20:
                preview.append(
                    {
                        "id": obj.get("id"),
                        "from": obj.get("from", ""),
                        "subject": obj.get("subject", ""),
                    }
                )
        print(f"DRY_RUN: would quarantine {total} messages. Use --apply to execute.")
        for row in preview:
            print(json.dumps(row))
        return

    svc = auth()
    label_id = ensure_label(svc, "me", LABEL_NAME)

    processed = 0
    with open(out_log, "w", encoding="utf-8") as out:
        for obj in iter_manifest(args.manifest):
            mid = obj.get("id")
            rec = dict(obj)

            try:
                msg = svc.users().messages().get(userId="me", id=mid, format="minimal").execute()
                lbls = msg.get("labelIds", [])
                if label_id in lbls:
                    rec["action"] = "already_quarantined"
                else:
                    svc.users().messages().modify(
                        userId="me",
                        id=mid,
                        body={"addLabelIds": [label_id]},
                    ).execute()
                    rec["action"] = "quarantined"
            except Exception as e:
                rec["action"] = "error"
                rec["error"] = str(e)

            rec["action_time"] = utc_iso()
            out.write(json.dumps(rec) + "\n")
            processed += 1

    print(f"quarantine_done processed={processed} log={out_log}")


if __name__ == "__main__":
    main()
