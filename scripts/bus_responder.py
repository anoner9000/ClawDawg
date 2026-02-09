#!/usr/bin/env python3
"""
bus_responder.py - simple responder that appends ACK or REVIEW_OK events when a REVIEW_REQUEST targets a monitored agent.
Usage: bus_responder.py --agent scribe [--once]

Note: This is intentionally simple and designed for manual invocation or supervised runs. It
will scan team_bus.jsonl and for each REVIEW_REQUEST targeting the agent, append an ACK event
if none exists from that agent.
"""
import argparse, json, os, datetime

BUS=os.path.expanduser('~/.openclaw/runtime/logs/team_bus.jsonl')

parser=argparse.ArgumentParser()
parser.add_argument('--agent',required=True)
parser.add_argument('--once',action='store_true')
parser.add_argument('--auto_ok',action='store_true',help='Post REVIEW_OK instead of ACK (use with caution)')
args=parser.parse_args()
agent=args.agent

os.makedirs(os.path.dirname(BUS),exist_ok=True)

# Load events
with open(BUS,'r') as f:
    lines=[l.strip() for l in f if l.strip()]
    events=[json.loads(l) for l in lines]

# Find REVIEW_REQUESTs targeting agent
pending=[]
for e in events:
    t=e.get('type')
    if t=='REVIEW_REQUEST':
        target=e.get('target') or e.get('requested') or e.get('target_agent')
        if not target:
            # sometimes target may be in 'requested' or 'target' as comma list
            continue
        if isinstance(target,str) and agent in target.split(','):
            pending.append(e)

# For each pending, check if agent already ACKed or REVIEW_OK
for req in pending:
    req_id=req.get('task_id') or req.get('summary')
    already=False
    for e in events:
        if e.get('actor')==agent and e.get('type') in ('ACK','REVIEW_OK','REVIEW_REJECT'):
            # crude check: same target and artifact
            if e.get('target')==req.get('target') or e.get('target')==req.get('artifacts') or e.get('summary'):
                already=True
                break
    if already:
        continue
    # append ACK or REVIEW_OK
    now=datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat()
    out={
        'ts':now,
        'actor':agent,
        'type':'REVIEW_OK' if args.auto_ok else 'ACK',
        'target':req.get('target'),
        'summary':f'{agent} auto-response to REVIEW_REQUEST: {req.get("summary")}',
        'artifacts':req.get('artifacts')
    }
    with open(BUS,'a') as f:
        f.write(json.dumps(out)+"\n")
    print('Appended',out['type'],'from',agent,'for',req.get('summary'))

print('Done')
