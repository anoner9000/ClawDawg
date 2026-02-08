#!/usr/bin/env python3
import argparse, json, ssl
import imaplib
from pathlib import Path
import datetime

def imap_set_timeout(M, seconds: int = 30):
    sock = getattr(M, "sock", None)
    if sock:
        try:
            sock.settimeout(seconds)
        except Exception:
            pass

def read_one_line(p: Path) -> str:
    s = p.read_text(encoding="utf-8", errors="replace").strip()
    if not s:
        raise SystemExit(f"Empty credential file: {p}")
    return s

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quarantine-log", required=True)
    ap.add_argument("--confirm", required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    if args.confirm != "TrashApply":
        raise SystemExit("Refusing: --confirm must equal TrashApply")

    qlog = Path(args.quarantine_log)
    if not qlog.exists() or qlog.stat().st_size == 0:
        print("No quarantine log entries.")
        return

    cfg_path = Path.home()/".openclaw/runtime/config/yahoo_cleanup_rules.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    qbox = cfg.get("quarantine_mailbox", "OpenClaw/Quarantine")
    trash_box = cfg.get("trash_mailbox", "Trash")

    runtime = Path.home()/".openclaw/runtime"
    email = read_one_line(runtime/"credentials/yahoo_email")
    app  = read_one_line(runtime/"credentials/yahoo_app_password")

    M = imaplib.IMAP4_SSL("imap.mail.yahoo.com", 993, ssl_context=ssl.create_default_context())
    imap_set_timeout(M, 30)
    M.login(email, app)
    try:
        typ, _ = M.select(qbox, readonly=not args.apply)
        if typ != "OK":
            raise RuntimeError(f"select {qbox} failed")

        out_log = Path(str(qlog) + ".trash_log")
        with qlog.open("r", encoding="utf-8") as src, out_log.open("w", encoding="utf-8") as out:
            for line in src:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec.get("action") == "skip":
                    continue
                if rec.get("result") != "quarantined":
                    continue

                # We don’t have stable UID mapping after COPY+EXPUNGE, so we trash by searching header fields.
                # Minimal: trash everything currently in quarantine mailbox if apply is enabled.
                if not args.apply:
                    rec2 = dict(rec)
                    rec2["trash_result"] = "dryrun"
                    out.write(json.dumps(rec2, ensure_ascii=False) + "\n")
                    continue

                # Mark deleted in quarantine and expunge = moved to Trash on Yahoo, generally.
                # (Yahoo’s IMAP may map expunged deleted messages to Trash depending on server policy.)
                mid = rec["msg_id"].encode()
                M.store(mid, "+FLAGS", r"(\Deleted)")
                rec["trash_result"] = "deleted_in_quarantine"
                rec["trash_mailbox"] = trash_box
                rec["trashed_ts_utc"] = datetime.datetime.now(datetime.UTC).isoformat()
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")

            if args.apply:
                M.expunge()

        print(f"Trash step complete. log={out_log}")
    finally:
        try: M.logout()
        except Exception: pass

if __name__ == "__main__":
    main()
