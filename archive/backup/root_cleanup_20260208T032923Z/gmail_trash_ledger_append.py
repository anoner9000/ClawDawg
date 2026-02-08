#!/usr/bin/env python3
"""
gmail_trash_ledger_append.py

Append-only, deduped global Gmail trash ledger.

Schema:
{"id","time","source_trash_log","source_quarantine_log"}
"""

import argparse
import json
import pathlib

HOME = pathlib.Path.home()
DEFAULT_LEDGER = HOME / ".openclaw/runtime/logs/gmail_trash_ledger.jsonl"


def load_existing_ids(path):
    ids = set()
    if not path.exists():
        return ids
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            ids.add(json.loads(line)["id"])
        except Exception:
            pass
    return ids


def iter_trashed(trash_log):
    for line in trash_log.read_text().splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
            if obj.get("action") == "trashed" and obj.get("id"):
                yield obj
        except Exception:
            continue


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quarantine-log", required=True)
    ap.add_argument("--trash-log")
    ap.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    args = ap.parse_args()

    if not args.quarantine_log.strip():
        raise SystemExit("--quarantine-log was empty (did you pass an unset $Q?)")

    qlog = pathlib.Path(args.quarantine_log)
    if not qlog.exists():
        raise SystemExit(f"quarantine log not found: {qlog}")

    tlog = pathlib.Path(
        args.trash_log if args.trash_log else str(qlog) + ".trash_log"
    )
    if not tlog.exists():
        raise SystemExit(f"trash log not found: {tlog}")

    ledger = pathlib.Path(args.ledger)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    print(f"using quarantine_log={qlog}")
    print(f"using trash_log={tlog}")
    print(f"using ledger={ledger}")

    existing = load_existing_ids(ledger)
    added = 0

    with ledger.open("a", encoding="utf-8") as out:
        for rec in iter_trashed(tlog):
            mid = rec["id"]
            if mid in existing:
                continue
            row = {
                "id": mid,
                "time": rec.get("time"),
                "source_trash_log": str(tlog),
                "source_quarantine_log": str(qlog),
            }
            out.write(json.dumps(row) + "\n")
            existing.add(mid)
            added += 1

    print(f"ledger_update added={added} total_ids={len(existing)} ledger={ledger}")


if __name__ == "__main__":
    main()
