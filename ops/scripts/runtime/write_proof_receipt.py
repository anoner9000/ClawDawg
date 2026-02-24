#!/usr/bin/env python3
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import os
import pathlib
import subprocess
import uuid
from typing import Any, Dict, List, Optional


def _utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run(cmd: str, cwd: Optional[str] = None) -> Dict[str, Any]:
    # Runs a shell command deterministically, captures stdout/stderr and exit.
    p = subprocess.run(
        cmd,
        shell=True,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {
        "cmd": cmd,
        "exit": p.returncode,
        "stdout": p.stdout,
        "stderr": p.stderr,
    }


def _git_head(repo_root: str) -> str:
    try:
        out = subprocess.check_output(["git", "-C", repo_root, "rev-parse", "HEAD"], text=True).strip()
        return out
    except Exception:
        return "unknown"


@dataclasses.dataclass
class EvidenceItem:
    kind: str
    data: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind, **self.data}


def main() -> int:
    ap = argparse.ArgumentParser(description="Write a Proof Receipt JSON for a claim.")
    ap.add_argument("--agent", required=True, help="Producer agent name (e.g., rembrandt, custodian).")
    ap.add_argument("--claim-kind", required=True, help="One of: runtime_state, code_change, verification, commit, etc.")
    ap.add_argument("--claim-text", required=True, help="Human-readable claim statement.")
    ap.add_argument("--task-id", default="", help="Optional task_id for traceability.")
    ap.add_argument("--repo-root", default=os.environ.get("OPENCLAW_REPO_ROOT", "/home/kyler/.openclaw/workspace"))
    ap.add_argument("--out-dir", default=os.path.expanduser("~/.openclaw/runtime/reports/proof"))
    ap.add_argument("--evidence-cmd", action="append", default=[], help="Shell command to run and capture as evidence.")
    ap.add_argument(
        "--evidence-file",
        action="append",
        default=[],
        help="File excerpt evidence: 'path:lineStart-lineEnd' or 'path' for full file (discouraged).",
    )
    ap.add_argument("--stdout-excerpt-max", type=int, default=4000, help="Max chars of stdout excerpt per cmd.")
    ap.add_argument("--stderr-excerpt-max", type=int, default=2000, help="Max chars of stderr excerpt per cmd.")
    args = ap.parse_args()

    ts = _utc_now_iso()
    claim_id = f"claim-{ts.replace(':', '').replace('-', '').replace('Z', 'Z')}-{uuid.uuid4().hex[:6]}"
    repo_root = str(pathlib.Path(args.repo_root).resolve())
    out_dir = pathlib.Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = out_dir / f"{claim_id}.json"

    evidence: List[EvidenceItem] = []

    # Command evidence (capture now)
    for cmd in args.evidence_cmd:
        res = _run(cmd, cwd=repo_root)
        stdout = (res["stdout"] or "")[: args.stdout_excerpt_max]
        stderr = (res["stderr"] or "")[: args.stderr_excerpt_max]
        evidence.append(
            EvidenceItem(
                kind="command",
                data={
                    "cmd": res["cmd"],
                    "cwd": repo_root,
                    "exit": res["exit"],
                    "stdout_excerpt": stdout,
                    "stderr_excerpt": stderr,
                },
            )
        )

    # File excerpt evidence (non-OCR, simple excerpt)
    for spec in args.evidence_file:
        # spec formats:
        #   "path"
        #   "path:10-40"
        path_part = spec
        line_range = ""
        if ":" in spec:
            path_part, line_range = spec.split(":", 1)
        rel_path = path_part.strip()
        abs_path = (
            (pathlib.Path(repo_root) / rel_path).resolve()
            if not os.path.isabs(rel_path)
            else pathlib.Path(rel_path).resolve()
        )

        excerpt = ""
        if abs_path.exists() and abs_path.is_file():
            lines = abs_path.read_text(errors="replace").splitlines()
            if line_range:
                try:
                    a_s, b_s = line_range.split("-", 1)
                    a = max(1, int(a_s))
                    b = max(a, int(b_s))
                    excerpt_lines = lines[a - 1 : b]
                    excerpt = "\n".join(excerpt_lines)
                except Exception:
                    excerpt = "\n".join(lines[:80])
                    line_range = "1-80"
            else:
                excerpt = "\n".join(lines[:80])
                line_range = "1-80"
        else:
            excerpt = "<missing file>"

        evidence.append(
            EvidenceItem(
                kind="file_excerpt",
                data={
                    "path": str(abs_path),
                    "repo_rel_path": rel_path if not os.path.isabs(rel_path) else "",
                    "lines": line_range or "1-80",
                    "excerpt": excerpt[:8000],
                },
            )
        )

    payload: Dict[str, Any] = {
        "schema": "openclaw.proof_receipt.v1",
        "ts": ts,
        "agent": args.agent,
        "claim_id": claim_id,
        "claim_text": args.claim_text,
        "claim_kind": args.claim_kind,
        "status": "unverified",
        "context": {
            "repo_root": repo_root,
            "git_head": _git_head(repo_root),
            "task_id": args.task_id,
        },
        "evidence": [e.to_dict() for e in evidence],
    }

    receipt_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    # Emit a single-line token that other systems can parse.
    print(f"proof_receipt={receipt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
