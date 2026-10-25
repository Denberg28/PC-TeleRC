"""Run every regression module in a fresh native-runtime process; never retry failures."""
import argparse
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def merge_reports(paths, destination):
    combined = ET.Element('testsuites')
    for path in paths:
        root = ET.parse(path).getroot()
        suites = [root] if root.tag == 'testsuite' else list(root.findall('testsuite'))
        if not suites or sum(int(s.get('tests', 0)) for s in suites) < 1:
            raise ValueError(f'Missing regression results: {path}')
        if any(int(s.get(k, 0)) for s in suites for k in ('failures', 'errors')):
            raise ValueError(f'Failed regression results: {path}')
        for suite in suites:combined.append(suite)
    if not len(combined):raise ValueError('No regression modules ran')
    ET.ElementTree(combined).write(destination, encoding='utf-8', xml_declaration=True)
    return sum(int(s.get('tests', 0)) for s in combined)


def run(report='windows-tests.xml'):
    destination = ROOT/report
    destination.unlink(missing_ok=True)
    parts = ROOT/'regression-parts'
    parts.mkdir(exist_ok=True)
    modules = sorted((ROOT/'tests').glob('test_*.py'))
    reports = []
    for module in modules:
        path = parts/(module.stem+'.xml')
        path.unlink(missing_ok=True)
        print(f'Running {module.name} in a fresh process', flush=True)
        subprocess.run([sys.executable, '-m', 'pytest', '-q', str(module),
            '--junitxml='+str(path)], cwd=ROOT, check=True)
        # Fail immediately on missing/malformed/failed evidence, too.
        merge_reports([path], parts/'last-module.xml')
        reports.append(path)
    count = merge_reports(reports, destination)
    print(f'All {len(modules)} modules passed; {count} regression results', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', default='windows-tests.xml')
    run(parser.parse_args().report)
