from pathlib import Path
import os,subprocess,tempfile
root=Path(__file__).resolve().parent
cases=[]
for role,seed in ((1,0),(3,1),(3,0),(2,0)):
 for name in ('runtime','sleep','sketch_pairing'):
  extra=['-DTELERC_RELAY_COUNT=1'] if role==2 else []
  if name=='sketch_pairing':extra+=['-DTELERC_LORA_PASSWORD="Ab12Cd34"']
  cases.append((role,seed,name,extra))
with tempfile.TemporaryDirectory(prefix='telerc-runtime-') as work:
 for role,seed,name,extra in cases:
  binary=Path(work)/f'role-{role}-{seed}-{name}'
  folder='BASE' if role==1 else 'NODE' if role==2 else 'ROVER'
  subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
   '-fsanitize=address,undefined','-fno-pie','-no-pie','-DARDUINO_USB_CDC_ON_BOOT=1',f'-DTELERC_ROLE={role}',f'-DTELERC_TRANSPORT_WIFI={seed}',*extra,
   '-I',str(root/'mocks'),'-I',str(root.parent/('TeleRCLoRa_'+folder)),
   str(root/('test_'+name+'.cpp')),'-lcrypto','-o',str(binary)],check=True)
  subprocess.run([str(binary)],check=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'})
 # Invalid sketch passwords fail compilation, rather than silently using old NVS.
 for password in ('short','1234 678','123456789'):
  result=subprocess.run(['g++','-std=c++17','-DTELERC_ROLE=1',f'-DTELERC_LORA_PASSWORD="{password}"',
   '-I',str(root.parent/'TeleRCLoRa_BASE'),'-x','c++','-fsyntax-only','-'],input='#include "SketchSettings.h"\n',text=True,capture_output=True)
  assert result.returncode!=0 and 'exactly 8 visible ASCII' in result.stderr
 print('Invalid sketch passwords: compile-time rejection passed')
