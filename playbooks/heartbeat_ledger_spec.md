HEARTBEAT USAGE LEDGER - SPEC (canonical)

Overview
- The Heartbeat Usage Ledger is an append-only, provenance-first record of LLM usage for heartbeat/aggregator runs. It records request/response artifacts and computes/appends cost records to ~/.openclaw/runtime/logs/heartbeat/llm_usage.jsonl.

Key invariants (must hold)
- Audit / provenance: Every successful run MUST produce: instructions_*.txt, request_*.json, llm_response_*.json, heartbeat_run_*.log, and a processed_*.jsonl marker containing response_path.
- Append-only ledger: llm_usage.jsonl is append-only; no script edits existing lines.
- Exactly-once accounting: The orchestrator enforces once-per-response append. Usage append is idempotent by source path (no duplicates allowed).
- Queue safety: Queue cleared only after successful 2xx response and processed markers written; on failure, queue remains intact unless operator policy dictates otherwise.
- Spend safety: Aggregator enforces a hard estimated cost cap (default $0.50) and aborts before API call if exceeded.

Operational policies
- Production config files must have a known-good backup before tests modify anything. Known-good copies live under ~/.openclaw/runtime/config.known-good/ and are the source of truth for restores.
- Rate guard: record only on HTTP 429; events stored with {ts, code} and pruned by window. Circuit opens when threshold exceeded.
- Failure handling: If usage append fails after a successful API call, the aggregator MUST write an accounting_incomplete_<ts>.flag with response_path, stderr output, and a repair_command; queue may be cleared per operator policy but a repair path must exist.

Testing & restore discipline
- Any test that would modify production files MUST first copy affected files to ~/.openclaw/runtime/config.known-good/ (or an operator-approved safe location) and record the restore command in the test run log.
- The orchestrator will prefer reading model rates from ~/.openclaw/runtime/config.known-good/ when available for dry-run tests.

Appendix: Known-good location (example)
- /home/kyler/.openclaw/runtime/config.known-good/model_rates.json

Recorded-by: Deiphobe
Timestamp: 2026-02-06T22:58:00Z
