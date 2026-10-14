"""Compile isolated instances of the actual Link.h and simulate a radio chain.
Model assumptions: one-ms loops, two-ms clear-channel CAD, exact SF7/BW500
RadioLib airtime and adjacent-only RF reception. This is not a range/HIL claim.
"""
from pathlib import Path
import os, subprocess, tempfile
root=Path(__file__).resolve().parent
fw=root.parent/'TeleRCLoRa_ROVER'
with tempfile.TemporaryDirectory(prefix='telerc-chain-') as work:
 work=Path(work)
 for name in ('BASE','ROVER','NODE1','NODE2'):
  for header in ('Link','SketchSettings','RelayRoute'):
   text='// isolated '+name+' '+header+'\n'+(fw/(header+'.h')).read_text()
   text=text.replace('"SketchSettings.h"',f'"{name}-SketchSettings.h"').replace('"RelayRoute.h"',f'"{name}-RelayRoute.h"')
   (work/(name+'-'+header+'.h')).write_text(text)
 for relays in (0,1,2):
  binary=work/f'chain-{relays}'
  subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
   '-fsanitize=address,undefined','-fno-pie','-no-pie','-DARDUINO_USB_CDC_ON_BOOT=1',f'-DTEST_RELAYS={relays}',
   '-I',str(work),'-I',str(root.parent/'runtime-tests/mocks'),'-I',str(fw),
   str(root/'test_chain.cpp'),'-lcrypto','-o',str(binary)],check=True)
  subprocess.run([str(binary)],check=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'})
