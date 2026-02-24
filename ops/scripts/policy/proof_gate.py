#!/usr/bin/env python3
from __future__ import annotations

import argparse
import pathlib
import sys
from typing import List, Tuple

try:
    import yaml  # type: ignore
except Exception:
    yaml = None


def _load_policy(path: str) -> dict:
    if yaml is None:
        raise RuntimeError("PyYAML not installed. Install or vendor a tiny YAML loader.")
    return yaml.safe_load(pathlib.Path(path).read_text())


def _should_skip_due_to_allow(text: str, allow_any: List[str]) -> bool:
    t = text.lower()
    for token in allow_any:
        if token.lower() in t:
            return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Proof Gate: fail if claim keywords appear without proof_receipt= or EVIDENCE: block.")
    ap.add_argument("--policy", default="ops/policy/proof_policy.yml")
    ap.add_argument("--file", action="append", default=[], help="Text file(s) to scan. If none, read stdin.")
    ap.add_argument("--context", default="", help="Optional label for diagnostics (e.g., task_id, agent).")
    args = ap.parse_args()

    policy = _load_policy(args.policy)
    cfg = policy.get("proofPolicy", {}) if isinstance(policy, dict) else {}
    if not cfg.get("enabled", False):
        print("proof_gate: disabled by policy")
        return 0

    keywords = [k.lower() for k in cfg.get("claimKeywords", [])]
    proof_token = str(cfg.get("proofReceiptToken", "proof_receipt="))
    evidence_prefix = str(cfg.get("evidenceBlockPrefix", "EVIDENCE:"))
    require = bool(cfg.get("requiresProofReceiptOrEvidenceBlock", True))
    allow_any = cfg.get("allowIfContainsAny", []) or []

    # gather inputs
    inputs: List[Tuple[str, str]] = []
    if args.file:
        for fp in args.file:
            p = pathlib.Path(fp).expanduser()
            inputs.append((str(p), p.read_text(errors="replace")))
    else:
        inputs.append(("<stdin>", sys.stdin.read()))

    violations: List[str] = []

    for label, text in inputs:
        if _should_skip_due_to_allow(text, allow_any):
            continue

        lower = text.lower()
        has_claim = any(k in lower for k in keywords)
        if not has_claim:
            continue

        if not require:
            continue

        has_proof = (proof_token in text) or (evidence_prefix in text)
        if not has_proof:
            # Show a short excerpt for debugging
            excerpt = text.strip().splitlines()
            excerpt = excerpt[:30]
            excerpt_s = "\n".join(excerpt)
            violations.append(
                f"[{args.context or 'context'}] {label}: claim keyword(s) present but no {proof_token} and no {evidence_prefix}\n"
                f"--- excerpt (first 30 lines) ---\n{excerpt_s}\n---"
            )

    if violations:
        print("proof_gate: FAIL")
        for v in violations:
            print(v)
        return 1

    print("proof_gate: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
