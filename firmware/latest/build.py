#!/usr/bin/env python3
"""Compile/package the private current baseline collection. Never flashes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

HERE=Path(__file__).resolve().parent
CATALOG=json.loads((HERE/'catalog.json').read_text())
OFFSETS={'bootloader':'0x0','partitions':'0x8000','boot_app0':'0xe000','application':'0x10000'}

def run(*args,cwd=None):
    return subprocess.check_output(list(map(str,args)),cwd=cwd,text=True).strip()

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def gh(path):return json.loads(run('gh','api',path))

def validate_catalog(catalog=CATALOG):
    profiles=catalog['profiles'];ids=[x['id'] for x in profiles]
    assert len(ids)==len(set(ids)) and profiles,'Duplicate/empty profiles'
    for p in profiles:
        assert re.fullmatch('[a-z0-9-]+',p['id'])
        assert p['source'] in catalog['sources']
        assert not Path(p['path']).is_absolute() and '..' not in Path(p['path']).parts
        assert all(not Path(g).is_absolute() and '..' not in Path(g).parts for g in p.get('guide_roots',[])+p.get('guide_files',[]))
        assert p['fqbn'].startswith('esp32:esp32:')
        assert not re.search('PASSWORD|KEY|DIRECTIONS_VERIFIED',p['flags'])
        assert set(p['defines']) <= {'TELERC_RELAY_COUNT','TELERC_NODE_INDEX','TELERC_TRANSPORT_WIFI'}
    return profiles

def checkout(source,commit,destination):
    if destination.exists():raise RuntimeError(f'Stale source directory: {destination}')
    repo=source['repository']
    if repo==os.environ['GITHUB_REPOSITORY']:
        # Checkout already owns a private scoped credential. Avoid exporting it.
        run('git','fetch','--no-tags','--depth=1','origin',commit)
        run('git','worktree','add','--detach',destination.resolve(),commit)
    else:
        assert repo=='Denberg28/TeleRC','Only approved public upstream is supported'
        run('git','clone','--filter=blob:none','--no-checkout',f'https://github.com/{repo}.git',destination)
        run('git','checkout','--detach',commit,cwd=destination)
    assert run('git','rev-parse','HEAD',cwd=destination)==commit

def resolve(args):
    validate_catalog();assert os.environ['GITHUB_REPOSITORY']=='Denberg28/PC-TeleRC'
    sources={}
    for name,source in CATALOG['sources'].items():
        ref=source['ref'];repo=source['repository']
        if ref in {'latest-android-release','latest-stable-pc-release'}:
            releases=gh(f'repos/{repo}/releases?per_page=100')
            releases=[x for x in releases if not x['draft'] and re.fullmatch(r'v\d+\.\d+\.\d+',x['tag_name'])]
            if ref=='latest-stable-pc-release':releases=[x for x in releases if not x['prerelease']]
            if not releases:raise RuntimeError('No published Android release; refusing stale fallback')
            ref=max(releases,key=lambda x:tuple(map(int,x['tag_name'][1:].split('.'))))['tag_name']
        commit=gh(f'repos/{repo}/commits/{ref}')['sha']
        sources[name]={**source,'resolved_ref':ref,'commit':commit}
    # Provenance, catalog and tooling all invalidate the previous collection.
    identity={'sources':sources,'catalog':sha(HERE/'catalog.json'),'builder':sha(Path(__file__)),'guide':sha(HERE/'README.md'),'workflow':sha(HERE.parents[1]/'.github/workflows/firmware-master.yml'),'tests':sha(HERE/'test_catalog.py')}
    fingerprint=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
    state={'schema':1,'fingerprint':fingerprint,'sources':sources,'catalog_commit':os.environ['GITHUB_SHA'],
           'run_url':f'https://github.com/{os.environ["GITHUB_REPOSITORY"]}/actions/runs/{os.environ["GITHUB_RUN_ID"]}',
           'esp32_core':CATALOG['esp32_core'],'radiolib':CATALOG['radiolib'],'hardware':'NOT TESTED'}
    args.state.write_text(json.dumps(state,indent=2)+'\n')
    changed=True
    old=Path(os.environ.get('RUNNER_TEMP','/tmp'))/'previous-firmware-latest.json'
    result=subprocess.run(['gh','release','download','firmware-collection','--repo',os.environ['GITHUB_REPOSITORY'],
        '--pattern','LATEST.json','--output',str(old),'--clobber'],capture_output=True,text=True)
    if result.returncode==0:
        changed=json.loads(old.read_text()).get('fingerprint')!=fingerprint
    elif 'release not found' not in result.stderr.lower() and 'not found' not in result.stderr.lower():
        raise RuntimeError('Cannot inspect previous firmware collection; refusing uncertain update')
    if os.environ.get('GITHUB_EVENT_NAME')=='workflow_dispatch':changed=True
    with open(os.environ['GITHUB_OUTPUT'],'a') as f:
        f.write(f'changed={str(changed).lower()}\nfingerprint={fingerprint}\n')
    print('Resolved sources:',{k:v['commit'] for k,v in sources.items()},'changed=',changed)

def prepare_sources(state,root):
    root.mkdir(parents=True,exist_ok=True)
    for name,source in state['sources'].items():
        checkout(source,source['commit'],root/name)
    # Fail closed when a newly added runtime sketch is omitted from this catalog.
    for name,prefix in [('android','bridge'),('pc-stable','firmware')]:
        found={p.parent.relative_to(root/name).as_posix() for p in (root/name/prefix).rglob('*.ino') if p.stem==p.parent.name}
        listed={p['path'] for p in CATALOG['profiles'] if p['source']==name}
        excluded=set(CATALOG.get('excluded_sketches',{}).get(name,{}))
        if found-listed-excluded:raise RuntimeError(f'Uncatalogued {name} sketches: {sorted(found-listed-excluded)}')

def stage(profile,sources,target):
    src=sources/profile['source']/profile['path'];sketch=target/'sketch'/src.name
    if not (src/(src.name+'.ino')).is_file():raise RuntimeError(f'Missing sketch {src}')
    shutil.copytree(src,sketch,ignore=shutil.ignore_patterns('build','__pycache__','*.bin','*.elf','*.map'))
    entry=sketch/(src.name+'.ino')
    text=entry.read_text()
    for name,value in profile['defines'].items():
        text,count=re.subn(r'(?m)^#define\s+'+name+r'\s+[^\n]+',f'#define {name} {value} // catalog variant',text)
        if count!=1:raise RuntimeError(f'Cannot safely set profile {name}')
    entry.write_text(text)
    # Ship required local library and role-specific explanatory guides.
    library=sources/profile['source']/'bridge/libraries'
    if library.is_dir():shutil.copytree(library,target/'libraries')
    for p in src.glob('*.md'):shutil.copyfile(p,target/p.name)
    guide_roots=[sources/profile['source']/p for p in profile.get('guide_roots',[])]
    for index,guide_root in enumerate(guide_roots):
        guide_target=target/'guides'/str(index);guide_target.mkdir(parents=True)
        for p in guide_root.iterdir():
            if p.is_file() and p.suffix.lower() in {'.md','.png','.svg'}:
                shutil.copyfile(p,guide_target/p.name)
    for relative in profile.get('guide_files',[]):
        guide=sources/profile['source']/relative
        destination=target/'guides'/relative;destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(guide,destination)
    (target/'PROFILE.md').write_text(f'# {profile["id"]}\n\n{profile["note"]}\n\nFQBN: `{profile["fqbn"]}`\nFlags: `{profile["flags"]}`\nSource: `{profile["source"]}/{profile["path"]}`\n\nRead the bundle README before choosing/flashing. Build verified only; physical acceptance pending.\n')
    return sketch

def compile_group(args):
    state=json.loads(args.state.read_text());sources=args.sources
    prepare_sources(state,sources)
    if args.output.exists():raise RuntimeError('Use a fresh group output directory')
    args.output.mkdir(parents=True)
    core=Path.home()/f'.arduino15/packages/esp32/hardware/esp32/{CATALOG["esp32_core"]}'
    for p in [x for x in validate_catalog() if x['group']==args.group]:
        target=args.output/p['id'];target.mkdir();sketch=stage(p,sources,target)
        work=Path(os.environ['RUNNER_TEMP'])/'compiled'/p['id'];work.mkdir(parents=True)
        cmd=['arduino-cli','compile','--jobs','2','--fqbn',p['fqbn'],'--libraries',str(sources/'android/bridge/libraries'),'--output-dir',str(work)]
        if p['flags']:cmd+=['--build-property','compiler.cpp.extra_flags='+p['flags']]
        cmd.append(str(sketch.resolve()))
        print('Compiling',p['id'],flush=True)
        with (target/'compile.log').open('w') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
        name=sketch.name;files={'bootloader':f'{name}.ino.bootloader.bin','partitions':f'{name}.ino.partitions.bin','application':f'{name}.ino.bin','boot_app0':'boot_app0.bin'}
        images=[]
        for kind,filename in files.items():
            source=core/'tools/partitions/boot_app0.bin' if kind=='boot_app0' else work/filename
            assert source.is_file() and source.stat().st_size>0,f'Missing {p["id"]} {kind}'
            dest=target/filename;shutil.copyfile(source,dest)
            images.append({'kind':kind,'file':filename,'offset':OFFSETS[kind],'bytes':dest.stat().st_size,'sha256':sha(dest)})
        record={**p,'provenance':state,'images':images,'status':'BUILD VERIFIED; HIL NOT TESTED'}
        (target/'BUILD.json').write_text(json.dumps(record,indent=2)+'\n')
        (target/'FLASH.json').write_text(json.dumps({'fqbn':p['fqbn'],'erase_all':False,'preserve_nvs_if_layout_compatible':True,'images':images},indent=2)+'\n')
        shutil.rmtree(work)

def verify_package(root,catalog=CATALOG):
    expected={x['id'] for x in catalog['profiles']}
    present={p.parent.name for p in root.glob('*/BUILD.json')}
    if present!=expected:raise RuntimeError(f'Incomplete collection: missing={expected-present}, unexpected={present-expected}')
    records=[];fingerprint=None
    for id in sorted(expected):
        directory=root/id;r=json.loads((directory/'BUILD.json').read_text())
        profile=next(p for p in catalog['profiles'] if p['id']==id)
        assert all(r.get(k)==v for k,v in profile.items()),'Mismatched profile metadata'
        if fingerprint is None:fingerprint=r['provenance']['fingerprint']
        assert r['provenance']['fingerprint']==fingerprint,'Mixed build generations'
        assert len(r['images'])==len(OFFSETS) and {x['kind'] for x in r['images']}==set(OFFSETS)
        for image in r['images']:
            assert Path(image['file']).name==image['file'],'Unsafe image path'
            assert image['offset']==OFFSETS[image['kind']]
            path=directory/image['file'];assert path.is_file() and sha(path)==image['sha256'] and path.stat().st_size==image['bytes'],'Image mismatch'
        records.append(r)
    assert not list(root.rglob('*.merged.bin')),'Whole-flash images are forbidden'
    return records

def package(args):
    state=json.loads(args.state.read_text());records=verify_package(args.output)
    assert all(r['provenance']==state for r in records)
    shutil.copyfile(HERE/'README.md',args.output/'README.md');shutil.copyfile(HERE/'catalog.json',args.output/'CATALOG.json')
    (args.output/'MANIFEST.json').write_text(json.dumps({**state,'profiles':records},indent=2)+'\n')
    sums=args.output/'SHA256SUMS.txt'
    sums.write_text(''.join(f'{sha(p)}  {p.relative_to(args.output).as_posix()}\n' for p in sorted(args.output.rglob('*')) if p.is_file() and p!=sums))
    args.archive.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(args.archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(args.output.rglob('*')):
            if p.is_file():z.write(p,Path('TeleRC-Firmware')/p.relative_to(args.output))
    with zipfile.ZipFile(args.archive) as z:
        assert z.testzip() is None
        for line in sums.read_text().splitlines():
            digest,name=line.split('  ',1);assert hashlib.sha256(z.read('TeleRC-Firmware/'+name)).hexdigest()==digest
    latest={**state,'file':args.archive.name,'sha256':sha(args.archive),'profiles':len(records),'catalog_status':'BUILD VERIFIED; PHYSICAL HIL NOT TESTED'}
    (args.archive.parent/'LATEST.json').write_text(json.dumps(latest,indent=2)+'\n')
    print(json.dumps(latest,indent=2))

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['resolve','compile','package']);p.add_argument('--state',type=Path,default=Path('source-state.json'));p.add_argument('--sources',type=Path,default=Path('sources'));p.add_argument('--group');p.add_argument('--output',type=Path,default=Path('firmware-bundle'));p.add_argument('--archive',type=Path,default=Path('deliverables/TeleRC-Firmware.zip'));a=p.parse_args()
    {'resolve':resolve,'compile':compile_group,'package':package}[a.command](a)
if __name__=='__main__':main()
