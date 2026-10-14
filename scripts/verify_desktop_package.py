"""Check assets and the FFmpeg backend needed by network camera playback."""
from pathlib import Path

root=Path('dist/PC-TeleRC')
files=list(root.rglob('*'))
names={p.name.lower() for p in files if p.is_file()}
for name in ('pc-telerc.exe','telerc.png','telerc.ico','test-pattern.mp4','qt6multimedia.dll','ffmpegmediaplugin.dll'):
    if name not in names:
        raise SystemExit('Missing required packaged component: '+name)
for prefix in ('avcodec','avformat','avutil','swscale','swresample'):
    if not any(name.startswith(prefix) and name.endswith('.dll') for name in names):
        raise SystemExit('Missing FFmpeg runtime DLL: '+prefix)
print('Camera backend, logo assets and packaged application verified.')
