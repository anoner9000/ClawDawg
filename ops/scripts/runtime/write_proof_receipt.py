#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional

from ops.governance.receipts import build_legacy_proof_receipt_v1

_BASE_KEYS = {"out","claim_kind","claim","evidence","details_json"}

def main() -> int:
    ap = argparse.ArgumentParser(description="Write a legacy proof receipt (thin wrapper).")
    ap.add_argument("--out", required=True, help="Output path for receipt JSON.")
    ap.add_argument("--claim-kind", required=True, help="Claim kind label (legacy).")
    ap.add_argument("--claim", required=True, help="Claim text (legacy).")
    ap.add_argument("--evidence", default=None, help="Optional evidence string.")
    ap.add_argument("--details-json", default=None, help="Optional JSON object for details.")

    # Extra flags preserved from prior implementation (WIP)
    ap.add_argument("--agent", required=True, help="Producer agent name (e.g., rembrandt, custodian).")
    ap.add_argument("--claim-kind", required=True, help="One of: runtime_state, code_change, verification, commit, etc.")
    ap.add_argument("--claim-text", default="", help="Human-readable claim statement.")
    ap.add_argument("--claim", default="", help="Alias for --claim-text.")
    ap.add_argument("--task-id", default="", help="Optional task_id for traceability.")
    ap.add_argument("--repo-root", default=os.environ.get("OPENCLAW_REPO_ROOT", "/home/kyler/.openclaw/workspace"))
    ap.add_argument("--out-dir", default=os.path.expanduser("~/.openclaw/runtime/reports/proof"))
    ap.add_argument("--evidence-cmd", action="append", default=[], help="Shell command to run and capture as evidence.")
    ap.add_argument(
    ap.add_argument("--evidence", action="append", default=[], help="Inline text evidence note.")
    ap.add_argument("--stdout-excerpt-max", type=int, default=4000, help="Max chars of stdout excerpt per cmd.")
    ap.add_argument("--stderr-excerpt-max", type=int, default=2000, help="Max chars of stderr excerpt per cmd.")

    args = ap.parse_args()

    details: Optional[Dict[str, Any]] = None
    if args.details_json:
        details = json.loads(args.details_json)

    # Preserve any extra parsed args by embedding them into details.extras
    extras: Dict[str, Any] = {}
    for k, v in vars(args).items():
        if k in _BASE_KEYS:
            continue
        # argparse converts "--claim-kind" into "claim_kind"
        if k in {"claim_kind","details_json"}:
            continue
        extras[k] = v

    if extras:
        if details is None:
            details = {}
        # Do not overwrite user-provided extras
        if "extras" not in details:
            details["extras"] = extras
        else:
            # merge conservatively
            for k, v in extras.items():
                details["extras"].setdefault(k, v)

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
