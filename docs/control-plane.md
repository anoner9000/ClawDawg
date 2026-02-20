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
