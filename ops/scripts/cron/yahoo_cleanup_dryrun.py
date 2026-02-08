#!/usr/bin/env python3
import argparse, json, re, ssl, datetime
import imaplib
import socket
from pathlib import Path
from email import message_from_bytes
from email.utils import parsedate_to_datetime, parseaddr
from email.header import decode_header, make_header

def imap_set_timeout(M, seconds: int = 20):
    sock = getattr(M, "sock", None)
    if sock:
        try:
            sock.settimeout(seconds)
        except Exception:
            pass
    # global default for any new sockets created underneath
    try:
        socket.setdefaulttimeout(seconds)
    except Exception:
        pass

def safe_imap_call(desc: str, fn, *args, **kwargs):
    # small wrapper to identify which IMAP call stalls
    print(f"IMAP: {desc} ...", flush=True)
    out = fn(*args, **kwargs)
    print(f"IMAP: {desc} done", flush=True)
    return out

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
    ap.add_argument("--max-messages", type=int, default=250)
    ap.add_argument("--batch", type=int, default=50)
    args = ap.parse_args()

    cfg = load_cfg(Path(args.config))
    lookback_days = int(cfg.get("lookback_days", 30))
    mailbox = cfg.get("mailbox", "INBOX")
    rules = cfg.get("rules", [])
    never_from = set(cfg.get("never_from") or [])
    if not rules:
        print("No rules configured; exiting.")
        Path(args.manifest).write_text("", encoding="utf-8")
        return

    runtime = Path.home()/".openclaw/runtime"
    email = read_one_line(runtime/"credentials/yahoo_email")
    app  = read_one_line(runtime/"credentials/yahoo_app_password")

    M = imaplib.IMAP4_SSL("imap.mail.yahoo.com", 993, ssl_context=ssl.create_default_context())
    imap_set_timeout(M, 20)

    safe_imap_call("login", M.login, email, app)
    imap_set_timeout(M, 20)

    try:
        typ, _ = safe_imap_call(f"select {mailbox}", M.select, mailbox, True)  # readonly=True
        imap_set_timeout(M, 20)

        if typ != "OK":
            raise RuntimeError(f"select {mailbox} failed: {typ}")

        # Yahoo IMAP date search is coarse; we still do lookback check after fetching headers
        since = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=lookback_days)).date()
        since_str = since.strftime("%d-%b-%Y")  # IMAP date format
        typ, data = safe_imap_call(f"search SINCE {since_str}", M.search, None, "SINCE", since_str)
        imap_set_timeout(M, 20)
        if typ != "OK":
            raise RuntimeError(f"search SINCE failed: {typ}")
        ids = data[0].split() if data and data[0] else []
        # newest-first cap: IMAP ids are increasing; keep the newest
        max_messages = int(args.max_messages)
        if max_messages > 0 and len(ids) > max_messages:
            ids = ids[-max_messages:]
        print(f"IMAP: ids_total={len(data[0].split()) if data and data[0] else 0} using_newest={len(ids)}", flush=True)

        out = Path(args.manifest)
        out.parent.mkdir(parents=True, exist_ok=True)

        def chunked(seq, n):
            for i in range(0, len(seq), n):
                yield seq[i:i+n]

        matched = 0
        with out.open("w", encoding="utf-8") as f:
            for chunk in chunked(ids, int(args.batch)):
                imap_set_timeout(M, 20)
                first = chunk[0].decode(errors="ignore")
                last = chunk[-1].decode(errors="ignore")
                print(f"IMAP: fetch headers batch {first}:{last} (n={len(chunk)})", flush=True)

                # Use an IMAP message set: "9170,9171,9172" (works reliably)
                msgset = b",".join(chunk)
                try:
                    typ, dat = safe_imap_call(f"fetch header batch {first}:{last}", M.fetch, msgset, "(BODY.PEEK[HEADER])")
                except Exception as e:
                    print(f"IMAP: batch fetch failed {first}:{last}: {type(e).__name__}: {e}", flush=True)
                    continue

                if typ != "OK" or not dat:
                    continue

                # dat contains tuples: (b'9170 (BODY[HEADER] {n}', header_bytes), b')', ...
                for item in dat:
                    if not isinstance(item, tuple) or len(item) != 2:
                        continue
                    meta, payload = item
                    if not isinstance(payload, (bytes, bytearray)):
                        continue

                    # meta begins with the msg sequence number in bytes
                    # ex: b'9174 (BODY[HEADER] {1234}'
                    m = re.match(rb"^(\d+)\s", meta or b"")
                    if not m:
                        continue
                    mid_bytes = m.group(1)

                    try:
                        msg = message_from_bytes(bytes(payload))
                    except Exception:
                        continue

                    frm = parseaddr(msg.get("From") or "")[1]
                    if frm in never_from:
                        continue
                    subj = decode_str(msg.get("Subject"))
                    dt_raw = msg.get("Date")
                    try:
                        msg_dt = parsedate_to_datetime(dt_raw) if dt_raw else None
                    except Exception:
                        msg_dt = None

                    if msg_dt and not within_lookback(msg_dt, lookback_days):
                        continue

                    action = None
                    rule_name = None
                    for r in rules:
                        if match_rule(frm, subj, r):
                            action = r.get("action", "quarantine")
                            rule_name = r.get("name", "rule")
                            break
                    if not action:
                        continue
                    if action == "skip":
                        # Hard ignore; do not emit manifest entry
                        continue

                    rec = {
                        "ts_utc": datetime.datetime.now(datetime.UTC).isoformat(),
                        "mailbox": mailbox,
                        "msg_id": mid_bytes.decode(errors="ignore"),
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
        try:
            M.logout()
        except Exception:
            pass

if __name__ == "__main__":
    main()
