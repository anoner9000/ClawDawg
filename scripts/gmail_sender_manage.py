#!/usr/bin/env python3
import os, json, argparse, datetime
HOME=os.path.expanduser('~')
CFG=os.path.join(HOME,'.openclaw','runtime','config','cleanup_senders.json')
LOG=os.path.join(HOME,'.openclaw','runtime','logs','gmail_sender_changes.log')
os.makedirs(os.path.dirname(CFG),exist_ok=True)
os.makedirs(os.path.dirname(LOG),exist_ok=True)

p=argparse.ArgumentParser()
p.add_argument('--add',help='email to add')
p.add_argument('--remove',help='email to remove')
p.add_argument('--operator',required=True)
args=p.parse_args()

if not os.path.exists(CFG):
    with open(CFG,'w') as f: json.dump({'senders':[]},f)

with open(CFG) as f: data=json.load(f)
senders=set(data.get('senders',[]))
now=datetime.datetime.utcnow().isoformat()
if args.add:
    senders.add(args.add)
    action='add'
elif args.remove:
    senders.discard(args.remove)
    action='remove'
else:
    print('nothing to do'); raise SystemExit(0)

with open(CFG,'w') as f:
    json.dump({'senders':sorted(list(senders))},f)

with open(LOG,'a') as f:
    f.write(json.dumps({'operator':args.operator,'action':action,'target':args.add or args.remove,'time':now})+"\n")

print('ok')
