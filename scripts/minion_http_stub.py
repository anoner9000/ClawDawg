#!/usr/bin/env python3
"""
minion_http_stub.py - Dry-run HTTP intake stub for Minion.

Behavior: when run, starts a local HTTP server that accepts POST /task and appends a dry-run event
to the team_bus.jsonl. The server binds to localhost only and logs to stdout. Run manually when needed.
"""
import http.server
import json
import datetime
import os

BUS=os.path.expanduser('~/.openclaw/runtime/logs/team_bus.jsonl')

class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != '/task':
            self.send_response(404)
            self.end_headers()
            return
        length=int(self.headers.get('Content-Length',0))
        body=self.rfile.read(length).decode('utf-8') if length else '{}'
        try:
            payload=json.loads(body)
        except Exception:
            payload={'raw':body}
        event={
            'ts':datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(),
            'actor':'minion',
            'action':'receive',
            'task_id':payload.get('task_id','task-'+datetime.datetime.now().strftime('%s')),
            'owner':payload.get('owner','unassigned'),
            'summary':payload.get('summary','no-summary'),
            'dry_run':True,
            'details':payload.get('details',None)
        }
        os.makedirs(os.path.dirname(BUS),exist_ok=True)
        with open(BUS,'a') as f:
            f.write(json.dumps(event)+"\n")
        self.send_response(200)
        self.send_header('Content-Type','application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'status':'ok','task_id':event['task_id']}).encode('utf-8'))

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--bind','default','local host binding')
    parser.add_argument('--port',type=int,default=8080)
    args=parser.parse_args()
    server=http.server.HTTPServer(('127.0.0.1',args.port),Handler)
    print('Minion HTTP stub listening on 127.0.0.1:%d (dry-run only). Ctrl-C to exit.'%args.port)
    server.serve_forever()
