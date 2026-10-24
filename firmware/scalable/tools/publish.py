"""Publish a verified prerelease without changing the existing stable release."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'scalable-dist'
TAG='scalable-v0.4.0rc1'

def gh(*args):return subprocess.check_output(['gh',*args],text=True)
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    repo=os.environ['GITHUB_REPOSITORY'];commit=os.environ['GITHUB_SHA']
    report=json.loads((OUT/'BUILD_REPORT.json').read_text())
    if report['source_commit']!=commit or len(report['builds'])!=10 or any(b['result']!='PASS' for b in report['builds']):raise ValueError('Missing current board build qualification')
    expected={p.name:digest(p) for p in OUT.iterdir() if p.is_file()}
    if set(expected)!={'TeleRC-Scalable-LoRa-v0.4.0rc1.zip','BUILD_REPORT.json','README.md','SHA256SUMS.txt'}:raise ValueError('Unexpected candidate assets')
    releases=json.loads(gh('api',f'repos/{repo}/releases?per_page=100'))
    if any(r['tag_name']==TAG for r in releases):raise ValueError('Refusing to replace an existing release')
    gh('release','create',TAG,'--repo',repo,'--target',commit,'--draft','--prerelease','--latest=false',
       '--title','TeleRC Scalable LoRa 0.4.0rc1 — Incremental nodes candidate',
       '--notes-file',str(OUT/'README.md'),*[str(OUT/name) for name in sorted(expected)])
    draft=next(r for r in json.loads(gh('api',f'repos/{repo}/releases?per_page=100')) if r['tag_name']==TAG)
    if not draft['draft'] or draft['target_commitish']!=commit or len(draft['assets'])!=len(expected):raise ValueError('Draft identity mismatch')
    with tempfile.TemporaryDirectory() as temp:
        for asset in draft['assets']:
            if asset['name'] not in expected or asset['state']!='uploaded' or asset.get('digest')!='sha256:'+expected[asset['name']]:raise ValueError('Uploaded asset mismatch')
            path=Path(temp)/asset['name']
            with path.open('wb') as output:subprocess.run(['gh','api',f'repos/{repo}/releases/assets/{asset["id"]}','-H','Accept: application/octet-stream'],stdout=output,check=True)
            if digest(path)!=expected[asset['name']]:raise ValueError('Downloaded asset mismatch')
    gh('api','--method','PATCH',f'repos/{repo}/releases/{draft["id"]}',
       '-F','draft=false','-F','prerelease=true','-f','make_latest=false')
    published=json.loads(gh('api',f'repos/{repo}/releases/{draft["id"]}'))
    print('Published verified candidate:',published['html_url'])

if __name__=='__main__':main()
