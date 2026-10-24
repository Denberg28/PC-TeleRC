"""Verify the map-only Windows artifact and absence of the FPV decoder runtime."""
from pathlib import Path
root=Path('dist/PC-TeleRC');names={p.name.lower() for p in root.rglob('*') if p.is_file()}
for name in ('pc-telerc.exe','telerc.png','telerc.ico'):
 if name not in names:raise SystemExit('Missing fleet component: '+name)
for name in ('qt6multimedia.dll','ffmpegmediaplugin.dll','test-pattern.mp4'):
 if name in names:raise SystemExit('Unexpected FPV component: '+name)
print('PASS map-only fleet package; no FPV media runtime')
