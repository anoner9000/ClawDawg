#!/usr/bin/env python3
"""
gmail_cleanup_quarantine.py
Reads manifest JSONL and applies label 'quarantine/cleanup' to each message id listed.

Safe defaults:
- Without --apply it only prints what it would do.
- Adds a hard cap via --max (default 500).
- Writes an audit log: <manifest>.quarantine_log
"""
import os
import json
import argparse
import datetime
import pathlib
import time

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
    """Gmail API auth with token caching."""
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
        if l["name"].lower() == label_name.lower():
            return l["id"]
    body = {"name": label_name, "labelListVisibility": "labelShow", "messageListVisibility": "show"}
    lab = service.users().labels().create(userId=user_id, body=body).execute()
    return lab["id"]


def iter_manifest(path):
    with open(path, "r", encoding="utf-8") as mf:
        for line in mf:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True)
    p.add_argument("--apply", action="store_true", help="If set, perform quarantine (otherwise dry-run)")
    p.add_argument("--max", type=int, default=500, help="Max messages to process (safety cap)")
    p.add_argument("--sleep", type=float, default=0.05, help="Sleep seconds between operations")
    args = p.parse_args()

    if not os.path.exists(CREDS_PATH):
        raise SystemExit(f"credentials.json not found at {CREDS_PATH}; create OAuth client and save it there")

    out_manifest = args.manifest + ".quarantine_log"

    if not args.apply:
        sample = []
        n = 0
        for obj in iter_manifest(args.manifest):
            n += 1
            if len(sample) < 20:
                sample.append({"id": obj.get("id"), "from": obj.get("from"), "subject": obj.get("subject")})
            if n >= args.max:
                break
        print(f"DRY_RUN: would process up to {min(n, args.max)} messages (cap={args.max}); use --apply to execute")
        for s in sample:
            print(json.dumps(s))
        return

    svc = auth()
    label_id = ensure_label(svc, "me", LABEL_NAME)

    processed = 0
    with open(out_manifest, "w", encoding="utf-8") as out:
        for obj in iter_manifest(args.manifest):
            if processed >= args.max:
                break

            mid = obj.get("id")
            if not mid:
                continue

            try:
                msg = svc.users().messages().get(userId="me", id=mid, format="metadata").execute()
                lbls = msg.get("labelIds", [])
                if label_id in lbls:
                    obj["action"] = "already_quarantined"
                    obj["action_time"] = utc_iso()
                    out.write(json.dumps(obj) + "\n")
                    processed += 1
                    continue

                svc.users().messages().modify(userId="me", id=mid, body={"addLabelIds": [label_id]}).execute()
                obj["action"] = "quarantined"
                obj["action_time"] = utc_iso()
            except Exception as e:
                obj["action"] = "error"
                obj["error"] = str(e)
                obj["action_time"] = utc_iso()

            out.write(json.dumps(obj) + "\n")
            processed += 1
            if args.sleep:
                time.sleep(args.sleep)

    print(f"quarantine_done processed={processed} cap={args.max} log={out_manifest}")


if __name__ == "__main__":
    main()
