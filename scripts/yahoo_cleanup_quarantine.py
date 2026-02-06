#!/usr/bin/env python3
import argparse, json, ssl
import imaplib
from pathlib import Path
import datetime

def read_one_line(p: Path) -> str:
    s = p.read_text(encoding="utf-8", errors="replace").strip()
    if not s:
        raise SystemExit(f"Empty credential file: {p}")
    return s

def ensure_mailbox(M, name: str):
    # create if missing
    typ, _ = M.create(name)
    # OK if already exists on many servers; ignore failures

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    manifest = Path(args.manifest)
    if not manifest.exists() or manifest.stat().st_size == 0:
        print("No manifest entries.")
        return

    cfg_path = Path.home()/".openclaw/runtime/config/yahoo_cleanup_rules.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    mailbox = cfg.get("mailbox", "INBOX")
    qbox = cfg.get("quarantine_mailbox", "OpenClaw/Quarantine")

    runtime = Path.home()/".openclaw/runtime"
    email = read_one_line(runtime/"credentials/yahoo_email")
    app  = read_one_line(runtime/"credentials/yahoo_app_password")

    M = imaplib.IMAP4_SSL("imap.mail.yahoo.com", 993, ssl_context=ssl.create_default_context())
    M.login(email, app)
    try:
        ensure_mailbox(M, qbox)
        typ, _ = M.select(mailbox, readonly=not args.apply)
        if typ != "OK":
            raise RuntimeError(f"select {mailbox} failed")

        qlog = Path(str(manifest) + ".quarantine_log")
        with manifest.open("r", encoding="utf-8") as src, qlog.open("w", encoding="utf-8") as out:
            for line in src:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                mid = rec["msg_id"].encode()

                if not args.apply:
                    rec["result"] = "dryrun"
                    out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    continue

                # COPY to quarantine then mark deleted in source + expunge later
                typ, _ = M.copy(mid, qbox)
                if typ != "OK":
                    rec["result"] = "copy_failed"
                    out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    continue

                M.store(mid, "+FLAGS", r"(\Deleted)")
                rec["result"] = "quarantined"
                rec["quarantine_mailbox"] = qbox
                rec["applied_ts_utc"] = datetime.datetime.now(datetime.UTC).isoformat()
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")

            if args.apply:
                M.expunge()

        print(f"Quarantine complete. log={qlog}")
    finally:
        try: M.logout()
        except Exception: pass

if __name__ == "__main__":
    main()
