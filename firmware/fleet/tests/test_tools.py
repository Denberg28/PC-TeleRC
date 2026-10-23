import importlib.util
from pathlib import Path
import random
import sys
import tempfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from network import init, sketch
import json
from fleet_gateway import encode, Decoder, split_mav
from mission_client import read_plan, compare, fingerprint

def test_usb_chunking_noise_crc_and_bounded_input():
    payload = bytes(range(100))
    packet = encode(20, 1, payload)
    d = Decoder()
    results = []
    for byte in b'noise'+packet:
        results.extend(d.feed(bytes([byte])))
    assert results == [(20, 1, payload)]
    for index in range(len(packet)):
        corrupt = bytearray(packet)
        corrupt[index] ^= 128
        assert not Decoder().feed(corrupt)
    d.feed(b'\xff'*100000)
    assert len(d.buf) <= 1

def test_mav_datagram_splitting():
    from pymavlink.dialects.v20 import common as m
    raw = bytes(m.MAVLink_heartbeat_message(6, 8, 0, 0, 4, 3).pack(m.MAVLink(None)))
    assert split_mav(raw+raw) == [raw, raw]
    with pytest.raises(ValueError):
        split_mav(raw[:-1])

def plan(tmp_path, command=16):
    p = tmp_path/'mission.waypoints'
    p.write_text(f'QGC WPL 110\n0\t1\t3\t16\t0\t0\t0\t0\t13.6\t123.2\t0\t1\n1\t0\t3\t{command}\t0\t0\t0\t0\t13.6001\t123.2\t0\t1\n')
    return p

def test_plan_and_readback_fail_closed(tmp_path):
    items = read_plan(plan(tmp_path))
    compare(items, items)
    assert fingerprint(items, 1) != fingerprint(items, 2)
    import copy
    changed = copy.deepcopy(items)
    changed[1]['x'] += 1
    with pytest.raises(RuntimeError):
        compare(items, changed)
    changed = copy.deepcopy(items)
    changed[1]['params'][0] = float('nan')
    with pytest.raises(RuntimeError):
        compare(items, changed)
    with pytest.raises(ValueError):
        read_plan(plan(tmp_path, command=400))

def test_separate_start_never_uploads_or_arms(tmp_path, monkeypatch):
    import mission_client as mod
    path = plan(tmp_path)
    items = mod.read_plan(path)
    phrase = f'START 1 {mod.fingerprint(items, 1)[:12]}'
    calls = []
    class Fake:
        start_attempted = False
        def __init__(self, endpoint, rover):
            self.link = self
        def heartbeat(self, **kwargs):
            calls.append('heartbeat')
        def loss_policy(self, value, **kwargs):
            calls.append('policy')
        def download(self):
            calls.append('readback')
            return items
        def start_once(self):
            calls.append('start')
            self.start_attempted = True
        def recv(self, *args):
            raise KeyboardInterrupt
        def hold(self):
            calls.append('hold')
        def close(self):
            calls.append('close')
    monkeypatch.setattr(mod, 'Client', Fake)
    monkeypatch.setattr('builtins.input', lambda text: phrase)
    monkeypatch.setattr(sys, 'argv', ['mission_client.py', '--rover', '1', 'start', str(path)])
    mod.main()
    assert calls == ['heartbeat', 'policy', 'readback', 'readback', 'policy', 'start', 'hold', 'close']


def test_add_only_changes_id_and_node_cannot_decrypt(tmp_path):
    secret=init(tmp_path/'private')
    network=json.loads(secret.read_text())
    before=(tmp_path/'private/TeleRCFleet_BASE/NetworkConfig.h').read_bytes()
    a=sketch(tmp_path/'rover1','rover',1,network)
    b=sketch(tmp_path/'rover20','rover',20,network)
    node=sketch(tmp_path/'node200','node',200,network)
    assert (a/'NetworkConfig.h').read_bytes()==(b/'NetworkConfig.h').read_bytes()==before
    assert 'ENDPOINT_ROOT' not in (node/'NetworkConfig.h').read_text()
    assert network['endpoint_root'] not in (node/'NetworkConfig.h').read_text()
    assert '#define ROVER_ID 20' in (b/'rover20.ino').read_text()
    assert '#define NODE_ID 200' in (node/'node200.ino').read_text()
    assert (tmp_path/'private/TeleRCFleet_BASE/NetworkConfig.h').read_bytes()==before
    other=init(tmp_path/'other')
    assert json.loads(other.read_text())['route_key']!=network['route_key']
    with pytest.raises(FileExistsError):
        init(tmp_path/'private')
    for role,identity in [('rover',0),('rover',21),('node',0),('node',201)]:
        with pytest.raises(ValueError):
            sketch(tmp_path/'invalid',role,identity,network)


def test_watch_ranges_are_bounded_and_deduplicated():
    from fleet_gateway import parse_watch
    assert parse_watch('1,3-5,3')==[1,3,4,5]
    for text in ('','0','21','5-1','1-2-3','a'):
        with pytest.raises(ValueError):
            parse_watch(text)


def test_detach_requires_explicit_continuation_before_connect(monkeypatch):
    import mission_client as mod
    called=[]
    monkeypatch.setattr(mod,'Client',lambda *a:called.append(a))
    for tail in (['start','missing','--detach'],['upload','missing','--continue-on-loss','--detach']):
        monkeypatch.setattr(sys,'argv',['mission_client.py','--rover','1']+tail)
        with pytest.raises(SystemExit) as e:
            mod.main()
        assert e.value.code==2
    assert not called


def test_detach_follows_verified_start_and_never_requests_hold(tmp_path,monkeypatch):
    import mission_client as mod
    path=plan(tmp_path);items=mod.read_plan(path);calls=[]
    class Fake:
        start_attempted=False
        def __init__(self,*a):self.link=self
        def heartbeat(self,**kwargs):calls.append('heartbeat')
        def loss_policy(self,value,**kwargs):
            assert value and kwargs['min_timeout']==10
            calls.append('policy')
        def download(self):calls.append('readback');return items
        def start_once(self):calls.append('start');self.start_attempted=True
        def hold(self):raise AssertionError('Detach must be deliberate AUTO continuation')
        def recv(self,*a):raise AssertionError('Detach must close the writer')
        def close(self):calls.append('close')
    monkeypatch.setattr(mod,'Client',Fake)
    phrase=f'START 1 {mod.fingerprint(items,1)[:12]}'
    monkeypatch.setattr('builtins.input',lambda _:phrase)
    monkeypatch.setattr(sys,'argv',['mission_client.py','--rover','1','start',str(path),'--continue-on-loss','--detach'])
    mod.main()
    assert calls==['heartbeat','policy','readback','readback','policy','start','close']


def test_public_package_has_exact_headers_and_no_private_credentials(tmp_path):
    import importlib.util,zipfile,hashlib,json
    spec=importlib.util.spec_from_file_location('fleet_package',ROOT/'tools/package.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    archive=mod.package(tmp_path/'dist')
    with zipfile.ZipFile(archive) as z:
        assert not any(n.endswith(('.bin','.elf','FleetCredentials.json')) for n in z.namelist())
        prefix=mod.NAME+'/'
        manifest=json.loads(z.read(prefix+'MANIFEST.sha256.json'))['files']
        for name,digest in manifest.items():
            assert hashlib.sha256(z.read(prefix+name)).hexdigest()==digest
        assert len([n for n in manifest if n.endswith('NetworkConfig.h')])==4
    first=archive.read_bytes();mod.package(tmp_path/'again');assert first==(tmp_path/'again'/archive.name).read_bytes()


def test_draft_staging_refuses_published_or_different_commit(tmp_path,monkeypatch):
    import stage_draft as mod,hashlib,json
    archive=tmp_path/(mod.NAME+'.zip');archive.write_bytes(b'public test archive')
    (tmp_path/(mod.NAME+'.sha256')).write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  '+archive.name+'\n')
    for release in ({'draft':False,'target_commitish':'a'*40},{'draft':True,'target_commitish':'b'*40}):
        calls=[]
        release.update(tag_name=mod.TAG)
        def fake(*args):
            calls.append(args)
            assert args[0]=='api' and '--slurp' in args
            return json.dumps([[release]])
        monkeypatch.setattr(mod,'gh',fake)
        monkeypatch.setattr(sys,'argv',['stage_draft.py','--dist',str(tmp_path),'--target','a'*40])
        with pytest.raises(ValueError,match='Refusing'):
            mod.main()
        assert len(calls)==1


def test_draft_staging_validates_exact_archive_before_network(tmp_path,monkeypatch):
    import stage_draft as mod
    (tmp_path/(mod.NAME+'.zip')).write_bytes(b'changed')
    (tmp_path/(mod.NAME+'.sha256')).write_text('wrong hash\n')
    monkeypatch.setattr(mod,'gh',lambda *a:pytest.fail('No GitHub call before checksum verification'))
    monkeypatch.setattr(sys,'argv',['stage_draft.py','--dist',str(tmp_path),'--target','a'*40])
    with pytest.raises(ValueError,match='checksum'):
        mod.main()


@pytest.mark.parametrize('changes',[{}, {'SERVO9_FUNCTION':70}, {'SERVO9_MIN':1600}, {'SERVO9_MAX':float('nan')}, {'SERVO9_MAX':2100}])
def test_auxiliary_output_checks_are_read_only_and_fail_closed(changes):
    from mission_client import verify_outputs
    parameters={'SERVO9_FUNCTION':0,'SERVO9_MIN':1000,'SERVO9_MAX':2000,**changes}
    calls=[]
    class Fake:
        def parameter(self,key):calls.append(key);return parameters[key]
        def log(self,text):pass
    items=[{'command':183,'params':[9,1500,0,0]}]
    if changes:
        with pytest.raises(RuntimeError):verify_outputs(Fake(),items)
    else:
        verify_outputs(Fake(),items)
    assert calls==['SERVO9_FUNCTION','SERVO9_MIN','SERVO9_MAX']


def test_auxiliary_output_policy_rejects_motor_channels():
    from mission_client import verify_outputs
    with pytest.raises(RuntimeError):
        verify_outputs(object(),[{'command':183,'params':[5,1500,0,0]}])


def test_draft_lookup_uses_authenticated_list_and_advances_only_exact_owned_candidate(tmp_path,monkeypatch):
    import stage_draft as mod,hashlib,json
    archive=tmp_path/(mod.NAME+'.zip');archive.write_bytes(b'reviewed revised public archive')
    sums=tmp_path/(mod.NAME+'.sha256');sums.write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  '+archive.name+'\n')
    old_sums=f'{mod.PREVIOUS_ZIP}  {mod.NAME}.zip\n'.encode()
    old={'tag_name':mod.TAG,'draft':True,'target_commitish':mod.PREVIOUS_TARGET,
         'assets':[{'name':archive.name,'digest':'sha256:'+mod.PREVIOUS_ZIP},
                   {'name':sums.name,'digest':'sha256:'+hashlib.sha256(old_sums).hexdigest()}]}
    fresh={'tag_name':mod.TAG,'draft':True,'target_commitish':'a'*40,
           'assets':[{'name':f.name,'size':f.stat().st_size,'digest':'sha256:'+hashlib.sha256(f.read_bytes()).hexdigest()} for f in (archive,sums)]}
    calls=[]
    def fake(*args):
        calls.append(args)
        assert not any('/releases/tags/' in arg for arg in args)
        if args[0]=='api':return json.dumps([[old if len(calls)==1 else fresh]])
        return ''
    monkeypatch.setattr(mod,'gh',fake)
    monkeypatch.setattr(sys,'argv',['stage_draft.py','--dist',str(tmp_path),'--target','a'*40])
    mod.main()
    assert [call[:2] for call in calls]==[('api','repos/Denberg28/PC-TeleRC/releases'),('release','edit'),('release','upload'),('api','repos/Denberg28/PC-TeleRC/releases')]
