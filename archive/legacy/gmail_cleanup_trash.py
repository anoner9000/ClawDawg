#!/usr/bin/env python3
"""
gmail_cleanup_trash.py
Move messages listed in the quarantine log to Trash (Gmail). This is reversible (Gmail keeps in Trash for ~30 days).
Requirements:
 - Only runs after a reviewed manifest + quarantine log exists (operator responsibility)
 - Requires explicit approval phrase: TrashApply
 - Logs every moved message to a .trash_log file alongside the quarantine log
 - No delete calls (uses Gmail 'trash' endpoint only)
Usage:
  python3 gmail_cleanup_trash.py --quarantine-log /path/to/mail_cleanup_manifest_DATE.jsonl.quarantine_log --confirm TrashApply --apply
If --apply is not provided, the script performs a dry-run and prints what it WOULD trash.
"""
import os, json, argparse, datetime
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

HOME = os.path.expanduser('~')
RUNTIME = os.path.join(HOME, '.openclaw', 'runtime')
CREDS_PATH = os.path.join(RUNTIME, 'config', 'credentials.json')
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

APPROVAL_PHRASE = 'TrashApply'


def auth():
    flow = InstalledAppFlow.from_client_secrets_file(CREDS_PATH, SCOPES)
    try:
        creds = flow.run_local_server(host='localhost', port=0)
    except Exception:
        creds = flow.run_console()
    return build('gmail', 'v1', credentials=creds)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--quarantine-log', required=False, help='Path to quarantine log (manifest.quarantine_log). Optional under new policy')
    p.add_argument('--confirm', required=True, help='Exact confirmation phrase required to allow trashing')
    p.add_argument('--apply', action='store_true', help='If set, actually move messages to Trash; otherwise dry-run')
    args = p.parse_args()

    # Policy change: allow TrashApply without path if policy file updated
    policy_file='playbooks/deiphobe_gmail_trash_protocol.md'
    policy_ok=False
    if Path(policy_file).exists():
        policy_ok=True
    if args.confirm != APPROVAL_PHRASE and not (args.confirm=='TrashApply' and policy_ok):
        raise SystemExit('Confirmation phrase incorrect; will not proceed')
        raise SystemExit('Confirmation phrase incorrect; will not proceed')

    if not os.path.exists(CREDS_PATH):
        raise SystemExit(f'credentials.json not found at {CREDS_PATH}; create OAuth client and save it there')

    # Load quarantine log entries
    with open(args.quarantine_log) as f:
        entries = [json.loads(l) for l in f if l.strip()]

    if not entries:
        print('No entries found in quarantine log; nothing to trash')
        return

    trash_log_path = args.quarantine_log + '.trash_log'

    if not args.apply:
        print(f'DRY_RUN: Would move {len(entries)} messages to Trash. Run with --apply to execute.')
        for e in entries[:20]:
            print(json.dumps({'id': e.get('id'), 'from': e.get('from'), 'subject': e.get('subject')}))
        return

    svc = auth()

    with open(trash_log_path, 'a') as out:
        for e in entries:
            mid = e.get('id')
            try:
                svc.users().messages().trash(userId='me', id=mid).execute()
                rec = {'id': mid, 'action': 'trashed', 'time': datetime.datetime.utcnow().isoformat()}
            except Exception as ex:
                rec = {'id': mid, 'action': 'error', 'error': str(ex), 'time': datetime.datetime.utcnow().isoformat()}
            out.write(json.dumps(rec) + '\n')
    print(f'trash_done log={trash_log_path}')


if __name__ == '__main__':
    main()
