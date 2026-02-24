# Governance Surface Contract

## Goal
Keep governance logic **minimal, centralized, and mechanically enforceable**.

## Allowed governance surfaces (only)
Governance logic (policy evaluation, completion validity, proof/receipt requirements, authority checks)
MUST live only in:

- `ops/policy/` (declarative contracts only)
- `ops/schemas/` (schemas only)
- `ops/scripts/policy/` (policy enforcement + validators only)
- `ops/governance/` (shared governance library; pure functions; no side effects)

Everything else (agents, UI, runtime scripts) may **call** governance, but must not **redefine** it.

## Explicitly forbidden locations
- `agents/**`
- `ui/**`
- `ops/scripts/ui/**`
- `ops/scripts/agents/**`
- `ops/scripts/runtime/**` (except thin wrappers that call ops/governance)

## Definition of “governance logic”
Includes:
- deciding who may complete
- risk tier evaluation / merge gating
- proof/receipt validation requirements
- authority / policy checks
- declaring something “PASS/FAIL” from policy

## Enforcement
CI must fail if governance logic keywords appear outside allowed surfaces.
