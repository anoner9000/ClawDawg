#!/usr/bin/env python3
"""
scan_for_secrets.py - simple workspace secret scanner
Searches ~/.openclaw/workspace for likely secrets (API keys, tokens, private keys) and reports findings.
Writes a short report to ~/.openclaw/workspace/reports/secrets_scan_{ts}.txt
"""
import re,os,sys,json,datetime
root=os.path.expanduser('~/.openclaw/workspace')
out_dir=os.path.expanduser('~/.openclaw/workspace/reports')
os.makedirs(out_dir,exist_ok=True)
now=datetime.datetime.now().strftime('%Y%m%dT%H%M%S')
out_path=os.path.join(out_dir,f'secrets_scan_{now}.txt')
# Patterns to look for
patterns={
    'possible_aws_key':re.compile(r'AKIA[0-9A-Z]{16}'),
    'possible_aws_secret':re.compile(r'(?i)aws(.{0,20})?secret'),
    'possible_openai_key':re.compile(r'sk-[A-Za-z0-9-_]{16,}'),
    'possible_private_key_header':re.compile(r'-----BEGIN (RSA|PRIVATE|OPENSSH) PRIVATE KEY-----'),
    'possible_oauth_token':re.compile(r'ya29\.[0-9A-Za-z\-_]+'),
    'possible_generic_token':re.compile(r'(?:token|secret|password)["\'\s:=]{1,3}[A-Za-z0-9\-\._]{8,}'),
}
ignore_dirs={'node_modules','.git','__pycache__','venv','.venv'}
results=[]
for dirpath,dirnames,filenames in os.walk(root):
    # prune ignore dirs
    dirnames[:] = [d for d in dirnames if d not in ignore_dirs]
    for fn in filenames:
        path=os.path.join(dirpath,fn)
        # skip binaries
        try:
            with open(path,'r',errors='ignore') as f:
                text=f.read()
        except Exception:
            continue
        for name,pat in patterns.items():
            for m in pat.finditer(text):
                # record snippet location
                snippet=text[max(0,m.start()-40):m.end()+40].replace('\n','\\n')
                results.append({'file':path,'pattern':name,'match':m.group(0),'snippet':snippet})

with open(out_path,'w') as out:
    out.write('Secrets scan report\n')
    out.write('Generated: '+datetime.datetime.now().isoformat()+"\n\n")
    if not results:
        out.write('No likely secrets found.\n')
    else:
        out.write(f'Findings: {len(results)}\n\n')
        for r in results:
            out.write('File: '+r['file']+"\n")
            out.write('Pattern: '+r['pattern']+"\n")
            out.write('Match: '+r['match']+"\n")
            out.write('Snippet: '+r['snippet']+"\n")
            out.write('--\n')
print('Scan complete. Report:',out_path)
