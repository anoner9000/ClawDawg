# CONTEXT — agent_ops
Last updated by: deiphobe
Last updated at: 2026-02-07

## Purpose
Central place for agent team doctrine, onboarding notes, and operating procedures.

## Current system invariants
- team_bus.jsonl is append-only truth
- gate requires Deiphobe APPROVAL with expires_at
- high/critical RISK auto-blocks
- UNBLOCKED is Deiphobe-only
- dashboard scripts are read-only
- ACE ingestion entrypoint: `./scripts/ingest_ace.sh` (delegates to `modules/briefings/scripts/ingest_ace.sh`). Default manifests + history live under `~/logs/ingest/` (history JSONL: `~/logs/ingest/history.jsonl`). Use `--dry-run`/`-n` to suppress writes or `--manifest-dir DIR` to override paths.

## Open items
- Run first agent onboarding trial (Scribe)
- Establish first monthly scorecard template
