#!/usr/bin/env bash
# logrotate_openclaw.sh
# Creates gzip archives of old log files and moves them to an archive directory.
# Approved by operator (do NOT enable automatically).

set -euo pipefail

RUNTIME_DIR="${HOME}/.openclaw/runtime/logs"
ARCHIVE_DIR="${RUNTIME_DIR}/archive/rotated"
KEEP_DAYS=30
COMPRESS_DAYS=14

mkdir -p "$ARCHIVE_DIR"

# Find log-like files older than COMPRESS_DAYS and gzip them (if not already .gz)
find "$RUNTIME_DIR" -type f -mtime +$COMPRESS_DAYS ! -name "*.gz" -print0 \
  | while IFS= read -r -d '' file; do
    # skip the archive directory itself
    case "$file" in
      "$ARCHIVE_DIR"* ) continue ;;
    esac
    # Compress into same directory then move to archive
    echo "Compressing: $file"
    if gzip -9 -- "$file"; then
      gzfile="${file}.gz"
      mv -v -- "$gzfile" "$ARCHIVE_DIR/"
    fi
  done

# Remove archived files older than KEEP_DAYS
find "$ARCHIVE_DIR" -type f -mtime +$KEEP_DAYS -print0 \
  | while IFS= read -r -d '' old; do
    echo "Removing old archive: $old"
    rm -f -- "$old"
  done

# Summary
echo "Rotation complete. Archive dir: $ARCHIVE_DIR"
