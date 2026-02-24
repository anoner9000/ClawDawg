from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def sha256_text(s: str) -> str:
    return sha256_bytes(s.encode("utf-8"))

@dataclass(frozen=True)
class ArtifactRef:
    path: str
    sha256: str

@dataclass(frozen=True)
class ProofFailure:
    code: str
    message: str

def build_legacy_proof_receipt_v1(
    *,
    claim_kind: str,
    claim: str,
    evidence: Optional[str],
    details: Optional[Dict[str, Any]],
    schema: str = "openclaw.proof_receipt.v1",
) -> Dict[str, Any]:
    """
    Legacy-compatible proof receipt builder.
    Pure function: returns a dict; caller decides where/how to store it.
    """
    obj: Dict[str, Any] = {
        "schema": schema,
        "ts": now_utc_iso(),
        "claim_kind": claim_kind,
        "claim": claim,
    }
    if evidence is not None:
        obj["evidence"] = evidence
    if details is not None:
        obj["details"] = details
    # Include a stable content hash for traceability
    obj["_content_sha256"] = sha256_text(json.dumps(obj, sort_keys=True, ensure_ascii=False))
    return obj

def build_execution_receipt_v2(
    *,
    task_id: str,
    executor: str,
    intent: str,
    paths_touched: List[str],
    notes: str,
    actions: List[Dict[str, Any]],
    artifacts: List[ArtifactRef],
    claims: List[Dict[str, Any]],
    receipt_version: str = "2.0",
) -> Dict[str, Any]:
    """
    v2 Execution Receipt builder.
    Pure function: returns a dict matching ops/schemas/execution_receipt.schema.json (expected).
    """
    return {
        "receipt_version": receipt_version,
        "task_id": task_id,
        "executor": executor,
        "intent": intent,
        "scope": {"paths_touched": paths_touched, "notes": notes},
        "actions": actions,
        "artifacts": [asdict(a) for a in artifacts],
        "claims": claims,
        "timestamp_utc": now_utc_iso(),
    }

def build_proof_validation_v2(
    *,
    task_id: str,
    result: str,
    failures: List[ProofFailure],
    validated_artifacts: List[ArtifactRef],
    validation_version: str = "2.0",
    custodian: str = "custodian",
) -> Dict[str, Any]:
    """
    v2 Proof Validation builder.
    Pure function: returns a dict matching ops/schemas/proof_validation.schema.json (expected).
    """
    return {
        "validation_version": validation_version,
        "task_id": task_id,
        "custodian": custodian,
        "result": result,
        "failures": [asdict(f) for f in failures],
        "validated_artifacts": [asdict(a) for a in validated_artifacts],
        "timestamp_utc": now_utc_iso(),
    }
