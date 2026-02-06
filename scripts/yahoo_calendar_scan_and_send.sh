#!/usr/bin/env bash
set -euo pipefail

# Yahoo Calendar Scanner -> ICS attachments -> email to wife
# Cron target (already installed by you): Mondays 05:00 America/Chicago
#
# Config:
#   ~/.openclaw/runtime/config/yahoo_calendar_senders.json
# Credentials (ONE LINE each; NOT used in --dry-run):
#   ~/.openclaw/runtime/credentials/yahoo_email
#   ~/.openclaw/runtime/credentials/yahoo_app_password

RUNTIME="${OPENCLAW_RUNTIME_DIR:-$HOME/.openclaw/runtime}"
CFG="$RUNTIME/config/yahoo_calendar_senders.json"

BASE="$RUNTIME/yahoo_calendar"
LOGDIR="$BASE/logs"
STATEDIR="$BASE/state"
OUTDIR="$BASE/outgoing"
ICSDIR="$OUTDIR/ics"

TS="$(date -Iseconds | tr ':' '-')"

# Logs:
# - Always append main run log
LOG="$LOGDIR/yahoo_calendar_scan.log"
# - Dry-run also writes its own dedicated log
DRY_LOG="$LOGDIR/dry_run_${TS}.log"
# - Cron wrapper log if you want to tee into it (optional)
CRON_LOG="$LOGDIR/cron.log"

# Prefer OpenClaw venv python, fall back to system python3
PY="$HOME/.openclaw/venv/bin/python3"
if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3)"
fi

DRY_RUN=0
INPUT_DIR=""
INPUT_FILE=""
INPUT_STDIN=0
MAX_MESSAGES=""

usage() {
  cat <<'USAGE'
Usage:
  yahoo_calendar_scan_and_send.sh [--dry-run] [--input-file FILE | --input-dir DIR | --stdin] [--max-messages N]

Modes:
  --dry-run
    Read-only mode:
      - NO credential reads
      - NO IMAP / SMTP
      - NO state writes
      - NO outgoing writes
      - Parses .eml input(s) and prints event candidates

Inputs (dry-run only):
  --input-file FILE     Single RFC822 .eml file
  --input-dir DIR       Directory containing *.eml files
  --stdin               Read one RFC822 message from STDIN
  --max-messages N      Limit how many *.eml files are processed (input-dir only)

Examples:
  ./yahoo_calendar_scan_and_send.sh --dry-run --input-file /path/sample.eml
  ./yahoo_calendar_scan_and_send.sh --dry-run --input-dir /path/eml_dir --max-messages 5
  cat sample.eml | ./yahoo_calendar_scan_and_send.sh --dry-run --stdin
USAGE
}

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift;;
    --input-dir) INPUT_DIR="${2:-}"; shift 2;;
    --input-file) INPUT_FILE="${2:-}"; shift 2;;
    --stdin) INPUT_STDIN=1; shift;;
    --max-messages) MAX_MESSAGES="${2:-}"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1" >&2; usage; exit 1;;
  esac
done

# Dry-run log-only: only create log dir. Live mode creates full tree.
if [[ "$DRY_RUN" -eq 1 ]]; then
  mkdir -p "$LOGDIR"
else
  mkdir -p "$LOGDIR" "$STATEDIR" "$OUTDIR" "$ICSDIR"
fi

{
  echo "=== $(date -Iseconds) START yahoo calendar scan ==="
  echo "python:     $PY"
  echo "runtime:    $RUNTIME"
  echo "config:     $CFG"
  echo "dry_run:    $DRY_RUN"
  echo "input_file: ${INPUT_FILE:-<none>}"
  echo "input_dir:  ${INPUT_DIR:-<none>}"
  echo "stdin:      ${INPUT_STDIN}"
  echo "max_msgs:   ${MAX_MESSAGES:-<none>}"
  echo

  "$PY" -u - <<PY
import os, re, json, ssl, smtplib, hashlib, datetime
import imaplib
from pathlib import Path
from email import message_from_bytes
from email.utils import parseaddr
from email.header import decode_header, make_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# ---------------------------
# Paths / settings
# ---------------------------
RUNTIME = Path(os.path.expanduser("${RUNTIME}"))
CFG = Path(os.path.expanduser("${CFG}"))

BASE = Path(os.path.expanduser("${BASE}"))
LOGDIR = Path(os.path.expanduser("${LOGDIR}"))
STATEDIR = Path(os.path.expanduser("${STATEDIR}"))
OUTDIR = Path(os.path.expanduser("${OUTDIR}"))
ICSDIR = Path(os.path.expanduser("${ICSDIR}"))

DRY_RUN = bool(int("${DRY_RUN}"))
INPUT_DIR = "${INPUT_DIR}"
INPUT_FILE = "${INPUT_FILE}"
INPUT_STDIN = bool(int("${INPUT_STDIN}"))
MAX_MESSAGES = "${MAX_MESSAGES}".strip()

DRY_LOG = Path(os.path.expanduser("${DRY_LOG}"))

CRED_EMAIL = RUNTIME / "credentials" / "yahoo_email"
CRED_APP_PASS = RUNTIME / "credentials" / "yahoo_app_password"

EMITTED = STATEDIR / "emitted_events.jsonl"
LAST_SUMMARY = STATEDIR / "last_summary.json"

TZID_DEFAULT = "America/Chicago"  # always Central

# ---------------------------
# Helpers
# ---------------------------
def die(msg, code=1):
    raise SystemExit(msg)

def read_one_line(p: Path) -> str:
    if not p.exists():
        die(f"Missing credential file: {p}")
    s = p.read_text(encoding="utf-8", errors="replace").strip()
    if not s:
        die(f"Empty credential file: {p}")
    return s

def decode_str(v) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    try:
        return str(make_header(decode_header(v)))
    except Exception:
        return str(v)

def normalize_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()

def extract_text(msg) -> str:
    # Prefer text/plain, fallback to stripped html
    parts = []
    if msg.is_multipart():
        for p in msg.walk():
            ctype = (p.get_content_type() or "").lower()
            disp = (p.get("Content-Disposition") or "").lower()
            if "attachment" in disp:
                continue
            if ctype == "text/plain":
                try:
                    payload = p.get_payload(decode=True) or b""
                    cs = p.get_content_charset() or "utf-8"
                    parts.append(payload.decode(cs, "replace"))
                except Exception:
                    pass
        if parts:
            return normalize_ws("\n".join(parts))

        for p in msg.walk():
            ctype = (p.get_content_type() or "").lower()
            disp = (p.get("Content-Disposition") or "").lower()
            if "attachment" in disp:
                continue
            if ctype == "text/html":
                try:
                    payload = p.get_payload(decode=True) or b""
                    cs = p.get_content_charset() or "utf-8"
                    html = payload.decode(cs, "replace")
                    txt = re.sub(r"<[^>]+>", " ", html)
                    return normalize_ws(txt)
                except Exception:
                    pass
        return ""
    else:
        try:
            payload = msg.get_payload(decode=True) or b""
            cs = msg.get_content_charset() or "utf-8"
            return normalize_ws(payload.decode(cs, "replace"))
        except Exception:
            return ""

def safe_filename(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r'[\\/:*?"<>|]+', "-", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = s.replace("—", "-").replace("–", "-")
    return (s[:80] if s else "Event")

def fmt_mmddyyyy(date_iso: str) -> str:
    y, m, d = date_iso.split("-")
    return f"{m}-{d}-{y}"

def sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def load_cfg():
    if not CFG.exists():
        die(f"Missing config: {CFG}")

    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    senders_raw = cfg.get("senders", [])
    if not isinstance(senders_raw, list) or not senders_raw:
        die("Config has no senders[]. Add at least one sender.")

    sender_emails = []
    for s in senders_raw:
        if isinstance(s, dict) and s.get("email"):
            sender_emails.append(s["email"].strip().lower())
        elif isinstance(s, str) and s.strip():
            sender_emails.append(s.strip().lower())

    lookback_days = int(cfg.get("lookback_days", 14))
    subj_keywords = [x.lower() for x in (cfg.get("optional_subject_keywords") or []) if isinstance(x, str)]
    tzid = cfg.get("timezone", TZID_DEFAULT) or TZID_DEFAULT
    wife_email = (cfg.get("wife_email") or "").strip()
    if not wife_email:
        die("Config missing wife_email")
    return sender_emails, lookback_days, subj_keywords, tzid, wife_email

# ---------------------------
# Grade/child mapping
# ---------------------------
EXCEPTION_KEYWORDS = [
    "picture day", "field day", "book fair",
    "no school", "day off", "days off", "holiday",
    "early release", "late start", "school closed"
]

GRADE_MAP = [
    (re.compile(r"\bkindergarten\b", re.IGNORECASE), "Kindergarten", "Henrik"),
    (re.compile(r"\bsecond\s+grade\b|\b2nd\s+grade\b", re.IGNORECASE), "Second Grade", "Amelia"),
    (re.compile(r"\bfourth\s+grade\b|\b4th\s+grade\b", re.IGNORECASE), "Fourth Grade", "Elijah"),
]

def infer_grade_and_child(text: str) -> tuple[str, str]:
    t = text.lower()
    if any(k in t for k in EXCEPTION_KEYWORDS):
        return "Grade Unspecified", "Grade Unspecified"
    hits = []
    for rx, grade, child in GRADE_MAP:
        if rx.search(text):
            hits.append((grade, child))
    if len(hits) == 1:
        return hits[0]
    return "Grade Unspecified", "Grade Unspecified"

# ---------------------------
# Date/time extraction
# ---------------------------
MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

RE_MONTH_DATE = re.compile(
    r"(?:(?:mon|tue|wed|thu|fri|sat|sun)(?:day)?\s*,\s*)?"
    r"(?P<month>january|february|march|april|may|june|july|august|september|october|november|december|"
    r"jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)"
    r"\s+(?P<day>\d{1,2})(?:st|nd|rd|th)?"
    r"(?:\s*,\s*(?P<year>\d{4}))?",
    re.IGNORECASE
)

RE_NUM_DATE = re.compile(r"\b(?P<m>\d{1,2})/(?P<d>\d{1,2})(?:/(?P<y>\d{2,4}))?\b")
RE_TIME_12H = re.compile(r"\b(?P<h>\d{1,2})(?::(?P<min>\d{2}))?\s*(?P<ampm>am|pm)\b", re.IGNORECASE)
RE_TIME_24H = re.compile(r"\b(?P<h>\d{1,2}):(?P<min>\d{2})\b")

def coerce_year(d: datetime.date, today: datetime.date) -> datetime.date:
    # If date looks "in the past" by more than ~30 days and no year was provided, assume next year.
    if d < today - datetime.timedelta(days=30):
        try:
            return d.replace(year=d.year + 1)
        except Exception:
            return d
    return d

def pick_title(subject: str, body: str, span_start: int) -> str:
    # heuristic: look left for "X: ..." then use X
    left = body[max(0, span_start - 220):span_start]
    last_line = left.split("\n")[-1].strip()
    if ":" in last_line:
        maybe = last_line.split(":")[0].strip()
        if 3 <= len(maybe) <= 60:
            return maybe
    subj = re.sub(r"^(re|fwd):\s*", "", (subject or "").strip(), flags=re.IGNORECASE)
    subj = normalize_ws(subj)
    return subj[:80] if subj else "Event"

def parse_time_near(body: str, span_start: int, span_end: int):
    # Search nearby text for a time. If absent, default 09:00 but note "time unspecified"
    win = body[max(0, span_start - 120):min(len(body), span_end + 180)]
    m = RE_TIME_12H.search(win)
    if m:
        h = int(m.group("h"))
        minute = int(m.group("min") or "0")
        ampm = (m.group("ampm") or "").lower()
        if ampm == "pm" and h != 12:
            h += 12
        if ampm == "am" and h == 12:
            h = 0
        return h, minute, "parsed"
    m2 = RE_TIME_24H.search(win)
    if m2:
        h = int(m2.group("h"))
        minute = int(m2.group("min"))
        if 0 <= h <= 23 and 0 <= minute <= 59:
            return h, minute, "parsed"
    # default time for DTSTART, but note remains "time unspecified"
    return 9, 0, "time unspecified"

def find_events(subject: str, body: str, today: datetime.date):
    events = []

    for m in RE_MONTH_DATE.finditer(body):
        mon = MONTHS[m.group("month").lower()]
        day = int(m.group("day"))
        year = m.group("year")
        y = int(year) if year else today.year
        try:
            d = datetime.date(y, mon, day)
        except Exception:
            continue
        if not year:
            d = coerce_year(d, today)

        h, minute, time_note = parse_time_near(body, m.start(), m.end())
        title = pick_title(subject, body, m.start())
        context = normalize_ws(body[max(0, m.start()-180):min(len(body), m.end()+260)])
        events.append({
            "date": d.isoformat(),
            "title": title,
            "hour": h,
            "minute": minute,
            "time_note": time_note,
            "context": context,
        })

    for m in RE_NUM_DATE.finditer(body):
        mon = int(m.group("m"))
        day = int(m.group("d"))
        yraw = m.group("y")
        if yraw:
            y = int(yraw)
            if y < 100:
                y += 2000
        else:
            y = today.year
        try:
            d = datetime.date(y, mon, day)
        except Exception:
            continue
        if not yraw:
            d = coerce_year(d, today)

        h, minute, time_note = parse_time_near(body, m.start(), m.end())
        title = pick_title(subject, body, m.start())
        context = normalize_ws(body[max(0, m.start()-180):min(len(body), m.end()+260)])
        events.append({
            "date": d.isoformat(),
            "title": title,
            "hour": h,
            "minute": minute,
            "time_note": time_note,
            "context": context,
        })

    # de-dupe within a single email
    uniq = []
    seen = set()
    for e in events:
        key = (e["date"], e["title"].lower(), e["hour"], e["minute"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(e)
    return uniq

# ---------------------------
# ICS generation
# ---------------------------
def ics_uid(seed: str) -> str:
    return f"{sha(seed)[:24]}@deiphobe"

def make_ics(event: dict, tzid: str) -> str:
    dtstamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    uid = ics_uid(event["hash"])

    def esc(x: str) -> str:
        x = x or ""
        return (x.replace("\\", "\\\\")
                 .replace("\n", "\\n")
                 .replace(",", "\\,")
                 .replace(";", "\\;"))

    y, mo, da = event["date"].split("-")
    hh = int(event["hour"])
    mm = int(event["minute"])

    dtlocal = f"{y}{mo}{da}T{hh:02d}{mm:02d}00"
    start_dt = datetime.datetime(int(y), int(mo), int(da), hh, mm)
    end_dt = start_dt + datetime.timedelta(minutes=60)
    dtend = end_dt.strftime("%Y%m%dT%H%M%S")

    desc_lines = [
        f"Grade: {event['grade']}",
        f"Child: {event['child']}",
        f"Time: {event['time_note']}",
        "",
        f"Source sender: {event['sender']}",
        f"Source subject: {event['subject']}",
        "",
        f"Context: {event['context']}",
    ]
    description = "\n".join(desc_lines)

    body = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Deiphobe//YahooCalendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{dtstamp}",
        f"SUMMARY:{esc(event['summary'])}",
        f"DESCRIPTION:{esc(description)}",
        f"DTSTART;TZID={tzid}:{dtlocal}",
        f"DTEND;TZID={tzid}:{dtend}",
        "END:VEVENT",
        "END:VCALENDAR",
        "",
    ]
    return "\r\n".join(body)

def load_emitted_hashes():
    hashes = set()
    if EMITTED.exists():
        for line in EMITTED.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                h = obj.get("event_hash")
                if h:
                    hashes.add(h)
            except Exception:
                pass
    return hashes

def append_emitted(row: dict):
    EMITTED.parent.mkdir(parents=True, exist_ok=True)
    with EMITTED.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

# ---------------------------
# Email sending
# ---------------------------
def send_email_with_attachments(from_email: str, app_pass: str, to_email: str, paths: list[Path]):
    subject = "Kids calendar dates (Apple Calendar attachments)"

    greeting = "Good Morning, My Love. I have these dates for you to review about up and coming events for the children."
    closing = "Love you — hope this makes your day a little easier. 💛"

    msg_out = MIMEMultipart()
    msg_out["From"] = from_email
    msg_out["To"] = to_email
    msg_out["Subject"] = subject

    body_text = (
        f"{greeting}\n\n"
        f"Attached are {len(paths)} calendar file(s). You can open them to add to Apple Calendar.\n\n"
        f"{closing}\n"
    )
    msg_out.attach(MIMEText(body_text, "plain", "utf-8"))

    for p in paths:
        part = MIMEBase("text", "calendar")
        part.set_payload(p.read_bytes())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{p.name}"')
        part.add_header("Content-Type", 'text/calendar; method=PUBLISH; charset="utf-8"')
        msg_out.attach(part)

    smtp = smtplib.SMTP_SSL("smtp.mail.yahoo.com", 465, context=ssl.create_default_context())
    smtp.login(from_email, app_pass)
    smtp.sendmail(from_email, [to_email], msg_out.as_string())
    smtp.quit()

# ---------------------------
# Input readers (dry-run)
# ---------------------------
def read_eml_bytes_from_dir(path: Path, max_messages: int | None) -> list[bytes]:
    files = sorted([p for p in path.glob("*.eml") if p.is_file()])
    if max_messages is not None:
        files = files[:max_messages]
    out = []
    for p in files:
        out.append(p.read_bytes())
    return out

def read_eml_bytes_from_file(path: Path) -> list[bytes]:
    return [path.read_bytes()]

def read_eml_bytes_from_stdin() -> list[bytes]:
    data = os.read(0, 10_000_000)
    return [data] if data else []

# ---------------------------
# Main
# ---------------------------
def main():
    sender_emails, lookback_days, subj_keywords, tzid, wife_email = load_cfg()
    tzid = tzid or TZID_DEFAULT

    if DRY_RUN:
        if not (INPUT_DIR or INPUT_FILE or INPUT_STDIN):
            die("DRY-RUN requires an input source: --input-dir, --input-file, or --stdin")
        if sum([1 if INPUT_DIR else 0, 1 if INPUT_FILE else 0, 1 if INPUT_STDIN else 0]) != 1:
            die("DRY-RUN: choose exactly one of --input-dir / --input-file / --stdin")
    else:
        # only read creds in non-dry-run
        yahoo_email = read_one_line(CRED_EMAIL)
        yahoo_app_pass = read_one_line(CRED_APP_PASS)

    today = datetime.date.today()

    print(f"Config senders: {len(sender_emails)}")
    print(f"Lookback days:  {lookback_days}")
    print(f"Timezone:       {tzid}")
    print(f"Wife email:     {wife_email}")
    print()

    emails_scanned = 0
    matched_emails = 0
    extracted_events = 0
    created_events = 0
    skipped_dedupe = 0

    emitted_hashes = set() if DRY_RUN else load_emitted_hashes()
    new_ics_paths: list[Path] = []

    raw_msgs: list[bytes] = []

    if DRY_RUN:
        max_msgs = int(MAX_MESSAGES) if MAX_MESSAGES else None
        if INPUT_FILE:
            raw_msgs = read_eml_bytes_from_file(Path(INPUT_FILE))
        elif INPUT_DIR:
            raw_msgs = read_eml_bytes_from_dir(Path(INPUT_DIR), max_msgs)
        else:
            raw_msgs = read_eml_bytes_from_stdin()

        print(f"DRYRUN: loaded {len(raw_msgs)} message(s) from input")
        print()
    else:
        since = today - datetime.timedelta(days=lookback_days)
        since_str = since.strftime("%d-%b-%Y")

        M = imaplib.IMAP4_SSL("imap.mail.yahoo.com", 993)
        M.login(yahoo_email, yahoo_app_pass)
        M.select("INBOX")

        typ, data = M.search(None, "SINCE", since_str)
        if typ != "OK":
            die("IMAP search failed")

        msg_ids = data[0].split()
        for mid in msg_ids:
            typ, msg_data = M.fetch(mid, "(RFC822)")
            if typ != "OK" or not msg_data or not msg_data[0]:
                continue
            raw = msg_data[0][1]
            if raw:
                raw_msgs.append(raw)

        M.close()
        M.logout()

    for raw in raw_msgs:
        if not raw:
            continue
        emails_scanned += 1

        msg = message_from_bytes(raw)
        from_hdr = decode_str(msg.get("From", ""))
        from_email = (parseaddr(from_hdr)[1] or "").strip().lower()

        if from_email not in sender_emails:
            continue

        subject = decode_str(msg.get("Subject", "")).strip()
        if subj_keywords:
            subj_low = subject.lower()
            if not any(k in subj_low for k in subj_keywords):
                continue

        matched_emails += 1
        body = extract_text(msg)
        if not body:
            continue

        grade, child = infer_grade_and_child(body)
        events = find_events(subject, body, today)
        if not events:
            continue

        extracted_events += len(events)

        for e in events:
            date_iso = e["date"]
            title = safe_filename(e["title"])
            summary = title

            seed = f"{from_email}|{subject}|{date_iso}|{title}|{e['hour']}|{e['minute']}|{grade}|{child}"
            h = "sha256:" + sha(seed)

            if h in emitted_hashes:
                skipped_dedupe += 1
                continue

            # Naming convention: MM-DD-YYYY_<short-title>.ics (no time in filename)
            mmddyyyy = fmt_mmddyyyy(date_iso)
            base_name = f"{mmddyyyy}_{title}.ics"
            planned_path = ICSDIR / base_name

            if DRY_RUN:
                print(f"- {mmddyyyy} | {title} | {grade} -> {child} | {e['time_note']} | file: {base_name}")
                continue

            # Ensure uniqueness if same filename exists
            path = planned_path
            if path.exists():
                i = 2
                while True:
                    alt = ICSDIR / f"{mmddyyyy}_{title}_{i}.ics"
                    if not alt.exists():
                        path = alt
                        break
                    i += 1

            event_obj = {
                "hash": h,
                "sender": from_email,
                "subject": subject,
                "date": date_iso,
                "summary": summary,
                "grade": grade,
                "child": child,
                "hour": e["hour"],
                "minute": e["minute"],
                "time_note": e["time_note"],
                "context": e["context"],
            }

            ics = make_ics(event_obj, tzid)
            path.write_text(ics, encoding="utf-8")
            new_ics_paths.append(path)

            created_events += 1
            emitted_hashes.add(h)

            append_emitted({
                "event_hash": h,
                "created_at": datetime.datetime.utcnow().isoformat() + "Z",
                "sender": from_email,
                "subject": subject,
                "event_date": date_iso,
                "filename": path.name,
                "grade": grade,
                "child": child,
            })

    if DRY_RUN:
        summary = {
            "mode": "dry_run",
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "emails_scanned": emails_scanned,
            "emails_matched": matched_emails,
            "events_extracted": extracted_events,
            "events_would_create": (extracted_events - skipped_dedupe),
            "events_skipped_dedupe_in_memory": skipped_dedupe,
            "timezone": tzid,
        }
        print()
        print("DRYRUN SUMMARY:")
        print(json.dumps(summary, ensure_ascii=False, indent=2))

        DRY_LOG.parent.mkdir(parents=True, exist_ok=True)
        DRY_LOG.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\nDRYRUN log written: {DRY_LOG}")
        return

    # Non-dry-run summary/state write
    summary = {
        "mode": "live",
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "lookback_days": lookback_days,
        "emails_scanned": emails_scanned,
        "emails_matched": matched_emails,
        "events_extracted": extracted_events,
        "events_created": created_events,
        "events_skipped_dedupe": skipped_dedupe,
        "timezone": tzid,
        "sent_to": wife_email,
        "attachments": [p.name for p in new_ics_paths],
    }
    LAST_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if not new_ics_paths:
        print("No new events found (or all deduped). No email sent.")
        print(f"last_summary: {LAST_SUMMARY}")
        return

    yahoo_email = read_one_line(CRED_EMAIL)
    yahoo_app_pass = read_one_line(CRED_APP_PASS)

    send_email_with_attachments(yahoo_email, yahoo_app_pass, wife_email, new_ics_paths)
    print(f"Email sent to {wife_email} with {len(new_ics_paths)} attachment(s).")
    print(f"last_summary: {LAST_SUMMARY}")

if __name__ == "__main__":
    main()
PY

  echo
  echo "=== $(date -Iseconds) END yahoo calendar scan ==="
  echo

} | tee -a "$LOG" | tee -a "$CRON_LOG" >/dev/null 2>&1
