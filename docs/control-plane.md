# Control Plane Contract

This repository uses a deterministic "Code Factory" governance model.

## Required Checks

All merges to `master` require:

- `gate` (risk policy preflight)
- `ci` (tests/build)

## Risk Policy Gate

The policy gate emits a machine-readable contract (`gate.json`) containing:

- baseSha
- headSha
- riskTier
- requiredChecks
- touchedPaths
- policy.tierRules
- policy.mergePolicy

`gate.json` is an artifact and is NOT committed.

## High-Risk Changes

For high-risk changes, the gate requires CodeRabbit review evidence
matching the current PR head SHA (no stale review allowed).

## Control-Plane Drift Rule

Any changes to:
- `.github/workflows/**`
- `ops/scripts/policy/**`

Require updating this document in the same PR.

## Change Log / Notes

- Workflow: CodeRabbit rerun condition now keys off `steps.policy.outputs.requiredChecks`.
- Script: `ops/scripts/policy/request_coderabbit_rerun.py` added/updated for canonical rerun requests.
- Rerun requests are SHA-deduped via marker `<!-- coderabbit-auto-rerun -->` and `sha:<HEAD_SHA>`.
- `gh_api` now uses explicit request timeout and timeout-specific error handling.
- `gh_api` enforces HTTPS-only URLs via scheme guard.
- Removed unused `time` import from rerun script.
- Workflow permissions now explicitly grant `contents: read`, `pull-requests: write`, and `issues: write` for PR comment operations.
- Rerun request step now skips fork PRs (`!github.event.pull_request.head.repo.fork`) to avoid permission-driven hard failures.
- Governance contract: added `ops/policy/risk_policy.yml` (policyVersion: 1) and updated `risk_policy_gate.py` to derive required checks/control-plane rules from the YAML contract.
- Auto-merge: enable GitHub auto-merge for low-risk PRs (contract-driven) after `gate` + `ci` succeed; skipped for fork PRs.
- Tightened workflow top-level permissions to `contents: read`; write access restricted to `auto-merge-low` job only (least-privilege enforcement).
- Policy validation: added `ops/scripts/policy/validate_risk_policy.py` and run it in Code Factory before the gate so malformed `ops/policy/risk_policy.yml` fails fast.
- Merge audit: when `auto-merge-low` enables GitHub auto-merge (riskTier=low), Code Factory emits a structured JSON audit record and uploads it as an Actions artifact (`code-factory-merge-audit`).
- Gate behavior: control-plane doc drift is WARNING-only for riskTier=low; still enforced (blocking) for medium/high.

### Risk Label Automation

The Code Factory now auto-applies risk labels (`risk:low|medium|high`)
based on `gate_output.json` produced by the risk policy gate.

- Risk labels are contract-driven: `ops/policy/risk_policy.yml` defines `tiers.*.label`, and the gate emits `riskLabel` for the workflow to apply.

## 2026-02-20 — Guarded Direct Merge for Low-Risk PRs

### Summary
Replaced native GitHub auto-merge mutation with guarded direct `gh pr merge --squash`
execution in Code Factory.

### Details
- Introduced Guard auto-merge step:
  - Validates requiredChecks (`gate` + `ci`) are green on current head SHA.
  - Verifies repository auto-merge setting when applicable.
- Merge step now executes direct squash merge:
  - `gh pr merge --squash --delete-branch=false`
  - Only runs when:
    - `riskTier == low`
    - requiredChecks satisfied
- Maintains deterministic contract-driven governance.

### Rationale
Ensures merge enforcement is self-contained in workflow and does not rely
on GitHub native auto-merge setting.
