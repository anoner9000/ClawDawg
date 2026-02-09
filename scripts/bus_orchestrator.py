#!/usr/bin/env python3
"""
bus_orchestrator.py - Dry-run orchestrator service for Deiphobe.

Behavior: scans team_bus.jsonl for ORCHESTRATE events and, in dry-run mode,
appends corresponding route/escalate events to the bus. Requires events to include
'action','target_agent','task_id','dry_run'. This script is dry-run only and will
not perform filesystem changes.
"""
import json,os,datetime,time
BUS=os.path.expanduser('~/.openclaw/runtime/logs/team_bus.jsonl')
STATE_FILE=os.path.expanduser('~/.openclaw/runtime/var/bus_orchestrator.state')

os.makedirs(os.path.dirname(BUS),exist_ok=True)
os.makedirs(os.path.dirname(STATE_FILE),exist_ok=True)

def load_state():
    if not os.path.exists(STATE_FILE):
        return 0
    try:
        return int(open(STATE_FILE).read().strip() or 0)
    except Exception:
        return 0

def save_state(pos):
    open(STATE_FILE,'w').write(str(pos))

def now_ts():
    return datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat()

def append_event(ev):
    with open(BUS,'a') as f:
        f.write(json.dumps(ev)+"\n")

def process_orchestrate(ev):
    action=ev.get('action')
    target=ev.get('target_agent')
    task_id=ev.get('task_id')
    dry=ev.get('dry_run',True)
    summary=f"orchestrator: {action} -> {target} for {task_id} (dry_run={dry})"
    if dry:
        out={'ts':now_ts(),'actor':'deiphobe','type':'ORCHESTRATION_NOTICE','action':action,'target_agent':target,'task_id':task_id,'dry_run':True,'summary':summary}
        append_event(out)
        # Also append a suggested route for target agent
        route={'ts':now_ts(),'actor':'deiphobe','action':'route','task_id':task_id,'owner':target,'summary':f'suggested by orchestrator ({action})','dry_run':True}
        append_event(route)
    else:
        # live mode - not allowed in this dry-run script
        out={'ts':now_ts(),'actor':'deiphobe','type':'ORCHESTRATION_BLOCKED','summary':'Live orchestration not enabled in dry-run orchestrator','details':{'requested_action':action,'target':target,'task_id':task_id}}
        append_event(out)

def main(poll_interval=2):
    last_pos=load_state()
    while True:
        try:
            with open(BUS,'r') as f:
                f.seek(last_pos)
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        ev=json.loads(line)
                    except Exception:
                        continue
                    if ev.get('type')=='ORCHESTRATE' or ev.get('type')=='ORCHESTRATE_REQUEST':
                        process_orchestrate(ev)
                last_pos=f.tell()
                save_state(last_pos)
        except FileNotFoundError:
            pass
        except Exception:
            pass
        time.sleep(poll_interval)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--once',action='store_true')
    args=parser.parse_args()
    if args.once:
        # run a single pass
        last_pos=load_state()
        try:
            with open(BUS,'r') as f:
                f.seek(last_pos)
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        ev=json.loads(line)
                    except Exception:
                        continue
                    if ev.get('type') in ('ORCHESTRATE','ORCHESTRATE_REQUEST'):
                        process_orchestrate(ev)
                last_pos=f.tell()
                save_state(last_pos)
        except FileNotFoundError:
            pass
    else:
        main()
