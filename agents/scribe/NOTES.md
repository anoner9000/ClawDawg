# Scribe — NOTES

Last updated: 2026-02-07

## Current State Snapshot (1 paragraph)
Workspace has been reorganized into `doctrine/` (canonical playbooks/templates), `agents/` (agent-specific SOUL/RUNBOOK/NOTES), `ops/` (scripts + schemas + CLI wrapper), and `archive/` (legacy/backups). Canonical meta files (`BOOTSTRAP.md`, `IDENTITY.md`, `USER.md`) exist at repo root (currently symlinked into `doctrine/meta/`) so agents can rehydrate reliably. Usage accounting is active via `~/.openclaw/runtime/logs/heartbeat/llm_usage.jsonl`, with ledger/report tooling under `ops/scripts/ledger/` and a working `ops/scripts/ledger/token_today_totals.sh` for “today totals”. Heartbeat tasks are currently disabled by design (HEARTBEAT.md is empty/no tasks). Gmail cleanup pipeline work exists as archived legacy material and runtime logs remain the source of truth for execution history.

## What I track
- “What is live” (paths + commands)
- “What changed” (commits + dates)
- Known issues / open follow-ups
- Pointers to canonical docs (doctrine/*) and executable tools (ops/*)

## Open follow-ups
- Verify `ops/oc tokens today` works end-to-end in the expected shell + cron environment.
- Ensure all “canonical path references” in docs point to the active tree (no dead paths).
