#!/usr/bin/env python3

import json
import sys
from pathlib import Path



def die(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)

def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        die(f"Failed to load {path}: {e}")



def load_jsonl(path):
    items = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items

def main(run_dir):
    run_dir = Path(run_dir)
    claims_path = run_dir / "claims.json"
    evidence_path = run_dir / "evidence.jsonl"
    skeptic_path = run_dir / "skeptic.json"

    if not claims_path.exists():
        die("claims.json missing")
    if not evidence_path.exists():
        die("evidence.jsonl missing")

    marker = run_dir / "validation.ok"
    if not marker.exists():
        die("validation.ok missing (run validator first)")
    claims_doc = load_json(claims_path)
    evidence_items = load_jsonl(evidence_path)
    skeptic_doc = load_json(skeptic_path) if skeptic_path.exists() else {"claims": []}

    evidence_ids = {e["evidenceId"] for e in evidence_items}

    claim_decisions = []
    overall_status = "canonical"

    skeptic_by_claim = {
        c["claimId"]: c for c in skeptic_doc.get("claims", [])
    }

    for claim in claims_doc["claims"]:
        claim_id = claim["claimId"]
        base_conf = claim["confidence"]
        refs = set(claim["evidenceRefs"])

        blocking = []
        adjusted = base_conf

        # Structural check: missing evidence refs
        if not refs:
            blocking.append("NO_EVIDENCE_REFS")

        # Structural check: evidence objects exist
        missing_refs = refs - evidence_ids
        if missing_refs:
            blocking.append("MISSING_EVIDENCE_OBJECT")

        # Apply skeptic penalties
        findings = []
        skeptic_claim = skeptic_by_claim.get(claim_id, {})
        for finding in skeptic_claim.get("findings", []):
            impact = finding.get("impact", 0.0)
            adjusted -= impact
            findings.append(finding)

        adjusted = max(0.0, round(adjusted, 3))

        # Determine status
        if blocking:
            status = "invalid"
            overall_status = "invalid"
        elif adjusted >= 0.75:
            status = "canonical"
        elif adjusted >= 0.55:
            status = "provisional"
            if overall_status == "canonical":
                overall_status = "provisional"
        else:
            status = "exploratory"
            if overall_status not in ("invalid",):
                overall_status = "exploratory"

        claim_decisions.append({
            "claimId": claim_id,
            "status": status,
            "adjustedConfidence": adjusted,
            "blockingReasons": blocking,
            "skepticFindings": findings
        })

    adjudication = {
        "schemaVersion": "1.0",
        "runId": claims_doc["runId"],
        "overallStatus": overall_status,
        "mergeEligible": (run_dir / "patches" / "patch_manifest.json").exists(),
        "followupRecommended": overall_status in ("provisional", "exploratory"),
        "claims": claim_decisions,
        "notes": ""
    }

    out_path = run_dir / "adjudication.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(adjudication, f, indent=2)

    print(f"OK: wrote {out_path}")

    # Exit code only fails on structural invalid
    if overall_status == "invalid":
        sys.exit(2)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: adjudicate_investigation.py <run_dir>")
        sys.exit(1)

    main(sys.argv[1])
