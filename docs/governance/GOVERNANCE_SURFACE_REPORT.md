# Governance Surface Report

- Generated: 2026-02-24T16:42:53Z
- Pattern: `(risk_policy\.yml|risk[_ -]?policy|risk[_ -]?tier|proof_policy\.yml|proof[_ -]?policy|proof[_ -]?receipt|execution[_ -]?receipt|merge[_ -]?gate|policy[_ -]?gate|authority|authz|coderabbit|review[_ -]?agent|require_coderabbit|shepherd_merge|wait_for_check_runs|telegram|sendMessage|api\.telegram)`

## Top matches (file-level)

 -       8 ops/scripts/policy/risk_policy_gate.py
 -       8 ops/scripts/policy/require_coderabbit_review.py
 -       6 ops/scripts/policy/request_coderabbit_rerun.py
 -       5 ops/scripts/policy/validate_risk_policy.py
 -       5 ops/scripts/policy/require_review_agent.py
 -       5 doctrine/policies/CUSTODIAN_AUTHORITY_DOMAINS.md
 -       4 ops/scripts/policy/shepherd_merge_low_risk.sh
 -       4 ops/scripts/policy/emit_merge_audit.py
 -       3 ops/scripts/policy/proof_gate.py
 -       2 ops/scripts/runtime/write_proof_receipt.py
 -       1 ui/dashboard/app.py
 -       1 ops/scripts/policy/wait_for_check_runs.py
 -       1 ops/scripts/policy/governance_surface_gate.sh
 -       1 ops/scripts/policy/governance_surface_audit.sh
 -       1 ops/scripts/cron/morning_briefing_run_and_send.sh
 -       1 ops/scripts/bus/deiphobe
 -       1 ops/scripts/agents/custodian_claim_logger.py
 -       1 ops/scripts/README.md
 -       1 doctrine/playbooks/agent_management.md
 -       1 doctrine/QUICKSTART.md
 -       1 agents/rembrandt/SOUL.md
 -       1 agents/rembrandt/RUNBOOK.md
 -       1 agents/peabody/SOUL.md
 -       1 agents/minion/SOUL.md
 -       1 agents/minion/RUNBOOK.md
 -       1 agents/deiphobe/MANAGER_RUNBOOK.md

## Detailed matches (first 300 lines)

doctrine/QUICKSTART.md:7:- Agents publish structured state to the team bus. If it’s not on the bus, it didn’t happen. Deiphobe is the approval authority.
doctrine/policies/CUSTODIAN_AUTHORITY_DOMAINS.md:22:Custodian operates under a bounded authority model:
doctrine/policies/CUSTODIAN_AUTHORITY_DOMAINS.md:103:Custodian must not assert authority over:
doctrine/policies/CUSTODIAN_AUTHORITY_DOMAINS.md:129:Deiphobe retains full authority over:
doctrine/policies/CUSTODIAN_AUTHORITY_DOMAINS.md:162:- expand Custodian’s authority
doctrine/policies/CUSTODIAN_AUTHORITY_DOMAINS.md:166:All authority changes require explicit doctrine updates.
doctrine/playbooks/agent_management.md:4:Agents don’t “chat”. They publish structured state. Deiphobe routes work and is the only approval authority.
ops/scripts/README.md:20:- deiphobe                 : emit APPROVAL / UNBLOCKED (authority wrapper)
ops/scripts/runtime/write_proof_receipt.py:148:        "schema": "openclaw.proof_receipt.v1",
ops/scripts/runtime/write_proof_receipt.py:165:    print(f"proof_receipt={receipt_path}")
ops/scripts/bus/deiphobe:5:Unified authority emitter for the OpenClaw agent team bus.
ops/scripts/agents/custodian_claim_logger.py:19:    ap.add_argument("--receipt", required=True, help="Absolute path to a proof receipt JSON.")
agents/peabody/SOUL.md:7:Authority: Descriptive only (no routing or runtime authority)
ops/scripts/cron/morning_briefing_run_and_send.sh:12:"$WS/modules/briefings/scripts/telegram_send_latest_briefing.sh"
agents/rembrandt/RUNBOOK.md:8:- `AGENTS.md` (authority model and governance boundaries)
ui/dashboard/app.py:77:        "peabody": f"[auto] Peabody received: \"{short}\". I can map this against policy gates and approval flow.",
ops/scripts/policy/governance_surface_audit.sh:8:PATTERN='(risk_policy\.yml|risk[_ -]?policy|risk[_ -]?tier|proof_policy\.yml|proof[_ -]?policy|proof[_ -]?receipt|execution[_ -]?receipt|merge[_ -]?gate|policy[_ -]?gate|authority|authz|coderabbit|review[_ -]?agent|require_coderabbit|shepherd_merge|wait_for_check_runs|telegram|sendMessage|api\.telegram)'
ops/scripts/policy/require_coderabbit_review.py:4:BOT_LOGINS = {"coderabbitai[bot]", "coderabbitai"}  # be tolerant
ops/scripts/policy/require_coderabbit_review.py:14:def coderabbit_checkrun_success(payload: dict) -> bool:
ops/scripts/policy/require_coderabbit_review.py:15:    # Accept if any check-run from coderabbit is completed/success.
ops/scripts/policy/require_coderabbit_review.py:19:        if app in ("coderabbitai", "coderabbit") or name.lower().startswith("coderabbit"):
ops/scripts/policy/require_coderabbit_review.py:24:def coderabbit_status_success(payload: dict) -> bool:
ops/scripts/policy/require_coderabbit_review.py:77:        checkrun_ok = coderabbit_checkrun_success(check_runs_json)
ops/scripts/policy/require_coderabbit_review.py:78:        status_ok = coderabbit_status_success(status_json)
ops/scripts/policy/require_coderabbit_review.py:88:            if user not in BOT_LOGINS and "coderabbit" not in user.lower():
ops/scripts/policy/require_review_agent.py:9:BOT_LOGINS = {"coderabbitai[bot]", "coderabbitai"}
ops/scripts/policy/require_review_agent.py:83:            if user not in BOT_LOGINS and "coderabbit" not in user.lower():
ops/scripts/policy/require_review_agent.py:85:            if "Summary by CodeRabbit" not in body and "coderabbit" not in body.lower():
ops/scripts/policy/require_review_agent.py:102:            print("OK: review-agent evidence is current-head aligned:", json.dumps(match))
ops/scripts/policy/require_review_agent.py:108:        f"FAIL: no review-agent evidence for current HEAD_SHA within {timeout_minutes} minutes",
ops/scripts/policy/emit_merge_audit.py:64:    ap.add_argument("--risk-tier", default=_getenv("RISK_TIER"))
ops/scripts/policy/emit_merge_audit.py:85:    if not args.risk_tier:
ops/scripts/policy/emit_merge_audit.py:86:        die("risk-tier is required (set RISK_TIER or pass --risk-tier)")
ops/scripts/policy/emit_merge_audit.py:96:        "riskTier": args.risk_tier,
ops/scripts/policy/wait_for_check_runs.py:45:    ignore = {os.environ.get("GATE_CHECK_NAME", "risk-policy-gate").strip()}
ops/scripts/policy/shepherd_merge_low_risk.sh:101:policy_source="ops/policy/risk_policy.yml"
ops/scripts/policy/shepherd_merge_low_risk.sh:102:check_source="risk_policy.yml"
ops/scripts/policy/shepherd_merge_low_risk.sh:114:  echo "[shepherd] using required_checks from risk_policy.yml"
ops/scripts/policy/shepherd_merge_low_risk.sh:117:p = yaml.safe_load(open("ops/policy/risk_policy.yml", "r", encoding="utf-8"))
ops/scripts/policy/validate_risk_policy.py:3:validate_risk_policy.py
ops/scripts/policy/validate_risk_policy.py:5:Validates ops/policy/risk_policy.yml has the required shape/fields.
ops/scripts/policy/validate_risk_policy.py:23:POLICY_PATH = Path("ops/policy/risk_policy.yml")
ops/scripts/policy/validate_risk_policy.py:99:        if "require_coderabbit_head" in t:
ops/scripts/policy/validate_risk_policy.py:100:            require_bool(t["require_coderabbit_head"], f"root.tiers.{tier}.require_coderabbit_head")
agents/rembrandt/SOUL.md:19:- Does not make security decisions without Custodian/Deiphobe authority where required.
ops/scripts/policy/proof_gate.py:30:    ap = argparse.ArgumentParser(description="Proof Gate: fail if claim keywords appear without proof_receipt= or EVIDENCE: block.")
ops/scripts/policy/proof_gate.py:31:    ap.add_argument("--policy", default="ops/policy/proof_policy.yml")
ops/scripts/policy/proof_gate.py:43:    proof_token = str(cfg.get("proofReceiptToken", "proof_receipt="))
agents/deiphobe/MANAGER_RUNBOOK.md:98:Deiphobe retains full authority over:
ops/scripts/policy/risk_policy_gate.py:7:POLICY_PATH = Path("ops/policy/risk_policy.yml")
ops/scripts/policy/risk_policy_gate.py:22:        die("risk_policy.yml not found; policy contract required.", code=2)
ops/scripts/policy/risk_policy_gate.py:56:def enforce_review_agent(require_coderabbit_head: bool, head: str) -> bool:
ops/scripts/policy/risk_policy_gate.py:57:    if not require_coderabbit_head:
ops/scripts/policy/risk_policy_gate.py:63:    script = Path("ops/scripts/policy/require_coderabbit_review.py")
ops/scripts/policy/risk_policy_gate.py:67:        die("GITHUB_TOKEN is required to enforce coderabbit head review in PR context", code=2)
ops/scripts/policy/risk_policy_gate.py:173:    review_agent_enforced = enforce_review_agent(bool(tier_config.get("require_coderabbit_head")), head)
ops/scripts/policy/risk_policy_gate.py:190:        "reviewAgentEnforced": review_agent_enforced
agents/minion/SOUL.md:52:- Minion operates as Deiphobe's chief of staff and must follow Deiphobe's policy constraints and the authority hierarchy in AGENTS.md.
ops/scripts/policy/governance_surface_gate.sh:34:PATTERN='(risk_policy\.yml|risk[_ -]?policy|risk[_ -]?tier|proof_policy\.yml|proof[_ -]?policy|proof[_ -]?receipt|execution[_ -]?receipt|merge[_ -]?gate|policy[_ -]?gate|authority|authz|coderabbit|review[_ -]?agent|require_coderabbit|shepherd_merge|wait_for_check_runs|telegram|sendMessage|api\.telegram)'
agents/minion/RUNBOOK.md:7:1. Read AGENTS.md and Deiphobe's SOUL.md for authority boundaries.
ops/scripts/policy/request_coderabbit_rerun.py:17:- CODERABBIT_MENTION (default: @coderabbitai)
ops/scripts/policy/request_coderabbit_rerun.py:30:MARKER = "<!-- coderabbit-auto-rerun -->"
ops/scripts/policy/request_coderabbit_rerun.py:77:def coderabbit_evidence_ok(token: str, repo: str, sha: str) -> bool:
ops/scripts/policy/request_coderabbit_rerun.py:90:        if "coderabbit" in name or app in ("coderabbitai", "coderabbit"):
ops/scripts/policy/request_coderabbit_rerun.py:123:    mention = os.environ.get("CODERABBIT_MENTION") or "@coderabbitai"
ops/scripts/policy/request_coderabbit_rerun.py:135:    if coderabbit_evidence_ok(token, repo, head_sha):

## Notes
- This report is evidence for refactoring governance into a single surface.
