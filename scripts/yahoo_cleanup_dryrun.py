#!/usr/bin/env python3
import argparse, json, re, ssl, datetime
import imaplib
from pathlib import Path
from email import message_from_bytes
from email.utils import parsedate_to_datetime, parseaddr
from email.header import decode_header, make_header

def decode_str(v) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    try:
        return str(make_header(decode_header(v)))
    except Exception:
        return str(v)

def read_one_line(p: Path) -> str:
    s = p.read_text(encoding="utf-8", errors="replace").strip()
    if not s:
        raise SystemExit(f"Empty credential file: {p}")
    return s

def load_cfg(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip().lower()

def within_lookback(msg_dt: datetime.datetime, lookback_days: int) -> bool:
    # msg_dt can be naive or tz-aware
    now = datetime.datetime.now(datetime.UTC)
    if msg_dt.tzinfo is None:
        msg_dt = msg_dt.replace(tzinfo=datetime.UTC)
    return msg_dt >= (now - datetime.timedelta(days=lookback_days))

def match_rule(frm: str, subj: str, rule: dict) -> bool:
    frm_l = normalize(frm)
    subj_l = normalize(subj)
    from_list = [normalize(x) for x in rule.get("from", [])]
    subj_contains = [normalize(x) for x in rule.get("subject_contains", [])]
    if from_list and (frm_l not in from_list):
        return False
    if subj_contains and not any(k in subj_l for k in subj_contains):
        return False
    return True

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--manifest", required=True)
    args = ap.parse_args()

    cfg = load_cfg(Path(args.config))
    lookback_days = int(cfg.get("lookback_days", 30))
    mailbox = cfg.get("mailbox", "INBOX")
    rules = cfg.get("rules", [])
    if not rules:
        print("No rules configured; exiting.")
        Path(args.manifest).write_text("", encoding="utf-8")
        return

    runtime = Path.home()/".openclaw/runtime"
    email = read_one_line(runtime/"credentials/yahoo_email")
    app  = read_one_line(runtime/"credentials/yahoo_app_password")

    M = imaplib.IMAP4_SSL("imap.mail.yahoo.com", 993, ssl_context=ssl.create_default_context())
    M.login(email, app)
    try:
        typ, _ = M.select(mailbox, readonly=True)
        if typ != "OK":
            raise RuntimeError(f"select {mailbox} failed: {typ}")

        # Yahoo IMAP date search is coarse; we still do lookback check after fetching headers
        since = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=lookback_days)).date()
        since_str = since.strftime("%d-%b-%Y")  # IMAP date format
        typ, data = M.search(None, "SINCE", since_str)
        if typ != "OK":
            raise RuntimeError(f"search SINCE failed: {typ}")
        ids = data[0].split() if data and data[0] else []

        out = Path(args.manifest)
        out.parent.mkdir(parents=True, exist_ok=True)

        matched = 0
        with out.open("w", encoding="utf-8") as f:
            for mid in ids:
                # Fetch only headers to decide
                typ, dat = M.fetch(mid, "(BODY.PEEK[HEADER])")
                if typ != "OK" or not dat:
                    continue
                hb = None
                for it in dat:
                    if isinstance(it, tuple) and isinstance(it[1], (bytes, bytearray)):
                        hb = bytes(it[1])
                        break
                if not hb:
                    continue

                msg = message_from_bytes(hb)
                frm = parseaddr(msg.get("From") or "")[1]
                subj = decode_str(msg.get("Subject"))
                dt_raw = msg.get("Date")
                try:
                    msg_dt = parsedate_to_datetime(dt_raw) if dt_raw else None
                except Exception:
                    msg_dt = None

                if msg_dt and not within_lookback(msg_dt, lookback_days):
                    continue

                # Decide action based on first matching rule
                action = None
                rule_name = None
                for r in rules:
                    if match_rule(frm, subj, r):
                        action = r.get("action", "quarantine")
                        rule_name = r.get("name", "rule")
                        break
                if not action:
                    continue

                rec = {
                    "ts_utc": datetime.datetime.now(datetime.UTC).isoformat(),
                    "mailbox": mailbox,
                    "msg_id": mid.decode(errors="ignore"),
                    "from": frm,
                    "subject": subj,
                    "date": dt_raw,
                    "rule": rule_name,
                    "action": action,
                }
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                matched += 1

        print(f"Dryrun complete: scanned={len(ids)} matched={matched} manifest={out}")
    finally:
        try: M.logout()
        except Exception: pass

if __name__ == "__main__":
    main()
