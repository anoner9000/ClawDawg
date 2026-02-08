CRON vs Heartbeat Guide

Goal
Prevent LLM rate storms by choosing the right scheduler for each task and batching LLM calls.

Rules of thumb
- Needs direct system action, no LLM: use system scheduler (launchd/systemd) or local cron.
- Needs LLM and exact timing: use isolated Cron in an `isolated` session (minimize frequency; group similar tasks).
- Needs LLM but not exact timing: batch into a Heartbeat (hourly recommended) that issues a single aggregated LLM call.

Patterns
- High-frequency, small tasks → move to system scheduler (no LLM).
- Many LLM jobs within small windows → consolidate to 1 heartbeat call (aggregate payloads).
- Security checks & content scouts -> can often be batched hourly.

Implementation checklist
1. Audit scheduled jobs: list all cron/cronlike entries and identify which call LLMs.
2. Classify jobs: Non‑LLM / LLM-exact / LLM-batchable.
3. Move Non‑LLM to system scheduler or local cron managed outside the agent.
4. Implement heartbeat aggregator script; replace multiple LLM jobs with a single job that queues work items for the heartbeat.
5. Add a rate‑guard (circuit breaker) that pauses non‑critical LLM jobs on repeated 429s.
6. Monitor and iterate.

Delivery notes
- Start in dry-run mode: stage changes and run heartbeats manually before flipping live.
- Keep log rotation for heartbeat runs and failure counts under ~/logs/heartbeat/.
