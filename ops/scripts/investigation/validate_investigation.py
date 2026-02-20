#!/usr/bin/env python3
import json
import hashlib
import sys
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
except Exception as e:
    print(f"ERROR: jsonschema is required in the active interpreter: {e}", file=sys.stderr)
    sys.exit(1)

def die(msg: str, code: int = 2):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)

def load_json(path: Path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        die(f"Failed to load JSON {path}: {e}")

def iter_jsonl(path: Path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    yield i, json.loads(line)
                except Exception as e:
                    die(f"Invalid JSON on {path} line {i}: {e}")
    except FileNotFoundError:
        die(f"Missing file: {path}")



def sha256_file(path: Path) -> str:
    return sha256_hex(path.read_bytes())

def sha256_hex(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return "sha256:" + h.hexdigest()

def validate_instance(instance, schema, label: str):
    v = Draft202012Validator(schema)
    errs = sorted(v.iter_errors(instance), key=lambda e: list(e.path))
    if errs:
        for e in errs[:25]:
            loc = ".".join(str(p) for p in e.path) if e.path else "<root>"
            print(f"Schema error [{label}] at {loc}: {e.message}", file=sys.stderr)
        if len(errs) > 25:
            print(f"... plus {len(errs)-25} more errors", file=sys.stderr)
        die(f"Schema validation failed for {label}")

def validate_file(json_path: Path, schema_path: Path, label: str):
    inst = load_json(json_path)
    schema = load_json(schema_path)
    validate_instance(inst, schema, label)

def validate_jsonl(jsonl_path: Path, schema_path: Path, label: str):
    schema = load_json(schema_path)
    for line_no, inst in iter_jsonl(jsonl_path):
        validate_instance(inst, schema, f"{label}:{line_no}")

def main(run_dir: str):
    run_dir = Path(run_dir)
    schema_dir = Path("ops/schemas/investigation")

    claims_path = run_dir / "claims.json"
    evidence_path = run_dir / "evidence.jsonl"
    skeptic_path = run_dir / "skeptic.json"
    skeptic_requests_path = run_dir / "skeptic_requests.json"
    patch_dir = run_dir / "patches"
    patch_manifest_path = patch_dir / "patch_manifest.json"

    if not claims_path.exists():
        die(f"Missing claims.json in {run_dir}")
    if not evidence_path.exists():
        die(f"Missing evidence.jsonl in {run_dir}")

    validate_file(claims_path, schema_dir / "claims.schema.json", "claims.json")
    validate_jsonl(evidence_path, schema_dir / "evidence.schema.json", "evidence.jsonl")

    # VERIFY_CONTENT_HASH
    for line_no, inst in iter_jsonl(evidence_path):
        locator = inst.get("locator", {})
        kind = locator.get("kind")
        expected_hash = inst.get("contentHash")

        # Only verify file-based locators
        if kind == "file_row" or kind == "file_span":
            file_path = locator.get("path")
            if not file_path:
                die(f"Missing path in locator for evidence line {line_no}")

            fp = Path(file_path)
            if not fp.exists():
                die(f"Referenced file does not exist: {fp}")

            data = fp.read_bytes()
            actual_hash = sha256_hex(data)

            if actual_hash != expected_hash:
                die(
                    f"Hash mismatch in evidence line {line_no}: "
                    f"expected {expected_hash}, got {actual_hash}"
                )


    if skeptic_path.exists():
        validate_file(skeptic_path, schema_dir / "skeptic.schema.json", "skeptic.json")

    if skeptic_requests_path.exists():
        validate_file(skeptic_requests_path, schema_dir / "skeptic_requests.schema.json", "skeptic_requests.json")

    # PATCH VALIDATION (optional)
    # If patches exist, they must be described by patch_manifest.json and must stay within safe bounds.
    if patch_dir.exists():
        if not patch_manifest_path.exists():
            die("patches/ exists but patches/patch_manifest.json is missing")

        validate_file(patch_manifest_path, schema_dir / "patch_manifest.schema.json", "patches/patch_manifest.json")

        pm = load_json(patch_manifest_path)

        # hard caps (MVP defaults)
        MAX_PATCH_FILES = 5
        MAX_TOTAL_LINES_CHANGED = 800

        patches = pm.get("patches", [])
        if len(patches) > MAX_PATCH_FILES:
            die(f"Too many patch files: {len(patches)} > {MAX_PATCH_FILES}")

        total_changed = 0

        # path policy (denylist)
        forbidden_prefixes = [
            ".github/",
            "ops/policy/",
            "docs/control-plane.md",
            "ops/scripts/policy/",
            "ops/scripts/merge/",
            "ops/scripts/investigation/"
        ]

        for pinfo in patches:
            if not pinfo.get("touchedPaths"):
                die("Empty touchedPaths array in patch manifest")
            pf = patch_dir / pinfo["filename"]
            if not pf.exists():
                die(f"Patch listed in manifest missing on disk: {pf}")

            actual = sha256_file(pf)
            if actual != pinfo["sha256"]:
                die(f"Patch hash mismatch for {pf}: expected {pinfo['sha256']}, got {actual}")



            # PATH_TRAVERSAL_PROTECTION
            for touched in pinfo.get("touchedPaths", []):
                # Reject absolute paths
                if touched.startswith("/") or touched.startswith("\\"):
                    die(f"Absolute paths are forbidden in patch: {touched}")

                # Reject traversal
                parts = Path(touched).parts
                if ".." in parts:
                    die(f"Path traversal detected in patch: {touched}")

                if not touched.strip():
                    die("Empty touched path detected in patch manifest")

            # enforce forbidden paths
            for touched in pinfo.get("touchedPaths", []):
                for pref in forbidden_prefixes:
                    if touched == pref or touched.startswith(pref):
                        die(f"Forbidden patch path touched: {touched} (matches {pref})")

            total_changed += int(pinfo.get("linesAdded", 0)) + int(pinfo.get("linesDeleted", 0))

        if total_changed > MAX_TOTAL_LINES_CHANGED:
            die(f"Patch too large: total lines changed {total_changed} > {MAX_TOTAL_LINES_CHANGED}")


    # marker file so the adjudicator can enforce "validated first"
    marker = run_dir / "validation.ok"
    marker.write_text("ok\n", encoding="utf-8")

    print(f"OK: validated investigation artifacts; wrote {marker}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: validate_investigation.py <run_dir>", file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1])
