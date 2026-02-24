#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

RECEIPTS_DIRNAME = "receipts"
EXECUTION_RECEIPT_NAME = "EXECUTION_RECEIPT.json"
PROOF_VALIDATION_NAME = "PROOF_VALIDATION.json"

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def load_json(p: Path) -> Dict[str, Any]:
    return json.loads(p.read_text(encoding="utf-8"))

def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(2)

def warn(msg: str) -> None:
    print(f"WARN: {msg}")

def ok(msg: str) -> None:
    print(f"OK: {msg}")

def find_candidate_bus_files(root: Path) -> List[Path]:
    candidates: List[Path] = []
    for rel in [
        "team_bus.jsonl",
        "ops/team_bus.jsonl",
        "runtime/team_bus.jsonl",
        ".openclaw/runtime/team_bus.jsonl",
        ".openclaw/runtime/logs/team_bus.jsonl",
    ]:
        p = root / rel
        if p.exists():
            candidates.append(p)
    if not candidates:
        for p in root.rglob("*.jsonl"):
            name = p.name.lower()
            if "bus" in name and p.stat().st_size < 50_000_000:
                candidates.append(p)
    return candidates

def parse_jsonl_for_complete(bus_path: Path) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    with bus_path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            state = obj.get("state") or obj.get("payload", {}).get("state")
            if str(state).lower() == "complete":
                obj["_bus_path"] = str(bus_path)
                obj["_line_no"] = line_no
                events.append(obj)
    return events

def ensure_receipts(root: Path, task_id: str) -> Tuple[Path, Path]:
    task_dir = root / "tasks" / task_id / RECEIPTS_DIRNAME
    exec_r = task_dir / EXECUTION_RECEIPT_NAME
    proof_r = task_dir / PROOF_VALIDATION_NAME
    if not exec_r.exists():
        fail(f"missing {exec_r}")
    if not proof_r.exists():
        fail(f"missing {proof_r}")
    return exec_r, proof_r

def validate_required_fields_exec(r: Dict[str, Any]) -> None:
    for k in ["receipt_version","task_id","executor","intent","scope","actions","artifacts","claims","timestamp_utc"]:
        if k not in r:
            fail(f"EXECUTION_RECEIPT missing field: {k}")
    if not isinstance(r["actions"], list) or len(r["actions"]) < 1:
        fail("EXECUTION_RECEIPT.actions must be non-empty list")

def validate_required_fields_proof(r: Dict[str, Any]) -> None:
    for k in ["validation_version","task_id","custodian","result","failures","validated_artifacts","timestamp_utc"]:
        if k not in r:
            fail(f"PROOF_VALIDATION missing field: {k}")
    if r["custodian"] != "custodian":
        fail("PROOF_VALIDATION.custodian must equal 'custodian'")
    if r["result"] != "PASS":
        fail("PROOF_VALIDATION.result must be PASS for completion")

def verify_artifact_hashes(root: Path, artifacts: List[Dict[str, Any]]) -> None:
    for a in artifacts:
        path = a.get("path")
        h = a.get("sha256")
        if not path or not h:
            continue
        p = root / path
        if not p.exists():
            fail(f"artifact listed but missing: {path}")
        actual = sha256_file(p)
        if actual != h:
            fail(f"artifact hash mismatch for {path}: expected {h} got {actual}")

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".", help="repo root")
    ap.add_argument("--bus", default="", help="path to bus jsonl (optional)")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    bus_files: List[Path] = []
    if args.bus:
        p = (root / args.bus).resolve() if not os.path.isabs(args.bus) else Path(args.bus)
        if not p.exists():
            fail(f"--bus not found: {p}")
        bus_files = [p]
    else:
        bus_files = find_candidate_bus_files(root)

    if not bus_files:
        warn("No bus jsonl found; run with --bus to enforce against your canonical bus path.")
        ok("No enforcement triggered.")
        return

    complete_events: List[Dict[str, Any]] = []
    for b in bus_files:
        complete_events.extend(parse_jsonl_for_complete(b))

    if not complete_events:
        ok("No state=complete events found in bus.")
        return

    ok(f"Found {len(complete_events)} completion event(s); enforcing custodian-only completion + receipts.")

    for ev in complete_events:
        agent = ev.get("agent") or ev.get("from") or ev.get("payload", {}).get("agent") or ev.get("payload", {}).get("from")
        task_id = ev.get("task_id") or ev.get("payload", {}).get("task_id")
        if not task_id:
            fail(f"completion event missing task_id (bus={ev.get('_bus_path')} line={ev.get('_line_no')})")
        if agent != "custodian":
            fail(f"non-custodian completion forbidden: agent={agent} task_id={task_id} (bus={ev.get('_bus_path')} line={ev.get('_line_no')})")

        exec_r_path, proof_r_path = ensure_receipts(root, task_id)
        exec_r = load_json(exec_r_path)
        proof_r = load_json(proof_r_path)

        validate_required_fields_exec(exec_r)
        validate_required_fields_proof(proof_r)

        if exec_r.get("task_id") != task_id:
            fail(f"EXECUTION_RECEIPT.task_id mismatch: {exec_r.get('task_id')} != {task_id}")
        if proof_r.get("task_id") != task_id:
            fail(f"PROOF_VALIDATION.task_id mismatch: {proof_r.get('task_id')} != {task_id}")

        verify_artifact_hashes(root, exec_r.get("artifacts", []))
        verify_artifact_hashes(root, proof_r.get("validated_artifacts", []))

    ok("All completion events validated successfully.")

if __name__ == "__main__":
    main()
