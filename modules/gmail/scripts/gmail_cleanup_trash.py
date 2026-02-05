#!/usr/bin/env python3
"""
gmail_cleanup_trash.py

Moves messages listed in a quarantine_log to Trash.

Behavior (INTENTIONAL):
- No caps / no buffers
- Requires --apply AND exact --confirm TrashApply
- Only trashes entries that were actually quarantined (action == quarantined or already_quarantined)
- Logs every action to <quarantine_log>.trash_log (append)

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
APPROVAL_PHRASE = "TrashApply"


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


def iter_quarantine_log(path):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def is_eligible(entry):
    # Only trash things we actually labeled (or were already labeled).
    return entry.get("action") in ("quarantined", "already_quarantined")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--quarantine-log", required=True)
    p.add_argument("--confirm", required=True)
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()

    if args.confirm != APPROVAL_PHRASE:
        raise SystemExit("Confirmation phrase incorrect; will not proceed")

    if not os.path.exists(CREDS_PATH):
        raise SystemExit(f"credentials.json not found at {CREDS_PATH}")

    eligible = [e for e in iter_quarantine_log(args.quarantine_log) if is_eligible(e)]

    if not eligible:
        print("No eligible entries found in quarantine log; nothing to trash")
        return

    trash_log_path = args.quarantine_log + ".trash_log"
    os.makedirs(os.path.dirname(trash_log_path) or ".", exist_ok=True)

    if not args.apply:
        print(f"DRY_RUN: would trash {len(eligible)} messages. Use --apply to execute.")
        for e in eligible[:20]:
            print(json.dumps({"id": e.get("id"), "from": e.get("from", ""), "subject": e.get("subject", "")}))
        return

    svc = auth()

    moved = 0
    with open(trash_log_path, "a", encoding="utf-8") as out:
        for e in eligible:
            mid = e.get("id")
            rec = {"id": mid, "time": utc_iso()}

            try:
                svc.users().messages().trash(userId="me", id=mid).execute()
                rec["action"] = "trashed"
                moved += 1
            except Exception as ex:
                rec["action"] = "error"
                rec["error"] = str(ex)

            out.write(json.dumps(rec) + "\n")

    print(f"trash_done moved={moved} attempted={len(eligible)} log={trash_log_path}")


if __name__ == "__main__":
    main()
