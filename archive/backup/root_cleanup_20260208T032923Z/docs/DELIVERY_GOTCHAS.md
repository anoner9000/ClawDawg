Delivery Gotchas — common failure modes and fixes

1) Rate limits / auth cooldowns
- Symptom: Many LLM jobs trigger 429s and then auth profiles hit cooldown.
- Fix: Batch requests, add exponential backoff, and circuit breaker to pause non‑critical jobs.

2) Cron duplication
- Symptom: Multiple jobs schedule the same LLM call (slightly different times) and overlap.
- Fix: Use a single canonical heartbeat aggregator; have jobs enqueue work rather than call LLM directly.

3) Truncated web fetches / poor context
- Symptom: Web fetch returns partial pages → hallucinations.
- Fix: Index full sources when possible; otherwise attach source URLs and fallback to ‘I don’t know’ responses.

4) Silent failures (no logs)
- Symptom: Jobs fail silently; you only notice a downstream outage.
- Fix: Centralize heartbeat logs (~/logs/heartbeat) and create alerts for consecutive failures.

5) Unbounded backups & indexes
- Symptom: Indexer stores everything forever and consumes quota.
- Fix: Prune policies, rolling windows, and retention/archival.

6) Secret leakage via index
- Symptom: Indexer grabs .env, keys, or private messages.
- Fix: Strong exclude filters and pre‑index review; never index credentials files.
