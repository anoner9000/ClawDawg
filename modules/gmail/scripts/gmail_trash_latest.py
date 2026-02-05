#!/usr/bin/env python3
"""
gmail_trash_latest.py
Simplified wrapper: automatically finds the most recent quarantine log and moves to trash.
Only requires confirmation phrase - no path needed.
"""
import os, sys, glob, argparse
from pathlib import Path

HOME = os.path.expanduser('~')
LOG_DIR = os.path.join(HOME, '.openclaw', 'runtime', 'logs')
APPROVAL_PHRASE = 'TrashApply'

def find_latest_quarantine_log():
    pattern = os.path.join(LOG_DIR, 'mail_cleanup_manifest_*.jsonl.quarantine_log')
    logs = glob.glob(pattern)
    if not logs:
        return None
    # Sort by modification time, most recent first
    logs.sort(key=os.path.getmtime, reverse=True)
    return logs[0]

def main():
    p = argparse.ArgumentParser(description='Move quarantined emails to trash (uses most recent quarantine log)')
    p.add_argument('--confirm', required=True, help='Confirmation phrase required')
    p.add_argument('--apply', action='store_true', help='Actually execute (otherwise dry-run)')
    args = p.parse_args()
    
    if args.confirm != APPROVAL_PHRASE:
        print(f'ERROR: Incorrect confirmation phrase')
        sys.exit(1)
    
    log_path = find_latest_quarantine_log()
    if not log_path:
        print('ERROR: No quarantine log found')
        sys.exit(1)
    
    print(f'Using quarantine log: {log_path}')
    
    # Call the original trash script with the found path
    import subprocess
    cmd = [
        'python3',
        os.path.join(HOME, '.openclaw', 'workspace', 'scripts', 'gmail_cleanup_trash.py'),
        '--quarantine-log', log_path,
        '--confirm', args.confirm
    ]
    if args.apply:
        cmd.append('--apply')
    
    subprocess.run(cmd)

if __name__ == '__main__':
    main()
