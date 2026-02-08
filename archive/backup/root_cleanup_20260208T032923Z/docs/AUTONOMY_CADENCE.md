Autonomy Cadence

Recommended default cadences
- Heartbeat (aggregated LLM calls): hourly — collects queued LLM tasks and issues one LLM request.
- Critical exact-timing LLM jobs: rare, isolated cron (at most once every 15 minutes; group into single session).
- Non-LLM system checks (disk, service health, logs): use system scheduler (launchd/systemd) or non-agent cron every 5–30 minutes.
- User-facing reminders (habits): batch small reminders, or push via Cron but with rate limits.

Practical examples
- System health: systemd/launchd every 5–15 minutes (no LLM).
- Security deep scan: weekly Cron (LLM only for summary/triage; otherwise local processing).
- Briefings: Heartbeat hourly aggregator composes any LLM content for morning briefing.

Fallback rule
- If a scheduled LLM job causes auth errors (4xx/429), move it into the next heartbeat and pause the original schedule until validated.
