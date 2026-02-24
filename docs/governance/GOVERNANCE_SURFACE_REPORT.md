# Governance Surface Report

- Generated: 2026-02-24T16:35:05Z
- Pattern: `(risk[_ -]?tier|risk_policy|proof_policy|proof[_ -]?receipt|execution[_ -]?receipt|state[ =:]*complete|TASK_UPDATE|PASS|FAIL|authority|authz|merge[_ -]?gate|policy[_ -]?gate|verification|preflight|investigation-gate|CodeRabbit|telegram|sendMessage)`

## Top matches (file-level)

 -      25 ops/scripts/agents/rembrandt_worker.py
 -       8 ops/scripts/policy/require_coderabbit_review.py
 -       7 ops/scripts/policy/shepherd_merge_low_risk.sh
 -       5 ops/scripts/policy/request_coderabbit_rerun.py
 -       5 ops/scripts/policy/proof_gate.py
 -       5 doctrine/policies/CUSTODIAN_AUTHORITY_DOMAINS.md
 -       5 agents/minion/RUNBOOK.md
 -       4 scripts/task_lifecycle_logger.py
 -       4 ops/scripts/policy/validate_task_completion.py
 -       4 ops/scripts/policy/emit_merge_audit.py
 -       4 ops/scripts/backups/backup_sftp.sh
 -       3 ui/dashboard/app.py
 -       3 ops/scripts/runtime/write_proof_receipt.py
 -       3 ops/scripts/policy/validate_risk_policy.py
 -       3 ops/scripts/policy/risk_policy_gate.py
 -       3 ops/scripts/legacy/yahoo_calendar_scan_and_send.sh.bak.20260206_030817
 -       3 ops/scripts/cron/yahoo_calendar_scan_and_send.sh
 -       3 agents/rembrandt/RUNBOOK.md
 -       3 agents/peabody/SOUL.md
 -       2 ops/scripts/policy/wait_for_check_runs.py
 -       2 ops/scripts/policy/require_review_agent.py
 -       2 ops/scripts/legacy/usage_append_from_latest_response.sh.bak.20260207_120011
 -       2 ops/scripts/agents/agent_compliance_check.py
 -       2 doctrine/playbooks/agent_management.md
 -       2 doctrine/QUICKSTART.md
 -       2 agents/peabody/RUNBOOK.md
 -       2 agents/custodian/RUNBOOK.md
 -       1 ops/scripts/policy/governance_surface_gate.sh
 -       1 ops/scripts/policy/governance_surface_audit.sh
 -       1 ops/scripts/cron/morning_briefing_run_and_send.sh
 -       1 ops/scripts/bus/deiphobe
 -       1 ops/scripts/agents/query_status.py
 -       1 ops/scripts/agents/persist_status.sh
 -       1 ops/scripts/agents/custodian_claim_logger.py
 -       1 ops/scripts/agents/agent_status_responder.py
 -       1 ops/scripts/agents/README_STATUS_PROTOCOL.md
 -       1 ops/scripts/README.md
 -       1 agents/scribe/RUNBOOK.md
 -       1 agents/rembrandt/SOUL.md
 -       1 agents/minion/SOUL.md
 -       1 agents/executor-ui/RUNBOOK.md
 -       1 agents/executor-doc/RUNBOOK.md
 -       1 agents/executor-comm/RUNBOOK.md
 -       1 agents/executor-code/RUNBOOK.md
 -       1 agents/deiphobe/RUNBOOK.md
 -       1 agents/deiphobe/MANAGER_RUNBOOK.md
 -       1 agents/custodian/SOUL.md

## Detailed matches (first 300 lines)

doctrine/QUICKSTART.md:7:- Agents publish structured state to the team bus. If it’s not on the bus, it didn’t happen. Deiphobe is the approval authority.
doctrine/QUICKSTART.md:45:- Auditors perform verification before closure; Deiphobe records the final decision.
doctrine/policies/CUSTODIAN_AUTHORITY_DOMAINS.md:22:Custodian operates under a bounded authority model:
doctrine/policies/CUSTODIAN_AUTHORITY_DOMAINS.md:103:Custodian must not assert authority over:
doctrine/policies/CUSTODIAN_AUTHORITY_DOMAINS.md:129:Deiphobe retains full authority over:
doctrine/policies/CUSTODIAN_AUTHORITY_DOMAINS.md:162:- expand Custodian’s authority
doctrine/policies/CUSTODIAN_AUTHORITY_DOMAINS.md:166:All authority changes require explicit doctrine updates.
agents/peabody/RUNBOOK.md:45:printf '%s' '{"actor":"AGENT_NAME","type":"TASK_UPDATE","task_id":"TASK_ID","state":"in_process","summary":"Working..."}' | ~/.openclaw/workspace/ops/scripts/status/post_event.sh
agents/peabody/RUNBOOK.md:49:printf '%s' '{"actor":"AGENT_NAME","type":"TASK_UPDATE","task_id":"TASK_ID","state":"complete","summary":"Done"}' | ~/.openclaw/workspace/ops/scripts/status/post_event.sh
agents/peabody/SOUL.md:7:Authority: Descriptive only (no routing or runtime authority)
agents/peabody/SOUL.md:16:- producing clear diffs and verification steps
agents/peabody/SOUL.md:25:- Recommends concrete verification commands
ops/scripts/backups/backup_sftp.sh:3:# Assumes key-based auth to SFTP host is set up for the user and environment variables are set for RESTIC_PASSWORD
ops/scripts/backups/backup_sftp.sh:4:# Example usage: RESTIC_REPOSITORY=sftp:user@host:/path/to/repo RESTIC_PASSWORD_FILE=~/.config/restic/pass restic init
ops/scripts/backups/backup_sftp.sh:7:: ${RESTIC_PASSWORD_FILE:?"Set RESTIC_PASSWORD_FILE to file containing repo password (mode 600)"}
ops/scripts/backups/backup_sftp.sh:8:export RESTIC_PASSWORD=$(cat "$RESTIC_PASSWORD_FILE")
agents/custodian/RUNBOOK.md:2:- Only custodian may emit `state=complete`.
agents/custodian/RUNBOOK.md:5:  - `tasks/<task_id>/receipts/PROOF_VALIDATION.json` with `result=PASS`
doctrine/playbooks/agent_management.md:4:Agents don’t “chat”. They publish structured state. Deiphobe routes work and is the only approval authority.
doctrine/playbooks/agent_management.md:49:- tasks_closed, verification_pass_rate, rework_count
agents/custodian/SOUL.md:2:Verifier. Canonical truth + proof validation. Only agent allowed to complete after PASS validation.
agents/rembrandt/RUNBOOK.md:8:- `AGENTS.md` (authority model and governance boundaries)
agents/rembrandt/RUNBOOK.md:56:printf '%s' '{"actor":"rembrandt","type":"TASK_UPDATE","task_id":"TASK_ID","state":"in_process","summary":"Applying visual system updates"}' | ~/.openclaw/workspace/ops/scripts/status/post_event.sh
agents/rembrandt/RUNBOOK.md:60:printf '%s' '{"actor":"rembrandt","type":"TASK_UPDATE","task_id":"TASK_ID","state":"complete","summary":"Design pass complete"}' | ~/.openclaw/workspace/ops/scripts/status/post_event.sh
agents/rembrandt/SOUL.md:19:- Does not make security decisions without Custodian/Deiphobe authority where required.
ops/scripts/cron/yahoo_calendar_scan_and_send.sh:154:CRED_APP_PASS = RUNTIME / "credentials" / "yahoo_app_password"
ops/scripts/cron/yahoo_calendar_scan_and_send.sh:621:        yahoo_app_pass = read_one_line(CRED_APP_PASS)
ops/scripts/cron/yahoo_calendar_scan_and_send.sh:836:    yahoo_app_pass = read_one_line(CRED_APP_PASS)
agents/executor-comm/RUNBOOK.md:2:- Never emit `state=complete`.
ops/scripts/runtime/write_proof_receipt.py:57:    ap.add_argument("--claim-kind", required=True, help="One of: runtime_state, code_change, verification, commit, etc.")
ops/scripts/runtime/write_proof_receipt.py:148:        "schema": "openclaw.proof_receipt.v1",
ops/scripts/runtime/write_proof_receipt.py:165:    print(f"proof_receipt={receipt_path}")
ops/scripts/cron/morning_briefing_run_and_send.sh:12:"$WS/modules/briefings/scripts/telegram_send_latest_briefing.sh"
agents/scribe/RUNBOOK.md:2:- Never emit `state=complete`.
agents/deiphobe/RUNBOOK.md:2:- Never emit `state=complete`.
ops/scripts/agents/agent_status_responder.py:277:    event = build_base(args.agent, "TASK_UPDATE", args.task_id, args.summary, not args.live)
agents/deiphobe/MANAGER_RUNBOOK.md:98:Deiphobe retains full authority over:
ops/scripts/README.md:20:- deiphobe                 : emit APPROVAL / UNBLOCKED (authority wrapper)
ops/scripts/agents/query_status.py:41:        if ev.get("type") == "TASK_UPDATE":
ops/scripts/bus/deiphobe:5:Unified authority emitter for the OpenClaw agent team bus.
agents/executor-ui/RUNBOOK.md:2:- Never emit `state=complete`.
ops/scripts/agents/README_STATUS_PROTOCOL.md:5:- agent_status_responder.py: emit STATUS/TASK_ACK/TASK_UPDATE/STATUS_REPORT events.
ops/scripts/agents/persist_status.sh:55:tracked = {"STATUS", "TASK_ACK", "TASK_UPDATE", "STATUS_REPORT"}
agents/executor-code/RUNBOOK.md:2:- Never emit `state=complete`.
ops/scripts/agents/custodian_claim_logger.py:19:    ap.add_argument("--receipt", required=True, help="Absolute path to a proof receipt JSON.")
scripts/task_lifecycle_logger.py:3:task_lifecycle_logger.py - helper to log TASK_ACK, TASK_UPDATE, STATUS_REPORT events
scripts/task_lifecycle_logger.py:13:- If --production is set, marking state=complete requires an operator token file at ~/.openclaw/runtime/var/operator_tokens/CompleteApply
scripts/task_lifecycle_logger.py:92:            ev={'ts':now(),'actor':args.agent,'type':'TASK_UPDATE','task_id':args.task,'state':'blocked','summary':'Attempted to mark complete but operator token missing','details':{'required_token':'CompleteApply'}}
scripts/task_lifecycle_logger.py:95:    ev={'ts':now(),'actor':args.agent,'type':'TASK_UPDATE','task_id':args.task,'state':args.state,'summary':args.summary}
ops/scripts/agents/agent_compliance_check.py:46:        "type": "COMPLIANCE_FAIL",
ops/scripts/agents/agent_compliance_check.py:100:    print("❌ AGENT COMPLIANCE FAILED")
agents/executor-doc/RUNBOOK.md:2:- Never emit `state=complete`.
agents/minion/RUNBOOK.md:7:1. Read AGENTS.md and Deiphobe's SOUL.md for authority boundaries.
agents/minion/RUNBOOK.md:34:TASK_UPDATE (state: in_process | error | complete)
agents/minion/RUNBOOK.md:36:{"ts":"2026-02-09T01:10:00-06:00","actor":"minion","type":"TASK_UPDATE","task_id":"TASK_ID","state":"in_process","summary":"Routed to Peabody; awaiting review","details_path":"~/.openclaw/runtime/logs/status/tasks/TASK_ID/minion-notes.md"}
agents/minion/RUNBOOK.md:89:printf '%s' '{"actor":"AGENT_NAME","type":"TASK_UPDATE","task_id":"TASK_ID","state":"in_process","summary":"Working..."}' | ~/.openclaw/workspace/ops/scripts/status/post_event.sh
agents/minion/RUNBOOK.md:93:printf '%s' '{"actor":"AGENT_NAME","type":"TASK_UPDATE","task_id":"TASK_ID","state":"complete","summary":"Done"}' | ~/.openclaw/workspace/ops/scripts/status/post_event.sh
agents/minion/SOUL.md:52:- Minion operates as Deiphobe's chief of staff and must follow Deiphobe's policy constraints and the authority hierarchy in AGENTS.md.
ops/scripts/agents/rembrandt_worker.py:362:    if run_mode not in {"preflight", "verify"}:
ops/scripts/agents/rembrandt_worker.py:366:    # In preflight mode, no mutation is expected yet.
ops/scripts/agents/rembrandt_worker.py:367:    changed_files_raw = [] if run_mode == "preflight" else _git_changed_files(diff_base_used)
ops/scripts/agents/rembrandt_worker.py:379:            if run_mode == "preflight"
ops/scripts/agents/rembrandt_worker.py:472:            and (True if run_mode == "preflight" else checks["build_css_ok"])
ops/scripts/agents/rembrandt_worker.py:473:            and (True if run_mode == "preflight" else checks["theme_source_changed_ok"])
ops/scripts/agents/rembrandt_worker.py:474:            and (True if run_mode == "preflight" else checks["component_coverage_ok"])
ops/scripts/agents/rembrandt_worker.py:475:            and (True if run_mode == "preflight" else checks["base_css_source_ok"])
ops/scripts/agents/rembrandt_worker.py:476:            and (True if run_mode == "preflight" else checks["token_var_presence_ok"])
ops/scripts/agents/rembrandt_worker.py:477:            and (True if run_mode == "preflight" else checks["font_scale_delta_ok"])
ops/scripts/agents/rembrandt_worker.py:478:            and (True if run_mode == "preflight" else checks["radii_changed_ok"])
ops/scripts/agents/rembrandt_worker.py:479:            and (True if run_mode == "preflight" else checks["accent_changed_ok"])
ops/scripts/agents/rembrandt_worker.py:480:            and (True if run_mode == "preflight" else checks["bg_changed_ok"])
ops/scripts/agents/rembrandt_worker.py:494:        elif run_mode != "preflight" and contract.strict_requested and not checks["style_only_change_set_ok"]:
ops/scripts/agents/rembrandt_worker.py:496:        elif run_mode != "preflight" and contract.strict_requested and not checks["theme_source_changed_ok"]:
ops/scripts/agents/rembrandt_worker.py:498:        elif run_mode != "preflight" and contract.strict_requested and not checks["component_coverage_ok"]:
ops/scripts/agents/rembrandt_worker.py:501:        elif run_mode != "preflight" and contract.strict_requested and not checks["base_css_source_ok"]:
ops/scripts/agents/rembrandt_worker.py:503:        elif run_mode != "preflight" and contract.strict_requested and not checks["token_var_presence_ok"]:
ops/scripts/agents/rembrandt_worker.py:505:        elif run_mode != "preflight" and contract.strict_requested and not checks["base_token_var_presence_ok"]:
ops/scripts/agents/rembrandt_worker.py:507:        elif run_mode != "preflight" and contract.strict_requested and not checks["font_scale_delta_ok"]:
ops/scripts/agents/rembrandt_worker.py:509:        elif run_mode != "preflight" and contract.strict_requested and not checks["radii_changed_ok"]:
ops/scripts/agents/rembrandt_worker.py:511:        elif run_mode != "preflight" and contract.strict_requested and not checks["accent_changed_ok"]:
ops/scripts/agents/rembrandt_worker.py:513:        elif run_mode != "preflight" and contract.strict_requested and not checks["bg_changed_ok"]:
ops/scripts/agents/rembrandt_worker.py:517:        elif run_mode != "preflight" and contract.strict_requested and not checks["build_css_ok"]:
ops/scripts/agents/rembrandt_worker.py:555:    ap.add_argument("--mode", choices=["preflight", "verify"], default="verify")
ops/scripts/policy/request_coderabbit_rerun.py:3:Canonical CodeRabbit rerun requester with SHA dedupe.
ops/scripts/policy/request_coderabbit_rerun.py:6:- If CodeRabbit evidence is already success on HEAD_SHA: do nothing.
ops/scripts/policy/request_coderabbit_rerun.py:82:        if (st.get("context") or "") == "CodeRabbit" and st.get("state") == "success":
ops/scripts/policy/request_coderabbit_rerun.py:136:        print("OK: CodeRabbit evidence already present on HEAD_SHA; no rerun needed.")
ops/scripts/policy/request_coderabbit_rerun.py:160:    print("OK: posted canonical CodeRabbit rerun request.")
ops/scripts/policy/risk_policy_gate.py:7:POLICY_PATH = Path("ops/policy/risk_policy.yml")
ops/scripts/policy/risk_policy_gate.py:22:        die("risk_policy.yml not found; policy contract required.", code=2)
ops/scripts/policy/risk_policy_gate.py:167:            print(f"FAIL: control-plane paths changed but no {docs_required} update found.")
ops/scripts/policy/governance_surface_gate.sh:27:PATTERN='(risk[_ -]?tier|proof[_ -]?policy|proof[_ -]?receipt|execution[_ -]?receipt|state[ =:]*complete|TASK_UPDATE|PASS|FAIL|authority|authz|merge[_ -]?gate|policy[_ -]?gate|custodian-only|verification|preflight|investigation-gate|CodeRabbit)'
ops/scripts/policy/proof_gate.py:30:    ap = argparse.ArgumentParser(description="Proof Gate: fail if claim keywords appear without proof_receipt= or EVIDENCE: block.")
ops/scripts/policy/proof_gate.py:31:    ap.add_argument("--policy", default="ops/policy/proof_policy.yml")
ops/scripts/policy/proof_gate.py:43:    proof_token = str(cfg.get("proofReceiptToken", "proof_receipt="))
ops/scripts/policy/proof_gate.py:83:        print("proof_gate: FAIL")
ops/scripts/policy/proof_gate.py:88:    print("proof_gate: PASS")
ops/scripts/policy/validate_task_completion.py:22:    print(f"FAIL: {msg}")
ops/scripts/policy/validate_task_completion.py:91:    if r["result"] != "PASS":
ops/scripts/policy/validate_task_completion.py:92:        fail("PROOF_VALIDATION.result must be PASS for completion")
ops/scripts/policy/validate_task_completion.py:133:        ok("No state=complete events found in bus.")
ops/scripts/policy/shepherd_merge_low_risk.sh:42:        . or ($ev.type=="TASK_UPDATE" and ($ev.state=="complete" or $ev.status=="complete"))
ops/scripts/policy/shepherd_merge_low_risk.sh:50:        . or ($ev.task_id==$t and $ev.type=="TASK_UPDATE" and ($ev.state=="complete" or $ev.status=="complete"))
ops/scripts/policy/shepherd_merge_low_risk.sh:69:    --arg type "TASK_UPDATE" \
ops/scripts/policy/shepherd_merge_low_risk.sh:101:policy_source="ops/policy/risk_policy.yml"
ops/scripts/policy/shepherd_merge_low_risk.sh:102:check_source="risk_policy.yml"
ops/scripts/policy/shepherd_merge_low_risk.sh:114:  echo "[shepherd] using required_checks from risk_policy.yml"
ops/scripts/policy/shepherd_merge_low_risk.sh:117:p = yaml.safe_load(open("ops/policy/risk_policy.yml", "r", encoding="utf-8"))
ops/scripts/policy/wait_for_check_runs.py:45:    ignore = {os.environ.get("GATE_CHECK_NAME", "risk-policy-gate").strip()}
ops/scripts/policy/wait_for_check_runs.py:109:    print(f"FAIL: timed out waiting for required checks on head SHA after {timeout_minutes} minutes", file=sys.stderr)
ops/scripts/policy/validate_risk_policy.py:3:validate_risk_policy.py
ops/scripts/policy/validate_risk_policy.py:5:Validates ops/policy/risk_policy.yml has the required shape/fields.
ops/scripts/policy/validate_risk_policy.py:23:POLICY_PATH = Path("ops/policy/risk_policy.yml")
ops/scripts/policy/require_review_agent.py:85:            if "Summary by CodeRabbit" not in body and "coderabbit" not in body.lower():
ops/scripts/policy/require_review_agent.py:108:        f"FAIL: no review-agent evidence for current HEAD_SHA within {timeout_minutes} minutes",
ops/scripts/policy/emit_merge_audit.py:64:    ap.add_argument("--risk-tier", default=_getenv("RISK_TIER"))
ops/scripts/policy/emit_merge_audit.py:85:    if not args.risk_tier:
ops/scripts/policy/emit_merge_audit.py:86:        die("risk-tier is required (set RISK_TIER or pass --risk-tier)")
ops/scripts/policy/emit_merge_audit.py:96:        "riskTier": args.risk_tier,
ui/dashboard/app.py:77:        "peabody": f"[auto] Peabody received: \"{short}\". I can map this against policy gates and approval flow.",
ui/dashboard/app.py:296:                "preflight",
ui/dashboard/app.py:488:    if t in {"ERROR", "FAILED", "BLOCKED"} or "ERROR" in t or "FAILED" in t:
ops/scripts/legacy/yahoo_calendar_scan_and_send.sh.bak.20260206_030817:149:CRED_APP_PASS = RUNTIME / "credentials" / "yahoo_app_password"
ops/scripts/legacy/yahoo_calendar_scan_and_send.sh.bak.20260206_030817:579:        yahoo_app_pass = read_one_line(CRED_APP_PASS)
ops/scripts/legacy/yahoo_calendar_scan_and_send.sh.bak.20260206_030817:771:    yahoo_app_pass = read_one_line(CRED_APP_PASS)
ops/scripts/policy/governance_surface_audit.sh:8:PATTERN='(risk[_ -]?tier|risk_policy|proof_policy|proof[_ -]?receipt|execution[_ -]?receipt|state[ =:]*complete|TASK_UPDATE|PASS|FAIL|authority|authz|merge[_ -]?gate|policy[_ -]?gate|verification|preflight|investigation-gate|CodeRabbit|telegram|sendMessage)'
ops/scripts/policy/require_coderabbit_review.py:25:    # Accept commit status context "CodeRabbit" == success.
ops/scripts/policy/require_coderabbit_review.py:27:        if (st.get("context") or "") == "CodeRabbit" and st.get("state") == "success":
ops/scripts/policy/require_coderabbit_review.py:96:            # Weak: comment indicates CodeRabbit summary and is after last commit time
ops/scripts/policy/require_coderabbit_review.py:97:            if "Summary by CodeRabbit" in body and latest_time and is_after(created, latest_time):
ops/scripts/policy/require_coderabbit_review.py:114:            print("OK: CodeRabbit comment references current head SHA:", json.dumps(matched_strong))
ops/scripts/policy/require_coderabbit_review.py:117:            print("OK: CodeRabbit summary comment posted after latest commit:", json.dumps(matched_weak))
ops/scripts/policy/require_coderabbit_review.py:120:            print("OK: CodeRabbit evidence found on current head (check-run or status context).")
ops/scripts/policy/require_coderabbit_review.py:125:    print(f"FAIL: no CodeRabbit review evidence for current head SHA within {timeout_minutes} minutes", file=sys.stderr)
ops/scripts/legacy/usage_append_from_latest_response.sh.bak.20260207_120011:15:FAIL_LOG="$HB_DIR/usage_append_failures.log"
ops/scripts/legacy/usage_append_from_latest_response.sh.bak.20260207_120011:112:        with open(os.path.expanduser("$FAIL_LOG"), "a", encoding='utf-8') as lf:

## Notes
- This report is evidence for refactoring governance into a single surface.
