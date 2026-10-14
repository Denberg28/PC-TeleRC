from pathlib import Path
import os,subprocess,tempfile
root=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='telerc-runtime-') as work:
 for role,seed in ((1,0),(3,1),(3,0)):
  binary=Path(work)/f'role-{role}-{seed}'
  subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
   '-fsanitize=address,undefined','-fno-pie','-no-pie','-DARDUINO_USB_CDC_ON_BOOT=1',f'-DTELERC_ROLE={role}',f'-DTELERC_TRANSPORT_WIFI={seed}',
   '-I',str(root/'mocks'),'-I',str(root.parent/('TeleRCLoRa_BASE' if role==1 else 'TeleRCLoRa_ROVER')),
   str(root/'test_runtime.cpp'),'-lcrypto','-o',str(binary)],check=True)
  subprocess.run([str(binary)],check=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'})
