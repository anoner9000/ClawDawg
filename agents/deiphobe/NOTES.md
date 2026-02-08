# Deiphobe — NOTES
Last updated: 2026-02-08
Maintainer: Deiphobe (with Scribe support)

This file is the **authoritative snapshot of current operational state**.
It is not a log. It is not a plan. It is a curated, human-readable truth.

---

## 1) Current State (High-Level)

### System posture
- OpenClaw workspace restructured into domain folders: `doctrine/`, `agents/`, `projects/`, `ops/`, `archive/`
- Canonical identity/meta files now under `doctrine/meta/`
- Team bus model running at `team_bus.v1.1` with gate + risk/block workflow implemented
- Heartbeat framework present; no mandatory periodic agent polling configured (`HEARTBEAT.md` is effectively idle)

### What is working
- Team bus append/validation tooling:
  - `ops/scripts/bus/deiphobe`
  - `ops/scripts/validate/validate_team_bus.py`
  - `ops/scripts/validate/validate_team_bus_jsonl.py`
- Approval and block logic:
  - `ops/scripts/gates/gate_require_approval.py`
  - `ops/scripts/bus/auto_block_on_risk.py`
- Task status views:
  - `ops/scripts/dashboards/task_dashboard.py`
  - `ops/scripts/dashboards/task_state.py`
- Global Gmail trash ledger exists and is populated:
  - `~/.openclaw/runtime/logs/gmail_trash_ledger.jsonl`

### What is in progress
- Post-restructure cleanup: moving/normalizing script references from legacy `scripts/` paths to `ops/scripts/` paths
- Stabilizing runbook/docs references to moved files

### What is explicitly deferred
- External dashboard/UI (current visibility is CLI + logs)
- Full cron policy rewrite after path migration is finalized

---

## 2) Gmail Cleanup Pipeline

### Purpose
Automated cleanup and lifecycle management for Gmail (quarantine -> review -> trash),
with full auditability and idempotency.

### Components
- Active operational script paths:
  - `~/.openclaw/workspace/ops/scripts/gmail/`
- Manifests:
  - `~/.openclaw/runtime/logs/mail_cleanup_manifest_*.jsonl`
- Quarantine logs:
  - `~/.openclaw/runtime/logs/*.jsonl.quarantine_log`
- Trash logs:
  - `~/.openclaw/runtime/logs/*.jsonl.quarantine_log.trash_log`
- Ledger:
  - `~/.openclaw/runtime/logs/gmail_trash_ledger.jsonl`

### Safety guarantees
- Trash path is gated by explicit apply/confirm controls
- Ledger-based dedupe model exists (`gmail_trash_ledger.jsonl`)
- Append-only audit artifacts for manifests/quarantine/trash logs

### Status
- Historical dry-run/quarantine/trash artifacts exist and were validated previously
- **Current blocker:** several Gmail scripts in `ops/scripts/gmail/` are thin wrappers still pointing to `modules/gmail/scripts/...` paths that are no longer present after reorg; requires path remediation before reliable reruns

---

## 3) Token / Usage Accounting

### Purpose
Track LLM usage and cost over time with append-only artifacts.

### Artifacts
- Usage log:
  - `~/.openclaw/runtime/logs/heartbeat/llm_usage.jsonl`
- Append/report scripts:
  - `~/.openclaw/workspace/ops/scripts/ledger/usage_append_from_latest_response.sh`
  - `~/.openclaw/workspace/ops/scripts/ledger/ledger_render_report_accounting.py`
  - `~/.openclaw/workspace/ops/scripts/ledger/ledger_render_report_accounting_html.py`
- Reports:
  - `~/.openclaw/runtime/logs/heartbeat/ledger_report_accounting_latest.html`

### Status
- Runtime usage ledger is present and non-empty
- `token_today_totals.sh` currently not in active `ops/scripts/` tree (exists only in archived backup), so direct “today totals” shortcut is presently missing

---

## 4) Automation & Schedulers

### Cron / Task Scheduler
- Gmail nightly runner (current location):
  - `~/.openclaw/workspace/ops/scripts/gmail/gmail_nightly_cleanup.sh`
- Existing runtime logs include both old `cron_gmail_cleanup_*.log` and newer `gmail_cleanup_*.log` naming

### Heartbeat
- `HEARTBEAT.md` intentionally minimal (no active task list), so periodic polling is effectively disabled by default

---

## 5) Credentials & Secrets (High-Level Only)

- Runtime config/credential material lives under:
  - `~/.openclaw/runtime/config/`
  - `~/.openclaw/runtime/credentials/` (policy path)
- OAuth/token artifacts are present under runtime config (for Gmail modify flow)
- No secrets should be committed to repo paths

⚠️ Never record actual secrets in this file.

---

## 6) Dashboards & Outputs

- Team bus:
  - `~/.openclaw/runtime/logs/team_bus.jsonl`
- Task dashboard/state:
  - `~/.openclaw/workspace/ops/scripts/dashboards/task_dashboard.py`
  - `~/.openclaw/workspace/ops/scripts/dashboards/task_state.py`
- Ledger HTML reports:
  - `~/.openclaw/runtime/logs/heartbeat/ledger_report_accounting_latest.html`

---

## 7) Known Issues / Risks

- Script path drift after reorg:
  - Some moved scripts still reference old `modules/...` or old top-level `scripts/...` locations
- Cron environment mismatch risk:
  - historical cron entries may still point at pre-reorg paths
- Approval expiry workflow is strict by design:
  - stale approvals quickly transition tasks to `APPROVAL EXPIRED`

---

## 8) Open Follow-Ups

- [ ] Remediate Gmail script internal paths to use `ops/scripts/gmail/` or restore canonical module locations
- [ ] Reconcile cron entries with current `ops/scripts/...` paths
- [ ] Restore/replace `token_today_totals.sh` in active `ops/scripts/ledger/` toolchain
- [ ] Run end-to-end post-reorg smoke checks for: gate -> dashboard -> deiphobe -> gmail pipeline
