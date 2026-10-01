# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
pymav_datas,pymav_bins,pymav_hidden=collect_all('pymavlink')
pygame_datas,pygame_bins,pygame_hidden=collect_all('pygame')
analysis=Analysis(['main.py'],pathex=['src'],binaries=pymav_bins+pygame_bins,datas=pymav_datas+pygame_datas,hiddenimports=pymav_hidden+pygame_hidden,hookspath=[],hooksconfig={},runtime_hooks=[],excludes=[],noarchive=False)
pyz=PYZ(analysis.pure)
exe=EXE(pyz,analysis.scripts,analysis.binaries,analysis.datas,[],name='PC-TeleRC',debug=False,bootloader_ignore_signals=False,strip=False,upx=True,console=False,disable_windowed_traceback=False,argv_emulation=False,target_arch=None,codesign_identity=None,entitlements_file=None,icon=None)
