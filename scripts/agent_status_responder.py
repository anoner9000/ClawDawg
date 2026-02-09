#!/usr/bin/env python3
"""
agent_status_responder.py - simple responder to post STATUS events for an agent.
Usage: agent_status_responder.py --agent <name> [--status idle|in_process|error|complete] [--summary "..."]
This script appends a STATUS event to team_bus.jsonl and persists it under runtime status snapshots.
"""
import argparse, json, os, datetime

BUS=os.path.expanduser('~/.openclaw/runtime/logs/team_bus.jsonl')
STATUS_DIR=os.path.expanduser('~/.openclaw/runtime/logs/status/agents')

parser=argparse.ArgumentParser()
parser.add_argument('--agent',required=True)
parser.add_argument('--status',default='idle',choices=['idle','in_process','error','complete'])
parser.add_argument('--progress',type=int,default=0)
parser.add_argument('--summary',default='')
parser.add_argument('--task_id',default=None)
parser.add_argument('--dry_run',action='store_true')
args=parser.parse_args()

now=datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat()
event={'ts':now,'actor':args.agent,'type':'STATUS','task_id':args.task_id,'status':args.status,'progress':args.progress,'summary':args.summary or ('No active tasks' if args.status=='idle' else args.summary),'dry_run':args.dry_run}

os.makedirs(os.path.dirname(BUS),exist_ok=True)
with open(BUS,'a') as f:
    f.write(json.dumps(event)+"\n")

# persist per-agent latest snapshot
os.makedirs(STATUS_DIR,exist_ok=True)
latest_path=os.path.join(STATUS_DIR,f"{args.agent}.latest.json")
with open(latest_path,'w') as lf:
    json.dump(event,lf)
# also append to per-agent history
hist_dir=os.path.expanduser('~/.openclaw/runtime/logs/status/agents_history')
os.makedirs(hist_dir,exist_ok=True)
with open(os.path.join(hist_dir,f"{args.agent}.jsonl"),'a') as hf:
    hf.write(json.dumps(event)+"\n")

print('Posted STATUS for',args.agent)
