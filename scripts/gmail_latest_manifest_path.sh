#!/usr/bin/env bash
set -euo pipefail

LOG_DIR="${HOME}/.openclaw/runtime/logs"

latest="$(ls -1t "${LOG_DIR}"/mail_cleanup_manifest_*.jsonl 2>/dev/null | head -n 1 || true)"
if [[ -z "${latest}" ]]; then
  echo "No manifest files found in ${LOG_DIR}" >&2
  exit 1
fi

echo "${latest}"
