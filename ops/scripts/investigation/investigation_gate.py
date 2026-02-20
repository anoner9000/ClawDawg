#!/usr/bin/env python3
import json
import sys
from pathlib import Path
import subprocess
import hashlib

def compute_run_hash(run_dir: Path) -> str:
    """Deterministic run hash over key inputs (not CI outputs)."""
    # Only hash inputs / proposals (avoid validation.ok, adjudication.json churn)
    include = []
    for rel in [
        "claims.json",
        "evidence.jsonl",
        "skeptic.json",
        "skeptic_requests.json",
        "patches/patch_manifest.json",
    ]:
        fp = run_dir / rel
        if fp.exists():
            include.append(fp)

    # Include patch files if present
    patch_dir = run_dir / "patches"
    if patch_dir.exists():
        for pf in sorted(patch_dir.glob("*.patch")):
            include.append(pf)

    h = hashlib.sha256()
    for fp in sorted(set(include)):
        rel = fp.relative_to(run_dir).as_posix()
        h.update(rel.encode("utf-8") + b"\0")
        data = fp.read_bytes()
        h.update(hashlib.sha256(data).digest())
    return "sha256:" + h.hexdigest()

def run(cmd, **kw):
    return subprocess.run(cmd, check=False, text=True, capture_output=True, **kw)

def die(msg, code=1):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)

def load_json(p: Path):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def main():
    if len(sys.argv) != 3:
        print("Usage: investigation_gate.py <run_dir> <run_id>", file=sys.stderr)
        return 1

    run_dir = Path(sys.argv[1])
    run_id = sys.argv[2]

    if not run_dir.exists():
        die(f"run_dir does not exist: {run_dir}", 2)

    # If patches exist, (re)build manifest deterministically
    patch_dir = run_dir / "patches"
    if patch_dir.exists():
        r = run([sys.executable, "ops/scripts/investigation/patch_manifest_build.py", str(run_dir), run_id])
        if r.returncode != 0:
            print(r.stdout)
            print(r.stderr, file=sys.stderr)
            return r.returncode

    # Validate artifacts (schema + integrity + patch scope)
    r = run([sys.executable, "ops/scripts/investigation/validate_investigation.py", str(run_dir)])
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr, file=sys.stderr)
        return r.returncode

    # Adjudicate
    r = run([sys.executable, "ops/scripts/investigation/adjudicate_investigation.py", str(run_dir)])
    if r.returncode not in (0, 2):
        print(r.stdout)
        print(r.stderr, file=sys.stderr)
        return r.returncode

    adjud_path = run_dir / "adjudication.json"
    if not adjud_path.exists():
        die(f"adjudication.json missing after adjudication: {adjud_path}", 2)

    adjud = load_json(adjud_path)
    status = adjud.get("overallStatus", "unknown")
    merge_eligible = adjud.get("mergeEligible", False)

    # Short operator summary
    run_hash = compute_run_hash(run_dir)
    print(f"RECEIPT investigation_gate runId={run_id} status={status} mergeEligible={merge_eligible} runHash={run_hash}")

    # Gate is intentionally structural: adjudication quality is reported in receipt/artifact
    # but does not block unless the run is structurally invalid.
    if status == "invalid":
        return 2

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
