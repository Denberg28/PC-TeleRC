"""Incremental enrollment must not change the keys/config of deployed boards."""
import importlib.util
import json
import os
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('scale_project',ROOT/'tools/provision.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)

def test_all_ids_can_be_added_without_changing_base_or_existing_rover(tmp_path):
    project=p.create_project(tmp_path/'NETWORK.private.json')
    base=p.add_device(project,tmp_path/'BASE','BASE')
    rover=p.add_device(project,tmp_path/'ROVER_1','ROVER',1)
    before={base:(base/'Config.h').read_bytes(),rover:(rover/'Config.h').read_bytes()}
    for i in range(1,201):
        node=p.add_device(project,tmp_path/f'NODE_{i}','NODE',i)
        config=(node/'Config.h').read_text()
        assert f'#define NODE_ID {i}\n' in config
        assert 'ROVERS[]={{0,{0}}}' in config
        assert p.key(json.loads(project.read_text()),'rover-1').hex() not in config
    for i in range(2,21):p.add_device(project,tmp_path/f'ROVER_{i}','ROVER',i)
    assert len(json.loads(project.read_text())['issued'])==221
    for folder,data in before.items():assert (folder/'Config.h').read_bytes()==data
    network=json.loads(project.read_text())
    assert p.bytes_cpp(p.key(network,'rover-20')) in (base/'Config.h').read_text()
    assert p.bytes_cpp(p.key(network,'routing')) in (tmp_path/'NODE_200/Config.h').read_text()
    if os.name!='nt':assert project.stat().st_mode&0o077==0

def test_duplicate_id_bounds_and_failed_output_do_not_damage_project(tmp_path):
    project=p.create_project(tmp_path/'network.json')
    p.add_device(project,tmp_path/'NODE3','NODE',3)
    before=project.read_bytes()
    with pytest.raises(ValueError,match='already issued'):p.add_device(project,tmp_path/'DUPLICATE','NODE',3)
    with pytest.raises(ValueError):p.add_device(project,tmp_path/'NODE201','NODE',201)
    with pytest.raises(ValueError):p.add_device(project,tmp_path/'ROVER21','ROVER',21)
    existing=tmp_path/'existing';existing.mkdir()
    with pytest.raises(ValueError,match='overwrite'):p.add_device(project,existing,'NODE',4)
    assert project.read_bytes()==before and not project.with_name(project.name+'.lock').exists()
    with pytest.raises(FileExistsError):p.create_project(project)
    with pytest.raises(ValueError):p.create_project(ROOT/'private.json')

def test_reusing_saved_project_matches_keys_and_separate_network_is_isolated(tmp_path):
    first=p.create_project(tmp_path/'first.json',password='a private passphrase')
    second=p.create_project(tmp_path/'second.json',password='a private passphrase')
    assert p.key(json.loads(first.read_text()),'routing')!=p.key(json.loads(second.read_text()),'routing')
    node=p.add_device(first,tmp_path/'NODE3','NODE',3)
    config=(node/'Config.h').read_text()
    assert p.bytes_cpp(p.key(json.loads(first.read_text()),'routing')) in config
    assert 'master' not in config and 'passphrase' not in config
