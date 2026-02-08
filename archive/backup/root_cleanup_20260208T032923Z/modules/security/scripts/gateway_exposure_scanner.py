#!/usr/bin/env python3
"""
gateway_exposure_scanner.py
Lightweight exposure scanner for Gateway UI endpoints and WebSocket probes.
Writes JSONL results to an output file in the runtime logs.
"""
import argparse
import json
import socket
import urllib.request
import os
import datetime

HOME = os.path.expanduser('~')
RUNTIME = os.path.join(HOME, '.openclaw', 'runtime')
LOG_DIR = os.path.join(RUNTIME, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

COMMON_PATHS = ['/', '/gateway/ui', '/ui', '/admin', '/gateway', '/control']
WS_PORTS = [80, 443]  # default WS probe ports; can be extended later

def probe_http(host, port, path, timeout=6):
    url = f'http://{host}:{port}{path}'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            status = r.getcode()
            headers = dict(r.getheaders())
            body = r.read(1024 * 8)
            snippet = body.decode('utf-8', errors='replace')[:1024]
            return {'status': status, 'headers': headers, 'snippet': snippet}
    except urllib.error.HTTPError as e:
        return {'status': e.code, 'headers': {}, 'snippet': ''}
    except urllib.error.URLError as e:
        return {'status': 0, 'headers': {}, 'snippet': ''}
    except Exception:
        return {'status': 0, 'headers': {}, 'snippet': ''}

def probe_tcp(host, port, timeout=4):
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return True
    except Exception:
        return False

def main():
    p = argparse.ArgumentParser(description="Gateway Exposure Scanner")
    p.add_argument('--targets', required=True, help='Path to targets.txt')
    p.add_argument('--output', default=os.path.join(LOG_DIR, f'exposure_scan_{datetime.datetime.now(datetime.UTC).isoformat()}.jsonl'))
    p.add_argument('--port', type=int, default=80, help='Port to probe (default: 80)')
    args = p.parse_args()

    output_file = args.output
    print(f"Output: {output_file}")

    with open(args.targets) as f:
        targets = [line.strip() for line in f if line.strip()]

    for host in targets:
        rec = {
            'target': host,
            'port': args.port,
            'checked': datetime.datetime.now(datetime.UTC).isoformat(),
            'results': []
        }

        # HTTP probes
        for path in COMMON_PATHS:
            result = probe_http(host, args.port, path)
            rec['results'].append({
                'path': path,
                'http_status': result['status'],
                'headers': {k: v for k, v in result['headers'].items() if k.lower() in ['server', 'content-type', 'x-frame-options', 'content-security-policy']},
                'snippet': result['snippet'][:200]  # truncate for brevity
            })

        # Simple WS/TCP probe (only on same port for now)
        ws_result = probe_tcp(host, args.port)
        rec['ws_probe'] = {'tcp_connect': ws_result}

        # Risk score (simple example)
        risk = 0
        for r in rec['results']:
            if r['http_status'] == 200:
                risk += 4  # open UI path
            if 'sourceMappingURL' in r['snippet']:
                risk += 3  # source map leak
        rec['risk_score'] = min(risk, 10)

        # Write result
        with open(output_file, 'a') as out:
            out.write(json.dumps(rec) + '\n')

    print(f"Scan complete. Results in: {output_file}")

if __name__ == '__main__':
    main()
