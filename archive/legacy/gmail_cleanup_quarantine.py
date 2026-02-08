#!/usr/bin/env python3
import pathlib
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
"""
gmail_cleanup_quarantine.py
Reads manifest JSONL and applies label 'quarantine/cleanup' to each message id listed.
Idempotent and safe: without --apply it will only print what it would do.
"""
import os, json, argparse, datetime, pathlib
import sys
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

HOME = os.path.expanduser('~')
RUNTIME = os.path.join(HOME, '.openclaw', 'runtime')
CREDS_PATH = os.path.join(RUNTIME, 'config', 'credentials.json')
TOKEN_PATH = pathlib.Path(os.path.join(RUNTIME, 'config', 'token.json'))

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

RUN_STAMP = datetime.datetime.now().strftime('%Y-%m-%d_%H%M')

LOG_DIR = os.path.join(RUNTIME, 'logs')
LABEL_NAME = 'quarantine/cleanup'


def auth():
    """Gmail API auth with token caching."""
    creds = None

    # Load cached token if present
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    # Refresh or re-auth if needed
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)

        # Save token for next run
        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(creds.to_json())
        try:
            TOKEN_PATH.chmod(0o600)
        except Exception:
            pass

    return build("gmail", "v1", credentials=creds)
def ensure_label(service, user_id, label_name):
    resp = service.users().labels().list(userId=user_id).execute()
    for l in resp.get('labels', []):
        if l['name'].lower() == label_name.lower():
            return l['id']
    body = {'name': label_name, 'labelListVisibility': 'labelShow', 'messageListVisibility': 'show'}
    lab = service.users().labels().create(userId=user_id, body=body).execute()
    return lab['id']


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--manifest', required=True)
    p.add_argument('--apply', action='store_true', help='If set, perform the quarantine (otherwise dry-run)')
    args = p.parse_args()
    if not os.path.exists(CREDS_PATH):
        raise SystemExit(f'credentials.json not found at {CREDS_PATH}; create OAuth client and save it there')
    svc = auth()
    label_id = ensure_label(svc, 'me', LABEL_NAME)
    out_manifest = args.manifest + '.quarantine_log'
    manifest = []
    with open(args.manifest) as mf:
        for line in mf:
            if not line.strip(): continue
            manifest.append(json.loads(line))
    # Dry-run: show what we'd do
    if not args.apply:
        print(f"DRY_RUN: would process {len(manifest)} messages; use --apply to execute")
        # print first 20 as sample
        for m in manifest[:20]:
            print(json.dumps({'id':m.get('id'),'from':m.get('from'),'subject':m.get('subject')}))
        return
    # Apply mode: idempotent
    with open(out_manifest, 'w') as out:
        for obj in manifest:
            mid = obj.get('id')
            # check if already quarantined via labels
            try:
                msg = svc.users().messages().get(userId='me', id=mid, format='metadata', metadataHeaders=[]).execute()
                lbls = msg.get('labelIds',[])
                if label_id in lbls:
                    obj['action'] = 'already_quarantined'
                    obj['action_time'] = datetime.datetime.utcnow().isoformat()
                    out.write(json.dumps(obj)+"\n")
                    continue
                # apply label
                svc.users().messages().modify(userId='me', id=mid, body={'addLabelIds':[label_id]}).execute()
                obj['action'] = 'quarantined'
                obj['action_time'] = datetime.datetime.utcnow().isoformat()
            except Exception as e:
                obj['action']='error'
                obj['error']=str(e)
            out.write(json.dumps(obj)+"\n")
    print(f'quarantine_done log={out_manifest}')


if __name__=='__main__':
    main()
