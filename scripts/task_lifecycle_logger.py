#!/usr/bin/env python3
"""
task_lifecycle_logger.py - helper to log TASK_ACK, TASK_UPDATE, STATUS_REPORT events
Usage:
  task_lifecycle_logger.py ack --agent AGENT --task TASK_ID --summary "..." [--eta "..."] [--production]
  task_lifecycle_logger.py update --agent AGENT --task TASK_ID --state in_process|complete|error --summary "..." [--details PATH] [--production]
  task_lifecycle_logger.py report --agent AGENT --task TASK_ID --report PATH --summary "..." [--production]

Behavior:
- Appends canonical events to ~/.openclaw/runtime/logs/team_bus.jsonl
- Persists the same JSON to ~/.openclaw/runtime/logs/status/tasks/<task_id>/<agent>.jsonl
- Updates per-task latest snapshot: ~/.openclaw/runtime/logs/status/tasks/<task_id>/latest.json
- If --production is set, marking state=complete requires an operator token file at ~/.openclaw/runtime/var/operator_tokens/CompleteApply
"""
import argparse, json, os, datetime, sys

BUS=os.path.expanduser('~/.openclaw/runtime/logs/team_bus.jsonl')
STATUS_ROOT=os.path.expanduser('~/.openclaw/runtime/logs/status/tasks')
OP_TOKEN_DIR=os.path.expanduser('~/.openclaw/runtime/var/operator_tokens')

os.makedirs(os.path.dirname(BUS),exist_ok=True)

now=lambda: datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat()

parser=argparse.ArgumentParser()
sub=parser.add_subparsers(dest='cmd')

p_ack=sub.add_parser('ack')
p_ack.add_argument('--agent',required=True)
p_ack.add_argument('--task',required=True)
p_ack.add_argument('--summary',required=True)
p_ack.add_argument('--eta')
p_ack.add_argument('--production',action='store_true')

p_up=sub.add_parser('update')
p_up.add_argument('--agent',required=True)
p_up.add_argument('--task',required=True)
p_up.add_argument('--state',required=True,choices=['in_process','error','complete'])
p_up.add_argument('--summary',required=True)
p_up.add_argument('--details')
p_up.add_argument('--production',action='store_true')

p_rep=sub.add_parser('report')
p_rep.add_argument('--agent',required=True)
p_rep.add_argument('--task',required=True)
p_rep.add_argument('--report',required=True)
p_rep.add_argument('--summary',required=True)
p_rep.add_argument('--production',action='store_true')

args=parser.parse_args()
if not args.cmd:
    parser.print_help(); sys.exit(2)

def write_event(ev, task_id, agent):
    # append to bus
    with open(BUS,'a') as f:
        f.write(json.dumps(ev)+"\n")
    # persist per-task per-agent
    task_dir=os.path.join(STATUS_ROOT, task_id)
    os.makedirs(task_dir, exist_ok=True)
    per_agent_file=os.path.join(task_dir, f"{agent}.jsonl")
    with open(per_agent_file,'a') as f:
        f.write(json.dumps(ev)+"\n")
    # update latest snapshot for task
    latest=os.path.join(task_dir,'latest.json')
    try:
        with open(latest,'w') as lf:
            json.dump(ev,lf)
    except Exception:
        pass
    # set permissions (best-effort)
    try:
        os.chmod(per_agent_file,0o640)
    except Exception:
        pass

if args.cmd=='ack':
    ev={'ts':now(),'actor':args.agent,'type':'TASK_ACK','task_id':args.task,'assigned_by':'deiphobe','owner':args.agent,'summary':args.summary}
    if args.eta:
        ev['eta']=args.eta
    if args.production:
        ev['production']=True
    write_event(ev,args.task,args.agent)
    print('ACK logged')

elif args.cmd=='update':
    # production complete gating
    if args.production and args.state=='complete':
        token_file=os.path.join(OP_TOKEN_DIR,'CompleteApply')
        if not os.path.exists(token_file):
            # log attempt and refuse
            ev={'ts':now(),'actor':args.agent,'type':'TASK_UPDATE','task_id':args.task,'state':'blocked','summary':'Attempted to mark complete but operator token missing','details':{'required_token':'CompleteApply'}}
            write_event(ev,args.task,args.agent)
            print('ERROR: operator token required to mark complete on production. Logged attempt.'); sys.exit(1)
    ev={'ts':now(),'actor':args.agent,'type':'TASK_UPDATE','task_id':args.task,'state':args.state,'summary':args.summary}
    if args.details:
        ev['details']=args.details
    if args.production:
        ev['production']=True
    write_event(ev,args.task,args.agent)
    print('Update logged')

elif args.cmd=='report':
    ev={'ts':now(),'actor':args.agent,'type':'STATUS_REPORT','task_id':args.task,'report_path':args.report,'summary':args.summary}
    if args.production:
        ev['production']=True
    write_event(ev,args.task,args.agent)
    print('Report logged')
