#!/usr/bin/env python3
import pathlib
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
"""
gmail_cleanup_dryrun.py
Dry-run: list Gmail messages from specified senders older than N days.
Writes:
 - ~/.openclaw/runtime/logs/mail_cleanup_manifest_YYYY-MM-DD.jsonl
 - ~/.openclaw/runtime/logs/mail_cleanup_samples_YYYY-MM-DD.txt
Non-destructive: does not modify mailbox or labels.
"""
import os, json, datetime, argparse, pathlib
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
HOME = os.path.expanduser("~")
RUNTIME = os.path.join(HOME, ".openclaw", "runtime")
LOG_DIR = os.path.join(RUNTIME, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
RUN_STAMP = datetime.datetime.now().strftime('%Y-%m-%d_%H%M')

CREDS_PATH = os.path.join(RUNTIME, "config", "credentials.json")
TOKEN_PATH = pathlib.Path(os.path.join(RUNTIME, 'config', 'token.json'))



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
def build_query(senders, days):
    after_date = (datetime.date.today() - datetime.timedelta(days=days)).strftime("%Y/%m/%d")
    q_senders = " OR ".join(["from:{}".format(s) for s in senders])
    q = f"({q_senders}) before:{after_date}"
    return q


def page_messages(service, user_id, query):
    page_token = None
    while True:
        resp = service.users().messages().list(userId=user_id, q=query, pageToken=page_token, maxResults=500).execute()
        for m in resp.get('messages', []):
            yield m
        page_token = resp.get('nextPageToken')
        if not page_token:
            break


def get_meta(service, user_id, msg_id):
    m = service.users().messages().get(userId=user_id, id=msg_id, format='metadata', metadataHeaders=['From','Subject','Date']).execute()
    headers = {h['name']:h['value'] for h in m.get('payload',{}).get('headers',[])}
    return headers


def get_snippet(service, user_id, msg_id):
    m = service.users().messages().get(userId=user_id, id=msg_id, format='full').execute()
    sn = m.get('snippet','')
    return sn


def main():
    p = argparse.ArgumentParser(description='Gmail cleanup dry-run. Example senders: newsletter@example.com,news@lists.example.org')
    p.add_argument('--senders', required=True, help='comma-separated senders')
    p.add_argument('--days', type=int, default=180)
    p.add_argument('--samples', type=int, default=20)
    args = p.parse_args()
    senders = [s.strip() for s in args.senders.split(',') if s.strip()]
    if not os.path.exists(CREDS_PATH):
        raise SystemExit(f'credentials.json not found at {CREDS_PATH}; create OAuth client and save it there')
    svc = auth()
    q = build_query(senders, args.days)
    manifest_path = os.path.join(LOG_DIR, f'mail_cleanup_manifest_{RUN_STAMP}.jsonl')
    samples_path = os.path.join(LOG_DIR, f'mail_cleanup_samples_{RUN_STAMP}.txt')
    count = 0
    samples = []
    with open(manifest_path, 'w') as mf:
        for m in page_messages(svc, 'me', q):
            hdr = get_meta(svc, 'me', m['id'])
            rec = {'id': m['id'], 'from': hdr.get('From',''), 'subject': hdr.get('Subject',''), 'date': hdr.get('Date','')}
            mf.write(json.dumps(rec) + "\n")
            count += 1
            if len(samples) < args.samples:
                sn = get_snippet(svc, 'me', m['id'])
                samples.append({'id': m['id'], 'from': rec['from'], 'subject': rec['subject'], 'snippet': sn})
    with open(samples_path, 'w') as sf:
        for s in samples:
            sf.write(json.dumps(s) + "\n")
    print(f"dryrun_done rows={count} manifest={manifest_path} samples={samples_path}")


if __name__=='__main__':
    main()
