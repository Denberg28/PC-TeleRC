"""The isolated native-runtime runner must preserve every result and fail closed."""
import sys
from pathlib import Path
import xml.etree.ElementTree as ET
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import run_regressions as runner


def test_reports_preserve_all_module_results(tmp_path):
    a,b=tmp_path/'a.xml',tmp_path/'b.xml'
    a.write_text('<testsuites><testsuite tests="2" errors="0" failures="0"><testcase name="a"/><testcase name="b"/></testsuite></testsuites>')
    b.write_text('<testsuites><testsuite tests="1" errors="0" failures="0"><testcase name="c"/></testsuite></testsuites>')
    out=tmp_path/'out.xml'
    assert runner.merge_reports([a,b],out)==3
    assert len(list(ET.parse(out).getroot().iter('testcase')))==3


@pytest.mark.parametrize('text',['<testsuites/>','<testsuites><testsuite tests="0"/></testsuites>',
    '<testsuites><testsuite tests="1" failures="1"/></testsuites>',
    '<testsuites><testsuite tests="1" errors="1"/></testsuites>'])
def test_missing_or_failed_module_cannot_be_merged(tmp_path,text):
    path=tmp_path/'bad.xml';path.write_text(text)
    with pytest.raises(ValueError):runner.merge_reports([path],tmp_path/'out.xml')


def test_failed_subprocess_cannot_leave_aggregate_success(tmp_path,monkeypatch):
    import subprocess
    monkeypatch.setattr(runner,'ROOT',tmp_path)
    (tmp_path/'tests').mkdir();(tmp_path/'tests/test_bad.py').write_text('')
    old=tmp_path/'windows-tests.xml';old.write_text('<testsuites/>')
    def fail(*args,**kwargs):raise subprocess.CalledProcessError(1,args[0])
    monkeypatch.setattr(runner.subprocess,'run',fail)
    with pytest.raises(subprocess.CalledProcessError):runner.run()
    assert not old.exists()
