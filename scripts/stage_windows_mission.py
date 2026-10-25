"""Stage the current map-only fleet application and matching public firmware."""
import argparse,hashlib,json,re,shutil,subprocess,sys,zipfile
from pathlib import Path
from fleet_release_support import FW_NAME,VERSION,FIRMWARE_COMMIT,verify_firmware,verify_report
ROOT=Path(__file__).resolve().parents[1]
def stage(commit):
 if not re.fullmatch('[a-f0-9]{40}',commit):raise ValueError('Exact source commit required')
 desktop=ROOT/'dist/PC-TeleRC';exe=desktop/'PC-TeleRC.exe';report=ROOT/'frozen-ui-check.json'
 verify_report(json.loads(report.read_text()))
 if report.stat().st_mtime_ns<exe.stat().st_mtime_ns:raise ValueError('Stale frozen report')
 subprocess.run([sys.executable,'scripts/verify_fleet_package.py'],cwd=ROOT,check=True)
 archive=ROOT/'fleet-dist'/FW_NAME;digest=verify_firmware(archive,FIRMWARE_COMMIT)
 target=desktop/'Fleet-firmware';target.mkdir(exist_ok=True);shutil.copyfile(archive,target/FW_NAME)
 shutil.copyfile(ROOT/'docs/FLEET-STATION.md',desktop/'START-HERE.md')
 shutil.copyfile(ROOT/'docs/releases/v1.2.0rc2.md',desktop/'RELEASE.md')
 shutil.copyfile(ROOT/'docs/THIRD-PARTY.md',desktop/'THIRD-PARTY.md')
 shutil.copyfile(report,desktop/report.name)
 (desktop/'build-provenance.json').write_text(json.dumps(dict(version=VERSION,source_commit=commit,
  firmware='fleet 0.5.0rc1 + PWM converter 1.0.5',firmware_source_commit=FIRMWARE_COMMIT,firmware_sha256=digest,
  hardware_validation='NOT TESTED',video_runtime=False),indent=2)+'\n')
 out=ROOT/'release-dist';out.mkdir(exist_ok=True)
 path=out/f'PC-TeleRC-portable-v{VERSION}.zip'
 with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
  for p in sorted(desktop.rglob('*')):
   if p.is_symlink():raise ValueError('Symlink in Windows output')
   if p.is_file():z.write(p,p.relative_to(desktop).as_posix())
 print(path)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source-commit',required=True);stage(p.parse_args().source_commit)
