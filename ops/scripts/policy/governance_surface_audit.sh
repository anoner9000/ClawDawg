#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-.}"

OUT="docs/governance/GOVERNANCE_SURFACE_REPORT.md"
mkdir -p docs/governance

PATTERN='(risk[_ -]?tier|risk_policy|proof_policy|proof[_ -]?receipt|execution[_ -]?receipt|state[ =:]*complete|TASK_UPDATE|PASS|FAIL|authority|authz|merge[_ -]?gate|policy[_ -]?gate|verification|preflight|investigation-gate|CodeRabbit|telegram|sendMessage)'

{
  echo "# Governance Surface Report"
  echo
  echo "- Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "- Pattern: \`$PATTERN\`"
  echo
  echo "## Top matches (file-level)"
  echo
  rg -n -S --no-heading "$PATTERN" agents ui ops/scripts scripts doctrine 2>/dev/null \
    | awk -F: '{print $1}' \
    | sort | uniq -c | sort -nr | head -n 80 \
    | sed 's/^/ - /'
  echo
  echo "## Detailed matches (first 300 lines)"
  echo
  rg -n -S "$PATTERN" agents ui ops/scripts scripts doctrine 2>/dev/null | head -n 300
  echo
  echo "## Notes"
  echo "- This report is evidence for refactoring governance into a single surface."
} > "$OUT"

echo "Wrote $OUT"
