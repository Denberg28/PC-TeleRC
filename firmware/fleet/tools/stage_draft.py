#!/usr/bin/env python3
"""CI-only: stage this exact public source package in a separate draft release."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
REPO='Denberg28/PC-TeleRC'
TAG='fleet-v1.1.0-dev1'
NAME='TeleRC-LoRa-Fleet-v1.1.0-dev1'


def gh(*args):
    return subprocess.run(['gh',*args],check=True,capture_output=True,text=True).stdout


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--dist',type=Path,required=True);p.add_argument('--target',required=True);a=p.parse_args()
    if len(a.target)!=40 or any(c not in '0123456789abcdef' for c in a.target):
        raise ValueError('Expected exact source commit SHA')
    archive=a.dist/(NAME+'.zip');sums=a.dist/(NAME+'.sha256')
    expected=sums.read_text().split()
    if expected!=[hashlib.sha256(archive.read_bytes()).hexdigest(),archive.name]:
        raise ValueError('Candidate archive checksum mismatch')
    # List first: a network/auth failure must not be mistaken for a missing draft.
    releases=json.loads(gh('api',f'repos/{REPO}/releases','--paginate','--slurp'))
    matches=[r for page in releases for r in page if r['tag_name']==TAG]
    if len(matches)>1:raise ValueError('Ambiguous release tag')
    if matches:
        release=matches[0]
        if not release['draft'] or release['target_commitish']!=a.target:
            raise ValueError('Refusing to modify a published release or a different candidate commit')
    else:
        notes=Path(__file__).resolve().parents[1]/'RELEASE-NOTES.md'
        gh('release','create',TAG,'--repo',REPO,'--draft','--prerelease','--target',a.target,
           '--title','TeleRC LoRa Fleet 1.1.0-dev1 — development candidate','--notes-file',str(notes))
    gh('release','upload',TAG,str(archive),str(sums),'--repo',REPO,'--clobber')
    release=json.loads(gh('api',f'repos/{REPO}/releases/tags/{TAG}'))
    if not release['draft']:raise ValueError('Candidate must remain draft')
    for file in (archive,sums):
        item=next(v for v in release['assets'] if v['name']==file.name)
        if item['size']!=file.stat().st_size or item.get('digest')!='sha256:'+hashlib.sha256(file.read_bytes()).hexdigest():
            raise ValueError('Uploaded asset digest/size mismatch')
    print('Verified draft candidate assets. Stable releases and Latest are unchanged.')


if __name__=='__main__':
    main()
