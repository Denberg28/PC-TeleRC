#!/usr/bin/env python3
"""Create a private network once, then add uniquely numbered boards offline."""
import argparse
from contextlib import contextmanager
import getpass
import hashlib
import hmac
import json
import os
import re
from pathlib import Path
import secrets
import shutil

ROOT=Path(__file__).resolve().parents[1]
SCHEMA=1
MAX_ROVERS=20
MAX_NODES=200

def outside(path):
    path=Path(path).expanduser().resolve()
    protected=[ROOT.resolve()]+[p for p in ROOT.parents if (p/'.git').exists()]
    if any(path.is_relative_to(p) for p in protected):
        raise ValueError('Keep private projects and sketches outside the source repository/package')
    return path

def write_private(path,text):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:
        f.write(text);f.flush();os.fsync(f.fileno())

def validate(data):
    if data.get('schema')!=SCHEMA or data.get('protocol')!='TU2':raise ValueError('Incompatible network project')
    if len(bytes.fromhex(data['master']))!=32 or len(bytes.fromhex(data['salt']))!=16:raise ValueError('Invalid project key')
    if not 1<=data['fleet']<=65535 or not 902<=data['frequency']<=928 or not 2<=data['power']<=17:raise ValueError('Invalid radio profile')
    if not 0<=data['servo_mask']<=65535 or data['servo_mask']&0xf0:raise ValueError('Invalid non-motor auxiliary mask')
    issued=data['issued']
    if len(issued)!=len(set(issued)) or any(x not in ['BASE:1']+[f'ROVER:{i}' for i in range(1,21)]+[f'NODE:{i}' for i in range(1,201)] for x in issued):raise ValueError('Invalid or duplicate device inventory')
    return data

def create_project(project,password=None,fleet=271,frequency=915.0,power=2,servo_mask=0):
    project=outside(project)
    if password is not None and len(password)<16:raise ValueError('Use a private passphrase of at least 16 characters')
    salt=secrets.token_bytes(16)
    master=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,600000) if password else secrets.token_bytes(32)
    data=dict(schema=SCHEMA,protocol='TU2',version='0.5.0rc1',master=master.hex(),salt=salt.hex(),fleet=fleet,frequency=frequency,power=power,servo_mask=servo_mask,issued=[])
    validate(data);project.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    write_private(project,json.dumps(data,indent=2)+'\n')
    return project

@contextmanager
def locked(project):
    lock=project.with_name(project.name+'.lock')
    fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
    try:yield
    finally:lock.unlink()

def bytes_cpp(value):return '{'+','.join(f'0x{x:02x}' for x in value)+'}'
def key(data,label):return hmac.digest(bytes.fromhex(data['master']),f'TeleRC-scale-TU2-{data["fleet"]}-{label}'.encode(),'sha256')

def add_device(project,out,role,number=1):
    project=outside(project);out=outside(out);role=role.upper()
    if role not in ('BASE','ROVER','NODE') or not 1<=number<={'BASE':1,'ROVER':MAX_ROVERS,'NODE':MAX_NODES}[role]:raise ValueError('Use BASE 1, ROVER 1..20, NODE 1..200')
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,62}",out.name):raise ValueError("Use an Arduino sketch folder name with letters, digits and underscores, at most 63 characters")
    with locked(project):
        data=validate(json.loads(project.read_text()))
        identity=f'{role}:{number}'
        if identity in data['issued']:raise ValueError('ID already issued; reuse its saved sketch for replacement. Never deploy duplicate IDs')
        if out.exists():raise ValueError('Refusing to overwrite an existing sketch')
        out.parent.mkdir(parents=True,exist_ok=True,mode=0o700);out.mkdir(mode=0o700)
        temp=project.with_name(project.name+'.tmp');own_temp=False
        try:
            for p in (ROOT/'firmware').glob('*.h'):
                if p.name!='Config.example.h':shutil.copyfile(p,out/p.name);(out/p.name).chmod(0o600)
            endpoint_ids=range(1,21) if role=='BASE' else [number] if role=='ROVER' else []
            rows=','.join('{'+str(i)+','+bytes_cpp(key(data,f'rover-{i}'))+'}' for i in endpoint_ids) or '{0,{0}}'
            config=f'''#pragma once
#define ROLE {dict(BASE=1,ROVER=2,NODE=3)[role]}
#define ROVER_ID {number if role=='ROVER' else 1}
#define NODE_ID {number if role=='NODE' else 1}
#define RELAY_COUNT 2
#define FLEET_ID {data['fleet']}
#define FREQUENCY_MHZ {data['frequency']:.3f}f
#define POWER_DBM {data['power']}
#define SERVO_MASK {data['servo_mask']}
#define PROVISIONED 1
struct RoverKey {{ unsigned char id; unsigned char key[32]; }};
static const unsigned char ROUTE_KEY[32]={bytes_cpp(key(data,'routing'))};
static const RoverKey ROVERS[]={{{rows}}};
'''
            write_private(out/'Config.h',config)
            write_private(out/(out.name+'.ino'),'#include <Wire.h>\n#include "Runtime.h"\n')
            write_private(out/'.gitignore','*\n')
            data['issued'].append(identity)
            write_private(temp,json.dumps(data,indent=2)+'\n');own_temp=True;os.replace(temp,project)
        except Exception:
            if own_temp and temp.exists():temp.unlink()
            shutil.rmtree(out)
            raise
    return out

# Host/board qualification helper. Its private project is retained alongside the
# profiles, never copied into public candidate staging.
def provision(out,count=1,relays=2):
    if not 1<=count<=20 or not 0<=relays<=200:raise ValueError('Invalid profile count')
    out=outside(out)
    if out.exists():raise ValueError('Refusing to overwrite private profiles')
    out.mkdir(parents=True,mode=0o700)
    project=create_project(out/'NETWORK.private.json')
    add_device(project,out/'TeleRCFleet_BASE','BASE')
    for i in range(1,count+1):add_device(project,out/f'TeleRCFleet_ROVER_{i:03}','ROVER',i)
    for i in range(1,relays+1):add_device(project,out/f'TeleRCFleet_NODE_{i}','NODE',i)
    return dict(version='0.5.0rc1',rovers=list(range(1,count+1)),nodes=relays)

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    init=sub.add_parser('init');init.add_argument('--project',required=True);init.add_argument('--password',action='store_true')
    init.add_argument('--fleet',type=int,default=271);init.add_argument('--frequency',type=float,default=915.0);init.add_argument('--power',type=int,default=2)
    init.add_argument('--servo-mask',type=lambda x:int(x,0),default=0)
    add=sub.add_parser('add');add.add_argument('--project',required=True);add.add_argument('--role',choices=['BASE','ROVER','NODE'],required=True);add.add_argument('--id',type=int,default=1);add.add_argument('--out',required=True)
    a=p.parse_args()
    try:
        if a.action=='init':
            password=getpass.getpass('Private passphrase (16+ characters): ') if a.password else None
            if a.password and password!=getpass.getpass('Repeat passphrase: '):raise ValueError('Passphrases do not match')
            create_project(a.project,password,a.fleet,a.frequency,a.power,a.servo_mask)
            print('Created private network project. Back up the project and generated sketches; never share them.')
        else:add_device(a.project,a.out,a.role,a.id);print('Created matching private sketch:',a.out)
    except (OSError,ValueError,KeyError,TypeError) as e:p.error(str(e))

if __name__=='__main__':main()
