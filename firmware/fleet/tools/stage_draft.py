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
# Only this exact previously staged draft may be advanced by this repair.
PREVIOUS_TARGET='118b8552dc82eaef8ce71de10fdb3d515b4d122b'
PREVIOUS_ZIP='8f6253c617f25291eb16ac23d487ffc114ec2f621a2f2f6e3ec56974c0a5d2c8'


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
    notes=Path(__file__).resolve().parents[1]/'RELEASE-NOTES.md'
    if matches:
        release=matches[0]
        if not release['draft']:
            raise ValueError('Refusing to modify a published release')
        if release['target_commitish']!=a.target:
            assets={item['name']:item.get('digest') for item in release.get('assets',[])}
            previous_sums=hashlib.sha256(f'{PREVIOUS_ZIP}  {NAME}.zip\n'.encode()).hexdigest()
            expected_assets={NAME+'.zip':'sha256:'+PREVIOUS_ZIP,NAME+'.sha256':'sha256:'+previous_sums}
            if release['target_commitish']!=PREVIOUS_TARGET or assets!=expected_assets:
                raise ValueError('Refusing to modify a different candidate commit or unrecognized assets')
            gh('release','edit',TAG,'--repo',REPO,'--target',a.target,'--notes-file',str(notes))
    else:
        gh('release','create',TAG,'--repo',REPO,'--draft','--prerelease','--target',a.target,
           '--title','TeleRC LoRa Fleet 1.1.0-dev1 — development candidate','--notes-file',str(notes))
    gh('release','upload',TAG,str(archive),str(sums),'--repo',REPO,'--clobber')
    # Unpublished draft tags may have no Git ref: resolve the authenticated list.
    pages=json.loads(gh('api',f'repos/{REPO}/releases','--paginate','--slurp'))
    found=[item for page in pages for item in page if item['tag_name']==TAG]
    if len(found)!=1:raise ValueError('Draft not uniquely resolved after upload')
    release=found[0]
    if release['target_commitish']!=a.target:raise ValueError('Draft source commit mismatch')
    if not release['draft']:raise ValueError('Candidate must remain draft')
    for file in (archive,sums):
        item=next(v for v in release['assets'] if v['name']==file.name)
        if item['size']!=file.stat().st_size or item.get('digest')!='sha256:'+hashlib.sha256(file.read_bytes()).hexdigest():
            raise ValueError('Uploaded asset digest/size mismatch')
    print('Verified draft candidate assets. Stable releases and Latest are unchanged.')


if __name__=='__main__':
    main()
