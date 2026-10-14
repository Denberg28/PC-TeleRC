#!/usr/bin/env python3
"""Host logic/mocks only; does not validate ESP32 drivers, RF, crypto or timing."""
import subprocess
import os
import tempfile
from pathlib import Path
root=Path(__file__).resolve().parent
firmware=root.parent
cases=[('wifi','test_wifi.cpp','ROVER',[]),('routing','test_routing.cpp','ROVER',[]),('retry','test_retry.cpp','ROVER',[]),('lora_rover','test_lora.cpp','ROVER',[]),('lora_base','test_lora.cpp','BASE',['-DTEST_BASE=1']),('led','test_led.cpp','ROVER',[])]
with tempfile.TemporaryDirectory() as work:
 for name,source,role,extra in cases:
  binary=Path(work)/name
  subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-fsanitize=address,undefined','-fno-pie','-no-pie','-DARDUINO_USB_CDC_ON_BOOT=1',*extra,'-I',str(root/'mocks'),'-I',str(firmware/f'TeleRCLoRa_{role}'),str(root/source),'-o',str(binary)],check=True)
  subprocess.run([str(binary)],check=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'})
