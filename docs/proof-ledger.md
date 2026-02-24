# Proof Ledger Contract (Custodian)

Rule: **Every claim needs proof.**

A claim is any statement containing `claimKeywords` from `ops/policy/proof_policy.yml`
(e.g., "verified", "committed", "patched", "running", "returns 200", "pid").

## How to comply

1. Producer agent writes a Proof Receipt:

```bash
ops/scripts/runtime/write_proof_receipt.py \
  --agent rembrandt \
  --claim-kind code_change \
  --claim-text "Patched wrapper to be listener-pid based and localhost-only" \
  --evidence-file "ops/scripts/ui/clawdawgui:1-80" \
  --evidence-cmd "rg -n 'wait_for_listener\\(' ops/scripts/ui/clawdawgui"
```

2. Include receipt token in output/event text:

```text
proof_receipt=/abs/path/to/claim-...json
```

3. Custodian appends receipt reference to ledger:

```bash
ops/scripts/agents/custodian_claim_logger.py \
  --receipt /abs/path/to/claim-...json
```

4. Run proof gate against outputs:

```bash
ops/scripts/policy/proof_gate.py --file /path/to/agent_output.txt --context rembrandt
```

## Artifacts

- Policy: `ops/policy/proof_policy.yml`
- Receipt writer: `ops/scripts/runtime/write_proof_receipt.py`
- Ledger logger: `ops/scripts/agents/custodian_claim_logger.py`
- Gate: `ops/scripts/policy/proof_gate.py`
- Ledger file: `~/.openclaw/runtime/logs/custodian_claims.jsonl`
