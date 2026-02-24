#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional

from ops.governance.receipts import build_legacy_proof_receipt_v1

def main() -> int:
    ap = argparse.ArgumentParser(description="Write a legacy proof receipt (thin wrapper).")
    ap.add_argument("--out", required=True, help="Output path for receipt JSON.")
    ap.add_argument("--claim-kind", required=True, help="Claim kind label (legacy).")
    ap.add_argument("--claim", required=True, help="Claim text (legacy).")
    ap.add_argument("--evidence", default=None, help="Optional evidence string.")
    ap.add_argument("--details-json", default=None, help="Optional JSON object for details.")
    args = ap.parse_args()

    details: Optional[Dict[str, Any]] = None
    if args.details_json:
        details = json.loads(args.details_json)

    receipt = build_legacy_proof_receipt_v1(
        claim_kind=args.claim_kind,
        claim=args.claim,
        evidence=args.evidence,
        details=details,
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    print(f"proof_receipt={out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
