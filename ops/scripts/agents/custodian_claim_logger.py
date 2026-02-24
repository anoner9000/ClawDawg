#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import sys
from typing import Any, Dict


def _utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> int:
    ap = argparse.ArgumentParser(description="Append a Proof Receipt reference to Custodian's claims ledger (JSONL).")
    ap.add_argument("--receipt", required=True, help="Absolute path to a proof receipt JSON.")
    ap.add_argument("--ledger", default=os.path.expanduser("~/.openclaw/runtime/logs/custodian_claims.jsonl"))
    ap.add_argument("--copy-to", default="", help="Optional: copy receipt into a custodian-owned directory.")
    args = ap.parse_args()

    receipt_path = pathlib.Path(args.receipt).expanduser().resolve()
    if not receipt_path.exists():
        print(f"ERROR: receipt not found: {receipt_path}", file=sys.stderr)
        return 2

    try:
        receipt = json.loads(receipt_path.read_text())
    except Exception as e:
        print(f"ERROR: failed to parse receipt JSON: {e}", file=sys.stderr)
        return 2

    claim_id = receipt.get("claim_id", "")
    producer = receipt.get("agent", "")
    ts = _utc_now_iso()

    ledger_path = pathlib.Path(args.ledger).expanduser().resolve()
    ledger_path.parent.mkdir(parents=True, exist_ok=True)

    copied_path = ""
    if args.copy_to:
        dest_dir = pathlib.Path(args.copy_to).expanduser().resolve()
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / receipt_path.name
        dest.write_text(receipt_path.read_text())
        copied_path = str(dest)

    entry: Dict[str, Any] = {
        "schema": "openclaw.custodian.claim_ledger.v1",
        "ts": ts,
        "claim_id": claim_id,
        "producer_agent": producer,
        "receipt_path": str(receipt_path),
        "receipt_copy_path": copied_path,
        "status": "unverified",
        "notes": "",
    }

    with ledger_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")

    print(f"custodian_ledger_appended=1 claim_id={claim_id} ledger={ledger_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
