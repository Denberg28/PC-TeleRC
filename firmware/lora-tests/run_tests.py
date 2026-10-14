from pathlib import Path
import os
import subprocess
import tempfile

here = Path(__file__).resolve().parent
sketch = here.parent / 'TeleRCLoRa_BASE'
with tempfile.TemporaryDirectory(prefix='telerc-lora-') as temporary:
    for role in (1, 3):
        output = Path(temporary) / f'role-{role}'
        subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                        '-fno-pie', '-no-pie', '-DARDUINO_USB_CDC_ON_BOOT=1', f'-DTELERC_ROLE={role}',
                        '-I', str(here / 'stubs'), '-I', str(sketch),
                        str(here / 'test_link.cpp'), '-lcrypto', '-o', str(output)], check=True)
        subprocess.run([str(output)], check=True,
                       env={**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0'})

