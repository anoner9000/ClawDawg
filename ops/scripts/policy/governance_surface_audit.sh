#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-.}"

OUT="docs/governance/GOVERNANCE_SURFACE_REPORT.md"
mkdir -p docs/governance

PATTERN='(risk_policy\.yml|risk[_ -]?policy|risk[_ -]?tier|proof_policy\.yml|proof[_ -]?policy|proof[_ -]?receipt|execution[_ -]?receipt|merge[_ -]?gate|policy[_ -]?gate|authority|authz|coderabbit|review[_ -]?agent|require_coderabbit|shepherd_merge|wait_for_check_runs|telegram|sendMessage|api\.telegram)'

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
