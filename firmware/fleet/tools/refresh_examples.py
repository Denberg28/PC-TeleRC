#!/usr/bin/env python3
"""Refresh only the public keyless example folders after a source edit."""
from pathlib import Path
import shutil
from network import ROOT,sketch
for role,identity in [('base',1),('rover',1),('node',1),('node',2)]:
    name='TeleRCFleet_'+role.upper()+(f'_{identity:03d}' if role!='base' else '')
    target=ROOT/'sketches'/name
    if target.exists():
        config=(target/'NetworkConfig.h').read_text()
        if '#define PROVISIONED 0' not in config:
            raise ValueError('Refusing to replace a provisioned sketch')
        shutil.rmtree(target)
    sketch(target,role,identity)
print('Refreshed four RF-OFF examples; private profiles untouched.')
