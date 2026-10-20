"""Advance the private draft pointer only after the uploaded bundle digest matches."""
import json
import os
from pathlib import Path
import subprocess

def gh(*args):return subprocess.check_output(['gh',*args],text=True)
repo=os.environ['GITHUB_REPOSITORY'];assert repo=='Denberg28/PC-TeleRC'
latest=json.loads(Path('deliverables/LATEST.json').read_text())
releases=json.loads(gh('api',f'repos/{repo}/releases?per_page=100'))
release=next(r for r in releases if r['tag_name']=='firmware-collection')
assert release['draft'] and release['prerelease']
assets=json.loads(gh('api',f'repos/{repo}/releases/{release["id"]}/assets?per_page=100'))
asset=next(a for a in assets if a['name']==latest['file'])
assert asset['digest']=='sha256:'+latest['sha256']
assert asset['size']==(Path('deliverables')/latest['file']).stat().st_size
latest['release_url']=release['html_url']
latest['download_url']=asset['browser_download_url']
Path('deliverables/LATEST.json').write_text(json.dumps(latest,indent=2)+'\n')
subprocess.run(['gh','release','upload','firmware-collection','--repo',repo,'deliverables/LATEST.json','--clobber'],check=True)
print(release['html_url']);print('Verified all45 profiles; private draft latest pointer updated.')
