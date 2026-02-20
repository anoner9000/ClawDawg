#!/usr/bin/env python3
import hashlib
import json
import re
import sys
from pathlib import Path

DIFF_GIT_RE = re.compile(r"^diff --git a/(.+?) b/(.+?)\s*$")
HUNK_HDR_RE = re.compile(r"^@@ ")

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()

def parse_patch(patch_text: str):
    touched = []
    added = 0
    deleted = 0
    in_hunks = False

    for line in patch_text.splitlines():
        m = DIFF_GIT_RE.match(line)
        if m:
            a_path, b_path = m.group(1), m.group(2)
            # Use b_path as canonical touched path
            touched.append(b_path)
            in_hunks = False
            continue

        # Enter hunks once we see @@
        if HUNK_HDR_RE.match(line):
            in_hunks = True
            continue

        # Count +/- only inside hunks, ignore headers like +++/---
        if in_hunks:
            if line.startswith("+++ ") or line.startswith("--- "):
                continue
            if line.startswith("+") and not line.startswith("++"):
                added += 1
            elif line.startswith("-") and not line.startswith("--"):
                deleted += 1

    # De-dupe preserving order
    seen = set()
    touched_deduped = []
    for p in touched:
        if p not in seen:
            seen.add(p)
            touched_deduped.append(p)

    return touched_deduped, added, deleted

def main():
    if len(sys.argv) != 3:
        print("Usage: patch_manifest_build.py <run_dir> <run_id>", file=sys.stderr)
        sys.exit(1)

    run_dir = Path(sys.argv[1])
    run_id = sys.argv[2]

    patch_dir = run_dir / "patches"
    if not patch_dir.exists():
        print(f"OK: no patches dir at {patch_dir}; nothing to do")
        return 0

    patch_files = sorted(patch_dir.glob("*.patch"))
    if not patch_files:
        print(f"OK: patches dir exists but no *.patch files at {patch_dir}; nothing to do")
        return 0

    patches = []
    for pf in patch_files:
        text = pf.read_text(encoding="utf-8", errors="replace")
        touched, added, deleted = parse_patch(text)
        if not touched:
            print(f"ERROR: could not detect touched paths in {pf.name} (missing 'diff --git'?)", file=sys.stderr)
            sys.exit(2)

        patches.append({
            "filename": pf.name,
            "sha256": sha256_file(pf),
            "touchedPaths": touched,
            "summary": f"Patch proposal {pf.name}",
            "linesAdded": added,
            "linesDeleted": deleted
        })

    manifest = {
        "schemaVersion": "1.0",
        "runId": run_id,
        "patches": patches
    }

    out_path = patch_dir / "patch_manifest.json"
    out_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"OK: wrote {out_path} ({len(patches)} patches)")

if __name__ == "__main__":
    raise SystemExit(main())
