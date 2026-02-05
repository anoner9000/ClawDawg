#!/usr/bin/env python3
"""
gmail_cleanup_trash.py
Move messages listed in the quarantine log to Trash (Gmail). Reversible (~30 days in Trash).

Safety features:
- Requires --apply AND exact approval phrase via --confirm TrashApply
- Requires --quarantine-log
- Hard cap with --max (default 200)
- Verifies message has quarantine label before trashing
- Logs every action to <quarantine_log>.trash_log (append)
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
TOKEN_PATH = pathlib.Path(os.path.join(RUNTIME, "config", "token.json"))

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
APPROVAL_PHRASE = "TrashApply"
QUARANTINE_LABEL = "quarantine/cleanup"


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


def get_label_id(service, user_id, label_name):
    resp = service.users().labels().list(userId=user_id).execute()
    for l in resp.get("labels", []):
        if l["name"].lower() == label_name.lower():
            return l["id"]
    return None


def iter_quarantine_log(path):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--quarantine-log", required=True, help="Path to <manifest>.quarantine_log")
    p.add_argument("--confirm", required=True, help="Exact confirmation phrase required to allow trashing")
    p.add_argument("--apply", action="store_true", help="If set, actually move messages to Trash; otherwise dry-run")
    p.add_argument("--max", type=int, default=200, help="Max messages to trash (safety cap)")
    p.add_argument("--sleep", type=float, default=0.05, help="Sleep seconds between operations")
    args = p.parse_args()

    if args.confirm != APPROVAL_PHRASE:
        raise SystemExit("Confirmation phrase incorrect; will not proceed")

    if not os.path.exists(CREDS_PATH):
        raise SystemExit(f"credentials.json not found at {CREDS_PATH}; create OAuth client and save it there")

    entries = []
    for e in iter_quarantine_log(args.quarantine_log):
        if e.get("action") in ("quarantined", "already_quarantined"):
            mid = e.get("id")
            if mid:
                entries.append(e)
        if len(entries) >= args.max:
            break

    if not entries:
        print("No eligible entries found in quarantine log; nothing to trash")
        return

    trash_log_path = args.quarantine_log + ".trash_log"

    if not args.apply:
        print(f"DRY_RUN: Would move {len(entries)} messages to Trash (cap={args.max}). Run with --apply to execute.")
        for e in entries[:20]:
            print(json.dumps({"id": e.get("id"), "from": e.get("from"), "subject": e.get("subject"), "action": e.get("action")}))
        return

    svc = auth()
    q_label_id = get_label_id(svc, "me", QUARANTINE_LABEL)
    if not q_label_id:
        raise SystemExit(f"Quarantine label not found: {QUARANTINE_LABEL}. Run quarantine step first.")

    moved = 0
    with open(trash_log_path, "a", encoding="utf-8") as out:
        for e in entries:
            mid = e.get("id")
            rec = {"id": mid, "time": utc_iso()}

            try:
                msg = svc.users().messages().get(userId="me", id=mid, format="metadata").execute()
                lbls = msg.get("labelIds", [])
                if q_label_id not in lbls:
                    rec["action"] = "skipped_not_quarantined"
                    out.write(json.dumps(rec) + "\n")
                    continue

                svc.users().messages().trash(userId="me", id=mid).execute()
                rec["action"] = "trashed"
                moved += 1
            except Exception as ex:
                rec["action"] = "error"
                rec["error"] = str(ex)

            out.write(json.dumps(rec) + "\n")
            if args.sleep:
                time.sleep(args.sleep)

    print(f"trash_done moved={moved} attempted={len(entries)} cap={args.max} log={trash_log_path}")


if __name__ == "__main__":
    main()
