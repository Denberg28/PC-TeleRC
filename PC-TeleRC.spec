# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

pymav_datas, pymav_bins, pymav_hidden = collect_all('pymavlink')
pygame_datas, pygame_bins, pygame_hidden = collect_all('pygame')

analysis = Analysis(
    ['main.py'],
    pathex=['src'],
    binaries=pymav_bins + pygame_bins,
    datas=pymav_datas + pygame_datas + [('src/pctelerc/assets', 'pctelerc/assets'), ('tests/fixtures/test-pattern.mp4', 'pctelerc/assets')],
    hiddenimports=pymav_hidden + pygame_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name='PC-TeleRC',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='src/pctelerc/assets/telerc.ico',
)

coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PC-TeleRC',
)

